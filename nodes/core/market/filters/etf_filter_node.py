import asyncio
import logging
from typing import Any

import httpx

from core.api_key_vault import APIKeyVault
from core.types_registry import AssetSymbol, NodeCategory, OHLCVBar, get_type
from nodes.core.market.filters.base.base_filter_node import BaseFilter
from services.rate_limiter import RateLimiter

logger = logging.getLogger(__name__)


class ETFFilter(BaseFilter):
    """
    Filters ETFs out of OHLCV bundles to keep only stocks.

    Checks ticker details from Polygon.io API to determine if an asset is an ETF.
    Only keeps non-ETF assets in the output.
    
    Uses worker pool pattern with rate limiting for optimal performance.
    """

    CATEGORY = NodeCategory.MARKET
    inputs = {"ohlcv_bundle": get_type("OHLCVBundle")}
    outputs = {"filtered_ohlcv_bundle": get_type("OHLCVBundle")}
    default_params = {
        "exclude_etfs": True,  # True = filter out ETFs, False = keep only ETFs
        "max_concurrent": 5,  # Maximum concurrent workers
        "rate_limit_per_second": 10,  # API calls per second
    }
    params_meta = [
        {
            "name": "exclude_etfs",
            "type": "combo",
            "default": True,
            "options": [True, False],
            "label": "Exclude ETFs",
            "description": "If true, filters out ETFs (keeps only stocks). If false, keeps only ETFs.",
        },
        {
            "name": "max_concurrent",
            "type": "integer",
            "default": 5,
            "label": "Max Concurrent Workers",
            "description": "Maximum number of concurrent workers (default: 5)",
        },
        {
            "name": "rate_limit_per_second",
            "type": "integer",
            "default": 10,
            "label": "Rate Limit",
            "description": "API requests per second (default: 10)",
        },
    ]

    # Class-level cache to avoid repeated API calls
    _etf_cache: dict[str, bool] = {}

    def __init__(
        self,
        id: int,
        params: dict[str, Any] | None = None,
        graph_context: dict[str, Any] | None = None,
    ):
        super().__init__(id, params or {}, graph_context)
        self.exclude_etfs = self.params.get("exclude_etfs", True)
        self.max_concurrent = self.params.get("max_concurrent", 5)
        self.rate_limit_per_second = self.params.get("rate_limit_per_second", 10)
        self.workers = []

    def force_stop(self):
        """Cancel all workers on stop."""
        for w in self.workers:
            if not w.done():
                w.cancel()
        self.workers.clear()

    async def _check_etf(self, symbol: AssetSymbol, api_key: str, client: httpx.AsyncClient, rate_limiter: RateLimiter) -> bool:
        """Check if symbol is an ETF using Polygon API."""
        ticker = symbol.ticker
        
        # Check cache first
        if ticker in ETFFilter._etf_cache:
            return ETFFilter._etf_cache[ticker]
        
        url = f"https://api.polygon.io/v3/reference/tickers/{ticker}"
        params: dict[str, str] = {"apiKey": api_key}

        await rate_limiter.acquire()
        try:
            response = await client.get(url, params=params, timeout=10.0)
            response.raise_for_status()
            data = response.json()
            results = data.get("results", {})

            # Check multiple fields that indicate ETF status
            market_type = results.get("market", "")
            type_field = results.get("type", "")

            # Common ETF indicators in Polygon API
            is_etf = (
                market_type == "etp"  # Exchange Traded Product
                or type_field == "ETF"
                or "etf" in market_type.lower()
                or "etf" in type_field.lower()
            )

            # Cache the result
            ETFFilter._etf_cache[ticker] = is_etf
            return is_etf
        except Exception as e:
            logger.warning(f"Failed to fetch ETF status for {symbol}: {e}")
            # Cache as not an ETF when uncertain
            ETFFilter._etf_cache[ticker] = False
            return False

    async def _execute_impl(self, inputs: dict[str, Any]) -> dict[str, Any]:
        """Worker pool execution with rate limiting - matches PolygonBatchCustomBars pattern."""
        ohlcv_bundle: dict[AssetSymbol, list[OHLCVBar]] = inputs.get("ohlcv_bundle", {})

        if not ohlcv_bundle:
            return {"filtered_ohlcv_bundle": {}}

        api_key = APIKeyVault().get("POLYGON_API_KEY")
        if not api_key:
            raise ValueError("Polygon API key not found in vault")

        # Filter out empty data first
        symbols_to_check = [(symbol, ohlcv_data) for symbol, ohlcv_data in ohlcv_bundle.items() if ohlcv_data]
        
        if not symbols_to_check:
            return {"filtered_ohlcv_bundle": {}}

        total_symbols = len(symbols_to_check)
        completed_count = 0
        etf_results: dict[AssetSymbol, bool] = {}
        
        # Create queue and rate limiter
        queue: asyncio.Queue = asyncio.Queue()
        for sym, _ in symbols_to_check:
            queue.put_nowait(sym)
        
        rate_limiter = RateLimiter(max_per_second=self.rate_limit_per_second)
        
        # Create shared HTTP client
        async with httpx.AsyncClient() as client:
            async def worker(worker_id: int):
                nonlocal completed_count
                while not queue.empty():
                    try:
                        symbol = queue.get_nowait()
                    except asyncio.QueueEmpty:
                        break
                    
                    try:
                        is_etf = await self._check_etf(symbol, api_key, client, rate_limiter)
                        etf_results[symbol] = is_etf
                        
                        completed_count += 1
                        # Report progress every 10% or at the end
                        if completed_count % max(1, total_symbols // 10) == 0 or completed_count == total_symbols:
                            progress = (completed_count / total_symbols) * 100.0
                            self.report_progress(progress, f"{completed_count}/{total_symbols}")
                    except Exception as e:
                        logger.warning(f"Worker {worker_id} failed to check {symbol}: {e}")
                        etf_results[symbol] = False  # Default to not ETF on error
                        completed_count += 1
            
            # Start workers
            self.workers = [asyncio.create_task(worker(i)) for i in range(self.max_concurrent)]
            await asyncio.gather(*self.workers, return_exceptions=True)
            self.workers.clear()
        
        # Build filtered bundle
        filtered_bundle = {}
        for symbol, ohlcv_data in symbols_to_check:
            is_etf = etf_results.get(symbol, False)
            # If exclude_etfs is True, include when NOT an ETF
            # If exclude_etfs is False, include when IS an ETF
            should_include = not is_etf if self.exclude_etfs else is_etf
            if should_include:
                filtered_bundle[symbol] = ohlcv_data
        
        logger.info(
            f"ETF Filter: Kept {len(filtered_bundle)}/{total_symbols} symbols "
            f"(cache size: {len(ETFFilter._etf_cache)})"
        )

        return {"filtered_ohlcv_bundle": filtered_bundle}
