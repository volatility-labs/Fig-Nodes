import asyncio
import logging
from typing import Any

import httpx

from core.api_key_vault import APIKeyVault
from core.types_registry import AssetSymbol, NodeCategory, OHLCVBar, get_type
from nodes.core.market.filters.base.base_filter_node import BaseFilter

logger = logging.getLogger(__name__)


class ETFFilter(BaseFilter):
    """
    Filters ETFs out of OHLCV bundles to keep only stocks.

    Checks ticker details from Polygon.io API to determine if an asset is an ETF.
    Only keeps non-ETF assets in the output.
    
    Uses parallel API requests with rate limiting for optimal performance.
    """

    CATEGORY = NodeCategory.MARKET
    inputs = {"ohlcv_bundle": get_type("OHLCVBundle")}
    outputs = {"filtered_ohlcv_bundle": get_type("OHLCVBundle")}
    default_params = {
        "exclude_etfs": True,  # True = filter out ETFs, False = keep only ETFs
        "max_concurrent_requests": 20,  # Maximum concurrent API requests
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
            "name": "max_concurrent_requests",
            "type": "integer",
            "default": 20,
            "label": "Max Concurrent Requests",
            "description": "Maximum number of parallel API requests (default: 20)",
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
        self.max_concurrent_requests = self.params.get("max_concurrent_requests", 20)
        self._semaphore = asyncio.Semaphore(self.max_concurrent_requests)

    async def _is_etf(self, symbol: AssetSymbol, api_key: str, client: httpx.AsyncClient) -> bool:
        """Check if symbol is an ETF using Polygon API with rate limiting."""
        ticker = symbol.ticker
        
        # Check cache first
        if ticker in ETFFilter._etf_cache:
            return ETFFilter._etf_cache[ticker]
        
        url = f"https://api.polygon.io/v3/reference/tickers/{ticker}"
        params: dict[str, str] = {"apiKey": api_key}

        async with self._semaphore:  # Rate limiting
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
        """Optimized execution using parallel API requests with progress reporting."""
        ohlcv_bundle: dict[AssetSymbol, list[OHLCVBar]] = inputs.get("ohlcv_bundle", {})

        if not ohlcv_bundle:
            self.report_progress(100.0, "No symbols to filter")
            return {"filtered_ohlcv_bundle": {}}

        api_key = APIKeyVault().get("POLYGON_API_KEY")
        if not api_key:
            raise ValueError("Polygon API key not found in vault")

        # Filter out empty data first
        symbols_to_check = [(symbol, ohlcv_data) for symbol, ohlcv_data in ohlcv_bundle.items() if ohlcv_data]
        
        if not symbols_to_check:
            self.report_progress(100.0, "No valid symbols to filter")
            return {"filtered_ohlcv_bundle": {}}

        total_symbols = len(symbols_to_check)
        action = "Excluding ETFs" if self.exclude_etfs else "Keeping only ETFs"
        self.report_progress(10.0, f"{action}: checking {total_symbols} symbols...")
        logger.info(f"ETF Filter: Checking {total_symbols} symbols in parallel...")
        
        # Tracking for progress updates
        completed_count = 0
        filtered_bundle = {}
        errors = 0
        
        # Create a shared HTTP client for all requests
        async with httpx.AsyncClient() as client:
            # Create tasks for all symbols with progress tracking
            async def check_symbol_with_progress(symbol: AssetSymbol, ohlcv_data: list[OHLCVBar]) -> tuple[AssetSymbol, list[OHLCVBar], bool]:
                """Check a single symbol and return (symbol, data, should_include)."""
                nonlocal completed_count
                try:
                    is_etf = await self._is_etf(symbol, api_key, client)
                    # If exclude_etfs is True, include when NOT an ETF
                    # If exclude_etfs is False, include when IS an ETF
                    should_include = not is_etf if self.exclude_etfs else is_etf
                    
                    # Update progress periodically
                    completed_count += 1
                    if completed_count % max(1, total_symbols // 10) == 0 or completed_count == total_symbols:
                        progress = 10.0 + (completed_count / total_symbols * 80.0)  # 10-90%
                        self.report_progress(
                            progress,
                            f"{action}: {completed_count}/{total_symbols} checked"
                        )
                    
                    return (symbol, ohlcv_data, should_include)
                except Exception as e:
                    logger.warning(f"Failed to process ETF filter for {symbol}: {e}")
                    # On error, exclude to be safe
                    completed_count += 1
                    return (symbol, ohlcv_data, False)

            # Process all symbols in parallel
            tasks = [check_symbol_with_progress(symbol, ohlcv_data) for symbol, ohlcv_data in symbols_to_check]
            results = await asyncio.gather(*tasks, return_exceptions=True)

        # Build filtered bundle from results
        self.report_progress(90.0, "Building filtered results...")
        
        etfs_found = 0
        stocks_found = 0
        
        for result in results:
            if isinstance(result, Exception):
                errors += 1
                logger.error(f"ETF filter task failed: {result}")
                continue
            
            symbol, ohlcv_data, should_include = result
            
            # Track what we found for better reporting
            is_etf = symbol.ticker in ETFFilter._etf_cache and ETFFilter._etf_cache[symbol.ticker]
            if is_etf:
                etfs_found += 1
            else:
                stocks_found += 1
            
            if should_include:
                filtered_bundle[symbol] = ohlcv_data

        # Final status message
        kept = len(filtered_bundle)
        removed = total_symbols - kept
        status_msg = f"Kept {kept}/{total_symbols} symbols ({etfs_found} ETFs, {stocks_found} stocks found)"
        if errors > 0:
            status_msg += f", {errors} errors"
        
        logger.info(
            f"ETF Filter: {status_msg} (cached: {len(ETFFilter._etf_cache)})"
        )
        
        self.report_progress(95.0, status_msg)

        return {"filtered_ohlcv_bundle": filtered_bundle}
