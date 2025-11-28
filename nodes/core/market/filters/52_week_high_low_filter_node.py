import asyncio
import logging
import math
from typing import Any

from core.api_key_vault import APIKeyVault
from core.types_registry import (
    AssetSymbol,
    IndicatorResult,
    IndicatorType,
    IndicatorValue,
    NodeOutputs,
    OHLCVBar,
    get_type,
)
from nodes.core.market.filters.base.base_indicator_filter_node import BaseIndicatorFilter
from services.polygon_service import fetch_bars
from services.rate_limiter import RateLimiter

logger = logging.getLogger(__name__)


class Week52HighLowFilter(BaseIndicatorFilter):
    """
    Filters assets based on proximity to 52-week high or low prices.
    
    Fetches 1 year of daily bars from Massive.com API and calculates:
    - 52-week high: Maximum high price over the past year
    - 52-week low: Minimum low price over the past year
    
    Filter options:
    - Filter by proximity to 52-week high (within X% of high)
    - Filter by proximity to 52-week low (within X% of low)
    - Filter mode: "near_high", "near_low", or "both"
    """

    inputs = {
        "ohlcv_bundle": get_type("OHLCVBundle"),
    }

    default_params = {
        "filter_mode": "near_high",  # 'near_high', 'near_low', 'both'
        "proximity_threshold_pct": 5.0,  # Percentage threshold (e.g., 5.0 = within 5% of high/low)
        "lookback_days": 365,  # Number of days to look back (default 52 weeks)
    }

    params_meta = [
        {
            "name": "filter_mode",
            "type": "combo",
            "default": "near_high",
            "options": ["near_high", "near_low", "both"],
            "label": "Filter Mode",
            "description": "Filter for assets near 52-week high, low, or both",
        },
        {
            "name": "proximity_threshold_pct",
            "type": "number",
            "default": 5.0,
            "min": 0.0,
            "max": 100.0,
            "step": 0.1,
            "precision": 2,
            "label": "Proximity Threshold (%)",
            "unit": "%",
            "description": "Maximum distance from 52-week high/low as percentage (e.g., 5.0 = within 5%)",
        },
        {
            "name": "lookback_days",
            "type": "number",
            "default": 365,
            "min": 1,
            "step": 1,
            "label": "Lookback Days",
            "description": "Number of days to look back for high/low calculation (default: 365 for 52 weeks)",
        },
    ]

    def __init__(
        self, id: int, params: dict[str, Any], graph_context: dict[str, Any] | None = None
    ):
        super().__init__(id, params, graph_context)
        self.workers: list[asyncio.Task[None]] = []
        self._max_safe_concurrency = 5

    def force_stop(self):
        if self._is_stopped:
            return
        self._is_stopped = True
        for w in self.workers:
            if not w.done():
                w.cancel()
        self.workers.clear()

    def _validate_indicator_params(self):
        filter_mode = self.params.get("filter_mode", "near_high")
        proximity_threshold_pct = self.params.get("proximity_threshold_pct", 5.0)
        lookback_days = self.params.get("lookback_days", 365)
        max_concurrent = self.params.get("max_concurrent", 10)
        rate_limit_per_second = self.params.get("rate_limit_per_second", 95)

        if filter_mode not in ["near_high", "near_low", "both"]:
            raise ValueError('filter_mode must be "near_high", "near_low", or "both"')

        if not isinstance(proximity_threshold_pct, (int, float)) or proximity_threshold_pct < 0:
            raise ValueError("proximity_threshold_pct must be a non-negative number")

        if not isinstance(lookback_days, int) or lookback_days <= 0:
            raise ValueError("lookback_days must be a positive integer")

    async def _fetch_year_bars(self, symbol: AssetSymbol, api_key: str) -> list[OHLCVBar]:
        """Fetch daily bars for the past year (or specified lookback period)."""
        lookback_days = self.params.get("lookback_days", 365)
        if not isinstance(lookback_days, int):
            lookback_days = 365

        fetch_params = {
            "multiplier": 1,
            "timespan": "day",
            "lookback_period": f"{lookback_days} days",
            "adjusted": True,
            "sort": "asc",
            "limit": 5000,  # Massive.com API limit
        }

        bars, _metadata = await fetch_bars(symbol, api_key, fetch_params)
        return bars

    def _calculate_52_week_high_low(
        self, bars: list[OHLCVBar]
    ) -> tuple[float | None, float | None, float | None]:
        """
        Calculate 52-week high, low, and current price from bars.
        
        Returns:
            Tuple of (52_week_high, 52_week_low, current_price) or (None, None, None) if insufficient data
        """
        if not bars or len(bars) < 1:
            return None, None, None

        # Extract all highs and lows from the bars
        highs = [bar["high"] for bar in bars if isinstance(bar.get("high"), (int, float))]
        lows = [bar["low"] for bar in bars if isinstance(bar.get("low"), (int, float))]

        if not highs or not lows:
            return None, None, None

        # Calculate 52-week high and low
        week52_high = max(highs)
        week52_low = min(lows)

        # Get current price (last bar's close)
        last_bar = bars[-1]
        current_price = last_bar.get("close")
        if not isinstance(current_price, (int, float)):
            return None, None, None

        return week52_high, week52_low, float(current_price)

    async def _calculate_week52_indicator(
        self, symbol: AssetSymbol, api_key: str
    ) -> IndicatorResult:
        """Fetch bars and calculate 52-week high/low indicator."""
        bars = await self._fetch_year_bars(symbol, api_key)

        if not bars:
            return IndicatorResult(
                indicator_type=IndicatorType.WEEK52_HIGH_LOW,
                timestamp=0,
                values=IndicatorValue(lines={}),
                params=self.params,
                error="No bars fetched",
            )

        week52_high, week52_low, current_price = self._calculate_52_week_high_low(bars)

        if week52_high is None or week52_low is None or current_price is None:
            return IndicatorResult(
                indicator_type=IndicatorType.WEEK52_HIGH_LOW,
                timestamp=bars[-1]["timestamp"] if bars else 0,
                values=IndicatorValue(lines={}),
                params=self.params,
                error="Failed to calculate 52-week high/low",
            )

        # Calculate proximity percentages
        if week52_high > 0:
            distance_from_high = ((week52_high - current_price) / week52_high) * 100.0
        else:
            distance_from_high = float("inf")

        if week52_low > 0:
            distance_from_low = ((current_price - week52_low) / week52_low) * 100.0
        else:
            distance_from_low = float("inf")

        return IndicatorResult(
            indicator_type=IndicatorType.WEEK52_HIGH_LOW,
            timestamp=bars[-1]["timestamp"],
            values=IndicatorValue(
                lines={
                    "week52_high": week52_high,
                    "week52_low": week52_low,
                    "current_price": current_price,
                    "distance_from_high_pct": distance_from_high,
                    "distance_from_low_pct": distance_from_low,
                }
            ),
            params=self.params,
        )

    def _should_pass_filter(self, indicator_result: IndicatorResult) -> bool:
        """Pass filter based on proximity to 52-week high/low."""
        if indicator_result.error:
            return False

        lines = indicator_result.values.lines
        if not lines:
            return False

        distance_from_high_pct = lines.get("distance_from_high_pct")
        distance_from_low_pct = lines.get("distance_from_low_pct")

        if distance_from_high_pct is None or distance_from_low_pct is None:
            return False

        if not math.isfinite(distance_from_high_pct) or not math.isfinite(distance_from_low_pct):
            return False

        filter_mode = self.params.get("filter_mode", "near_high")
        proximity_threshold_pct = self.params.get("proximity_threshold_pct", 5.0)
        if not isinstance(proximity_threshold_pct, (int, float)):
            return False
        threshold = float(proximity_threshold_pct)

        if filter_mode == "near_high":
            # Pass if within threshold of 52-week high
            return distance_from_high_pct <= threshold
        elif filter_mode == "near_low":
            # Pass if within threshold of 52-week low
            return distance_from_low_pct <= threshold
        elif filter_mode == "both":
            # Pass if within threshold of either high or low
            return distance_from_high_pct <= threshold or distance_from_low_pct <= threshold
        else:
            return False

    async def _execute_impl(self, inputs: dict[str, Any]) -> NodeOutputs:
        """Override to handle async data fetching for 52-week high/low calculation."""
        api_key = APIKeyVault().get("POLYGON_API_KEY")
        if not api_key:
            raise ValueError("Massive.com API key (POLYGON_API_KEY) not found in vault")

        ohlcv_bundle: dict[AssetSymbol, list[OHLCVBar]] = inputs.get("ohlcv_bundle", {})

        if not ohlcv_bundle:
            return {"filtered_ohlcv_bundle": {}}

        # Internal defaults - not exposed to users
        max_concurrent = 10
        rate_limit = 95  # Stay under Polygon's recommended 100/sec

        filtered_bundle = {}
        rate_limiter = RateLimiter(max_per_second=rate_limit)
        total_symbols = len(ohlcv_bundle)
        completed_count = 0

        # Use a bounded worker pool for concurrency
        queue: asyncio.Queue[tuple[AssetSymbol, list[OHLCVBar]]] = asyncio.Queue()
        for symbol, ohlcv_data in ohlcv_bundle.items():
            if ohlcv_data:
                queue.put_nowait((symbol, ohlcv_data))

        async def worker(worker_id: int):
            nonlocal completed_count
            while True:
                if self._is_stopped:
                    logger.debug(f"Worker {worker_id} stopped due to _is_stopped flag")
                    break

                try:
                    try:
                        symbol, ohlcv_data = queue.get_nowait()
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

                        # Fetch 52-week data and calculate indicator
                        indicator_result = await self._calculate_week52_indicator(symbol, api_key)

                        if self._should_pass_filter(indicator_result):
                            filtered_bundle[symbol] = ohlcv_data

                        # Only increment counter on successful completion
                        completed_count += 1
                        progress = (completed_count / max(1, total_symbols)) * 100.0
                        progress_text = f"{completed_count}/{total_symbols}"
                        self.report_progress(progress, progress_text)
                    except asyncio.CancelledError:
                        # Coordinate shutdown across workers
                        self.force_stop()
                        raise  # Propagate cancellation
                    except Exception as e:
                        logger.warning(f"Failed to process 52-week high/low for {symbol}: {e}")
                        # Continue without adding to bundle
                        completed_count += 1
                        try:
                            progress = (completed_count / max(1, total_symbols)) * 100.0
                            self.report_progress(progress, f"{completed_count}/{total_symbols}")
                        except Exception:
                            pass
                except asyncio.CancelledError:
                    # Also catch cancellations from rate limiter or queue ops
                    self.force_stop()
                    raise
                finally:
                    queue.task_done()

        # Initial progress signal
        try:
            self.report_progress(0.0, f"0/{total_symbols}")
        except Exception:
            pass

        # Enforce a conservative upper bound for concurrency
        effective_concurrency = min(max_concurrent, self._max_safe_concurrency)
        self.workers.clear()
        self.workers.extend(
            asyncio.create_task(worker(i)) for i in range(min(effective_concurrency, total_symbols))
        )

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

        return {"filtered_ohlcv_bundle": filtered_bundle}

