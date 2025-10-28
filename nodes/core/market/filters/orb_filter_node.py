import asyncio
import logging
import math
from datetime import date, datetime, timedelta
from typing import Any

import pandas as pd
import pytz

from core.api_key_vault import APIKeyVault
from core.types_registry import (
    AssetClass,
    AssetSymbol,
    IndicatorResult,
    IndicatorType,
    IndicatorValue,
    NodeOutputs,
    OHLCVBar,
    get_type,
)
from nodes.core.market.filters.base.base_indicator_filter_node import BaseIndicatorFilter
from services.indicator_calculators.orb_calculator import calculate_orb
from services.polygon_service import fetch_bars
from services.rate_limiter import RateLimiter

logger = logging.getLogger(__name__)


class OrbFilter(BaseIndicatorFilter):
    """
    Filters assets based on Opening Range Breakout (ORB) criteria including relative volume and direction.
    """

    inputs = {
        "ohlcv_bundle": get_type("OHLCVBundle"),
    }

    default_params = {
        "or_minutes": 5,
        "rel_vol_threshold": 100.0,
        "direction": "both",  # 'bullish', 'bearish', 'both'
        "avg_period": 14,
        "max_concurrent": 10,  # For concurrency limiting
        "rate_limit_per_second": 95,  # Stay under Polygon's recommended 100/sec
    }

    params_meta = [
        {"name": "or_minutes", "type": "number", "default": 5, "min": 1, "step": 1},
        {"name": "rel_vol_threshold", "type": "number", "default": 100.0, "min": 0.0, "step": 1.0},
        {
            "name": "direction",
            "type": "combo",
            "default": "both",
            "options": ["bullish", "bearish", "both"],
        },
        {"name": "avg_period", "type": "number", "default": 14, "min": 1, "step": 1},
    ]

    def __init__(self, id: int, params: dict[str, Any]):
        super().__init__(id, params)
        self.workers: list[asyncio.Task[NodeOutputs]] = []
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
        or_minutes = self.params["or_minutes"]
        rel_vol_threshold = self.params["rel_vol_threshold"]
        avg_period = self.params["avg_period"]

        if not isinstance(or_minutes, (int, float)) or or_minutes <= 0:
            raise ValueError("Opening range minutes must be positive")
        if not isinstance(rel_vol_threshold, (int, float)) or rel_vol_threshold < 0:
            raise ValueError("Relative volume threshold cannot be negative")
        if not isinstance(avg_period, (int, float)) or avg_period <= 0:
            raise ValueError("Average period must be positive")

    async def _calculate_orb_indicator(self, symbol: AssetSymbol, api_key: str) -> IndicatorResult:
        avg_period_raw = self.params["avg_period"]
        or_minutes_raw = self.params["or_minutes"]

        # Type guard: ensure avg_period is a number
        if not isinstance(avg_period_raw, (int, float)):
            raise ValueError(f"avg_period must be a number, got {type(avg_period_raw)}")

        avg_period = int(avg_period_raw)

        # Type guard: ensure or_minutes is a number
        if not isinstance(or_minutes_raw, (int, float)):
            raise ValueError(f"or_minutes must be a number, got {type(or_minutes_raw)}")

        or_minutes = int(or_minutes_raw)

        # Fetch 1-min bars for last avg_period +1 days
        fetch_params = {
            "multiplier": 1,
            "timespan": "minute",
            "lookback_period": f"{avg_period + 1} days",
            "adjusted": True,
            "sort": "asc",
            "limit": 50000,
        }

        bars = await fetch_bars(symbol, api_key, fetch_params)

        if not bars:
            return IndicatorResult(
                indicator_type=IndicatorType.ORB,
                timestamp=0,
                values=IndicatorValue(),
                params=self.params,
                error="No bars fetched",
            )

        # Use the calculator to calculate ORB indicators
        result = calculate_orb(bars, symbol, or_minutes, avg_period)

        if result.get("error"):
            return IndicatorResult(
                indicator_type=IndicatorType.ORB,
                timestamp=0,
                values=IndicatorValue(),
                params=self.params,
                error=result["error"],
            )

        rel_vol_raw = result.get("rel_vol")
        direction = result.get("direction", "doji")

        # Type guard: ensure rel_vol is a number
        if not isinstance(rel_vol_raw, (int, float)):
            raise ValueError(f"rel_vol must be a number, got {type(rel_vol_raw)}")

        rel_vol = float(rel_vol_raw)

        # Get the latest timestamp from bars for the result
        latest_timestamp = bars[-1]["timestamp"] if bars else 0

        values = IndicatorValue(lines={"rel_vol": rel_vol}, series=[{"direction": direction}])

        return IndicatorResult(
            indicator_type=IndicatorType.ORB,
            timestamp=latest_timestamp,
            values=values,
            params=self.params,
        )

    def _should_pass_filter(self, indicator_result: IndicatorResult) -> bool:
        if (
            indicator_result.error
            or not indicator_result.values.lines
            or not indicator_result.values.series
        ):
            return False

        rel_vol = indicator_result.values.lines.get("rel_vol", 0)
        if math.isnan(rel_vol):
            return False
        directions = [s["direction"] for s in indicator_result.values.series if "direction" in s]
        direction = directions[0] if directions else "doji"

        if direction == "doji":
            return False

        rel_vol_threshold = self.params.get("rel_vol_threshold", 0.0)
        if not isinstance(rel_vol_threshold, (int, float)):
            raise ValueError(f"rel_vol_threshold must be a number, got {type(rel_vol_threshold)}")

        if rel_vol < float(rel_vol_threshold):
            return False

        param_dir = self.params["direction"]
        if param_dir == "both":
            return True
        return direction == param_dir

    def _get_target_date_for_orb(
        self, symbol: AssetSymbol, today_date: date, df: pd.DataFrame
    ) -> date:
        if symbol.asset_class == AssetClass.CRYPTO:
            utc_now = datetime.now(pytz.timezone("UTC"))
            return utc_now.date() - timedelta(days=1)
        sorted_dates = sorted(set(df["date"]))
        if today_date in sorted_dates:
            return today_date
        else:
            return max(sorted_dates) if sorted_dates else today_date

    async def _execute_impl(self, inputs: dict[str, Any]) -> NodeOutputs:
        self.api_key = APIKeyVault().get("POLYGON_API_KEY")
        if not self.api_key or not self.api_key.strip():
            raise ValueError("Polygon API key not found in vault")

        ohlcv_bundle: dict[AssetSymbol, list[OHLCVBar]] = inputs.get("ohlcv_bundle", {})

        if not ohlcv_bundle:
            return {"filtered_ohlcv_bundle": {}}

        max_concurrent_raw = self.params.get("max_concurrent", 10)
        if not isinstance(max_concurrent_raw, int):
            raise ValueError(f"max_concurrent must be an int, got {type(max_concurrent_raw)}")
        max_concurrent: int = max_concurrent_raw

        rate_limit_raw = self.params.get("rate_limit_per_second", 95)
        if not isinstance(rate_limit_raw, int):
            raise ValueError(f"rate_limit_per_second must be an int, got {type(rate_limit_raw)}")
        rate_limit: int = rate_limit_raw

        filtered_bundle = {}
        rate_limiter = RateLimiter(max_per_second=rate_limit)
        total_symbols = len(ohlcv_bundle)
        completed_count = 0

        # Use a bounded worker pool to avoid creating one task per symbol
        queue: asyncio.Queue[tuple[AssetSymbol, list[OHLCVBar]]] = asyncio.Queue()
        for symbol, ohlcv_data in ohlcv_bundle.items():
            if ohlcv_data:  # Only process symbols with data
                queue.put_nowait((symbol, ohlcv_data))

        async def worker(worker_id: int):
            nonlocal completed_count
            while True:
                # Check for cancellation before processing next symbol
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

                        # Calculate ORB indicator with error handling
                        try:
                            indicator_result = await self._calculate_orb_indicator(
                                symbol, self.api_key or ""
                            )
                            if self._should_pass_filter(indicator_result):
                                filtered_bundle[symbol] = ohlcv_data

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
                            logger.error(
                                f"Error calculating ORB for {symbol}: {str(e)}", exc_info=True
                            )
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

        return {"filtered_ohlcv_bundle": filtered_bundle}
