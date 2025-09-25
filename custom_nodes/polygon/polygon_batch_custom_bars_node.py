import logging
import asyncio
import time
from typing import Dict, Any, List
from nodes.base.base_node import BaseNode
from core.types_registry import get_type, AssetSymbol, OHLCVBar
from services.polygon_service import fetch_bars

logger = logging.getLogger(__name__)

class RateLimiter:
    """Simple rate limiter to stay under Polygon's recommended 100 requests/second."""

    def __init__(self, max_per_second: int = 100):
        self.max_per_second = max_per_second
        self.requests = []
        self.lock = asyncio.Lock()

    async def acquire(self):
        """Wait if necessary to stay under the rate limit."""
        async with self.lock:
            now = time.time()

            # Remove requests older than 1 second
            self.requests = [req_time for req_time in self.requests if now - req_time < 1.0]

            # If we're at the limit, wait until we can make another request
            if len(self.requests) >= self.max_per_second:
                oldest_request = min(self.requests)
                sleep_time = 1.0 - (now - oldest_request)
                if sleep_time > 0:
                    await asyncio.sleep(sleep_time)
                    # Refresh the list after sleeping
                    now = time.time()
                    self.requests = [req_time for req_time in self.requests if now - req_time < 1.0]

            # Record this request
            self.requests.append(now)

class PolygonBatchCustomBarsNode(BaseNode):
    """
    Fetches custom aggregate bars (OHLCV) for multiple symbols from Polygon.io in batch.
    Outputs a bundle (dict of symbol to list of bars).
    """
    inputs = {"symbols": get_type("AssetSymbolList"), "api_key": get_type("APIKey")}
    outputs = {"ohlcv_bundle": Dict[AssetSymbol, List[OHLCVBar]]}
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
        {"name": "timespan", "type": "combo", "default": "day", "options": ["minute", "hour", "day", "week", "month", "quarter", "year"]},
        {"name": "lookback_period", "type": "combo", "default": "3 months", "options": ["1 day", "3 days", "1 week", "2 weeks", "1 month", "2 months", "3 months", "4 months", "6 months", "9 months", "1 year", "18 months", "2 years", "3 years", "5 years", "10 years"]},
        {"name": "adjusted", "type": "combo", "default": True, "options": [True, False]},
        {"name": "sort", "type": "combo", "default": "asc", "options": ["asc", "desc"]},
        {"name": "limit", "type": "number", "default": 5000, "min": 1, "max": 50000, "step": 1},
        # Internal execution controls are not exposed to UI
    ]

    async def execute(self, inputs: Dict[str, Any]) -> Dict[str, Dict[AssetSymbol, List[OHLCVBar]]]:
        symbols: List[AssetSymbol] = inputs.get("symbols", [])
        if not symbols:
            return {"ohlcv_bundle": {}}

        api_key = inputs.get("api_key")
        if not api_key:
            raise ValueError("Polygon API key input is required")

        max_concurrent = self.params.get("max_concurrent", 10)
        rate_limit = self.params.get("rate_limit_per_second", 95)
        bundle: Dict[AssetSymbol, List[OHLCVBar]] = {}
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
                try:
                    sym = queue.get_nowait()
                except asyncio.QueueEmpty:
                    break
                # Respect Polygon rate limit
                await rate_limiter.acquire()
                try:
                    bars = await fetch_bars(sym, api_key, self.params)
                    if bars:
                        bundle[sym] = bars
                except Exception as e:
                    logger.warning(f"Worker {worker_id}: failed to fetch bars for {sym}: {e}")
                finally:
                    completed_count += 1
                    progress = (completed_count / total_symbols) * 100
                    progress_text = f"{completed_count}/{total_symbols}"
                    self.report_progress(progress, progress_text)
                    queue.task_done()

        workers = [asyncio.create_task(worker(i)) for i in range(min(max_concurrent, total_symbols))]
        try:
            await asyncio.gather(*workers)
        except asyncio.CancelledError:
            for w in workers:
                if not w.done():
                    w.cancel()
            raise

        return {"ohlcv_bundle": bundle}
