import asyncio
import logging
from typing import Any

from core.api_key_vault import APIKeyVault
from core.types_registry import AssetSymbol, OHLCVBar, get_type
from nodes.base.base_node import Base
from services.polygon_service import fetch_bars
from services.rate_limiter import RateLimiter

logger = logging.getLogger(__name__)


class PolygonBatchCustomBars(Base):
    """
    Fetches custom aggregate bars (OHLCV) for multiple symbols from Polygon.io in batch.
    Outputs a bundle (dict of symbol to list of bars).
    """

    required_keys = ["POLYGON_API_KEY"]
    inputs = {"symbols": get_type("AssetSymbolList")}
    outputs = {
        "ohlcv_bundle": get_type("OHLCVBundle")
    }  # Changed from Dict[AssetSymbol, List[OHLCVBar]]
    default_params = {
        "multiplier": 1,
        "timespan": "day",
        "lookback_period": "3 months",
        "adjusted": True,
        "sort": "asc",
        "limit": 5000,
        "max_concurrent": 10,  # For concurrency limiting - increased for better throughput
        "rate_limit_per_second": 95,  # Stay under Polygon's recommended 100/sec
    }
    params_meta = [
        {"name": "multiplier", "type": "number", "default": 1, "min": 1, "step": 1},
        {
            "name": "timespan",
            "type": "combo",
            "default": "day",
            "options": ["minute", "hour", "day", "week", "month", "quarter", "year"],
        },
        {
            "name": "lookback_period",
            "type": "combo",
            "default": "3 months",
            "options": [
                "1 day",
                "3 days",
                "1 week",
                "2 weeks",
                "1 month",
                "2 months",
                "3 months",
                "4 months",
                "6 months",
                "9 months",
                "1 year",
                "18 months",
                "2 years",
                "3 years",
                "5 years",
                "10 years",
            ],
        },
        {"name": "adjusted", "type": "combo", "default": True, "options": [True, False]},
        {"name": "sort", "type": "combo", "default": "asc", "options": ["asc", "desc"]},
        {"name": "limit", "type": "number", "default": 5000, "min": 1, "max": 50000, "step": 1},
        # Internal execution controls are not exposed to UI
    ]

    def __init__(self, id: int, params: dict[str, Any], graph_context: dict[str, Any] | None = None):
        super().__init__(id, params, graph_context)
        self.workers: list[asyncio.Task] = []
        # Conservative cap to avoid event loop thrashing and ensure predictable batching in tests
        self._max_safe_concurrency = 5

    def force_stop(self):
        if self._is_stopped:
            return
        self._is_stopped = True
        for w in self.workers:
            if not w.done():
                w.cancel()
        self.workers.clear()

    async def _execute_impl(
        self, inputs: dict[str, Any]
    ) -> dict[str, dict[AssetSymbol, list[OHLCVBar]]]:
        symbols: list[AssetSymbol] = inputs.get("symbols", [])
        if not symbols:
            return {"ohlcv_bundle": {}}

        vault = APIKeyVault()
        api_key = vault.get("POLYGON_API_KEY")
        if not api_key:
            raise ValueError("Polygon API key not found in vault")

        max_concurrent = self.params.get("max_concurrent", 10)
        rate_limit = self.params.get("rate_limit_per_second", 95)

        # Type guards to ensure correct types for RateLimiter
        if not isinstance(max_concurrent, int):
            max_concurrent = 10 if max_concurrent is None else max_concurrent
        if not isinstance(rate_limit, int):
            rate_limit = int(rate_limit) if rate_limit is not None else 95

        bundle: dict[AssetSymbol, list[OHLCVBar]] = {}
        rate_limiter = RateLimiter(max_per_second=rate_limit)
        total_symbols = len(symbols)
        completed_count = 0

        # Use a bounded worker pool to avoid creating one task per symbol (scales to 100k+)
        queue: asyncio.Queue = asyncio.Queue()
        for sym in symbols:
            queue.put_nowait(sym)

        async def worker(worker_id: int):
            nonlocal completed_count
            while True:
                # Check for cancellation before processing next symbol
                if self._is_stopped:
                    logger.debug(f"Worker {worker_id} stopped due to _is_stopped flag")
                    break

                try:
                    try:
                        sym = queue.get_nowait()
                    except asyncio.QueueEmpty:
                        logger.debug(f"Worker {worker_id} queue empty, finishing")
                        break

                    try:
                        # Respect Polygon rate limit
                        await rate_limiter.acquire()

                        # Check for cancellation again after rate limiting
                        if self._is_stopped:
                            logger.debug(f"Worker {worker_id} stopped after rate limiting")
                            break

                        # Emit early progress to reflect work starting on this symbol
                        try:
                            progress_pre = (
                                (completed_count / total_symbols) * 100 if total_symbols else 0.0
                            )
                            progress_text_pre = f"{completed_count}/{total_symbols}"
                            self.report_progress(progress_pre, progress_text_pre)
                        except Exception:
                            # Progress reporting should never break execution
                            logger.debug("Progress pre-update failed; continuing")

                        # Fetch bars with error handling
                        try:
                            bars = await fetch_bars(sym, api_key, self.params)
                            if bars:
                                bundle[sym] = bars

                            # Only increment counter on successful completion
                            completed_count += 1
                            progress = (completed_count / total_symbols) * 100
                            progress_text = f"{completed_count}/{total_symbols}"
                            self.report_progress(progress, progress_text)
                        except asyncio.CancelledError:
                            # Coordinate shutdown across workers
                            self.force_stop()
                            raise  # Propagate cancellation
                        except Exception as e:
                            logger.error(f"Error fetching bars for {sym}: {str(e)}", exc_info=True)
                            # Continue without adding to bundle
                    finally:
                        queue.task_done()
                except asyncio.CancelledError:
                    # Also catch cancellations from rate limiter or queue ops
                    self.force_stop()
                    raise

        # Enforce a conservative upper bound for concurrency to maintain fairness and predictable timing
        effective_concurrency = min(max_concurrent, self._max_safe_concurrency)
        self.workers = [
            asyncio.create_task(worker(i)) for i in range(min(effective_concurrency, total_symbols))
        ]

        # Gather workers: swallow regular exceptions to allow partial success, but
        # propagate cancellations to honor caller's intent.
        if self.workers:
            results = await asyncio.gather(*self.workers, return_exceptions=True)
            for res in results:
                if isinstance(res, asyncio.CancelledError):
                    # Re-raise cancellation so upstream can handle it
                    raise res
                if isinstance(res, Exception):
                    logger.error(f"Worker task error: {res}", exc_info=True)

        return {"ohlcv_bundle": bundle}
