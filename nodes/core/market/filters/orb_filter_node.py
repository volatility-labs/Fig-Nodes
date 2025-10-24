import asyncio
import logging
import math
import time
from datetime import datetime, timedelta
from typing import Any

import pandas as pd
import pytz

from core.api_key_vault import APIKeyVault
from core.types_registry import (
    AssetSymbol,
    IndicatorResult,
    IndicatorType,
    IndicatorValue,
    OHLCVBar,
    get_type,
)
from nodes.core.market.filters.base.base_indicator_filter_node import BaseIndicatorFilter
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

    def __init__(self, id: int, params: dict[str, Any] = None):
        super().__init__(id, params)
        self.workers: list[asyncio.Task] = []
        # Conservative cap to avoid event loop thrashing and ensure predictable batching in tests
        self._max_safe_concurrency = 5

    def validate_inputs(self, inputs: dict[str, Any]) -> bool:
        if "ohlcv_bundle" in inputs and isinstance(inputs["ohlcv_bundle"], dict):
            inputs["ohlcv_bundle"] = {
                k: v if v is not None else [] for k, v in inputs["ohlcv_bundle"].items()
            }
        return super().validate_inputs(inputs)

    def force_stop(self):
        if self._is_stopped:
            return
        self._is_stopped = True
        for w in self.workers:
            if not w.done():
                w.cancel()
        self.workers.clear()

    def _validate_indicator_params(self):
        if self.params["or_minutes"] <= 0:
            raise ValueError("Opening range minutes must be positive")
        if self.params["rel_vol_threshold"] < 0:
            raise ValueError("Relative volume threshold cannot be negative")
        if self.params["avg_period"] <= 0:
            raise ValueError("Average period must be positive")

    def _get_target_date_for_orb(self, symbol: AssetSymbol, today_date, df) -> datetime.date:
        """
        Determine the target date for ORB calculation based on asset class.

        For stocks: Use last trading day if today has no data
        For crypto: Use UTC midnight of prior day
        """
        if symbol.asset_class.name == "CRYPTO":
            # For crypto, use UTC midnight of prior day
            utc_now = datetime.now(pytz.timezone("UTC"))
            prior_day_utc = utc_now.date() - timedelta(days=1)
            return prior_day_utc
        else:
            # For stocks, check if today has data, otherwise use last trading day
            available_dates = sorted(df["date"].unique())
            if today_date in available_dates:
                return today_date
            else:
                # Use the most recent trading day
                return available_dates[-1] if available_dates else today_date

    async def _calculate_orb_indicator(self, symbol: AssetSymbol, api_key: str) -> IndicatorResult:
        avg_period = self.params["avg_period"]
        or_minutes = self.params["or_minutes"]

        # Fetch 1-min bars for last avg_period +1 days
        fetch_params = {
            "multiplier": 1,
            "timespan": "minute",
            "lookback_period": f"{int(avg_period) + 1} days",
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

        # Convert to df
        df = pd.DataFrame(bars)
        df["timestamp"] = (
            pd.to_datetime(df["timestamp"], unit="ms")
            .dt.tz_localize("UTC")
            .dt.tz_convert("US/Eastern")
        )

        # Group by date
        df["date"] = df["timestamp"].dt.date
        daily_groups = df.groupby("date")

        or_volumes = {}
        today_direction = None
        today_date = datetime.now(pytz.timezone("US/Eastern")).date()

        # Determine target date based on asset class
        target_date = self._get_target_date_for_orb(symbol, today_date, df)

        for date, group in daily_groups:
            # Determine opening range time based on asset class
            if symbol.asset_class.name == "CRYPTO":
                # For crypto, use UTC midnight (00:00:00) as opening range
                open_time = (
                    datetime.combine(date, datetime.strptime("00:00", "%H:%M").time())
                    .replace(tzinfo=pytz.timezone("UTC"))
                    .astimezone(pytz.timezone("US/Eastern"))
                )
            else:
                # For stocks, use 9:30 AM Eastern as opening range
                open_time = datetime.combine(
                    date, datetime.strptime("09:30", "%H:%M").time()
                ).replace(tzinfo=pytz.timezone("US/Eastern"))

            close_time = open_time + timedelta(minutes=or_minutes)

            or_bars = group[(group["timestamp"] >= open_time) & (group["timestamp"] < close_time)]

            if or_bars.empty:
                continue

            or_high = or_bars["high"].max()
            or_low = or_bars["low"].min()
            or_volume = or_bars["volume"].sum()
            or_open = or_bars.iloc[0]["open"]
            or_close = or_bars.iloc[-1]["close"]

            direction = (
                "bullish" if or_close > or_open else "bearish" if or_close < or_open else "doji"
            )

            or_volumes[date] = or_volume

            # Save direction for target date (today or last trading day)
            if date == target_date:
                today_direction = direction

        # Get sorted dates
        sorted_dates = sorted(or_volumes.keys())
        if len(sorted_dates) < 2:
            return IndicatorResult(
                indicator_type=IndicatorType.ORB,
                timestamp=0,
                values=IndicatorValue(),
                params=self.params,
                error="Insufficient days",
            )

        # Use target date for volume calculation
        target_volume_date = target_date if target_date in or_volumes else sorted_dates[-1]
        past_volumes = (
            [or_volumes[d] for d in sorted_dates[-avg_period - 1 : -1]]
            if len(sorted_dates) > avg_period
            else [or_volumes[d] for d in sorted_dates[:-1]]
        )

        if not past_volumes:
            avg_vol = 0
        else:
            avg_vol = sum(past_volumes) / len(past_volumes)

        current_vol = or_volumes.get(target_volume_date, 0)
        rel_vol = (current_vol / avg_vol * 100) if avg_vol > 0 else 0

        if today_direction is None:
            today_direction = "doji"

        values = IndicatorValue(lines={"rel_vol": rel_vol}, series=[{"direction": today_direction}])

        return IndicatorResult(
            indicator_type=IndicatorType.ORB,
            timestamp=int(df["timestamp"].iloc[-1].timestamp() * 1000),
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

        if rel_vol < self.params["rel_vol_threshold"]:
            return False

        param_dir = self.params["direction"]
        if param_dir == "both":
            return True
        return direction == param_dir

    async def _execute_impl(self, inputs: dict[str, Any]) -> dict[str, Any]:
        self.api_key = APIKeyVault().get("POLYGON_API_KEY")
        if not self.api_key:
            raise ValueError("Polygon API key not found in vault")

        ohlcv_bundle: dict[AssetSymbol, list[OHLCVBar]] = inputs.get("ohlcv_bundle", {})

        if not ohlcv_bundle:
            return {"filtered_ohlcv_bundle": {}}

        max_concurrent = self.params.get("max_concurrent", 10)
        rate_limit = self.params.get("rate_limit_per_second", 95)
        filtered_bundle = {}
        rate_limiter = RateLimiter(max_per_second=rate_limit)
        total_symbols = len(ohlcv_bundle)
        completed_count = 0

        # Use a bounded worker pool to avoid creating one task per symbol
        queue: asyncio.Queue = asyncio.Queue()
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
                                symbol, self.api_key
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
