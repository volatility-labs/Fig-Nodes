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
        "filter_above_orh": "No",  # Filter for price above Opening Range High
        "filter_below_orl": "No",  # Filter for price below Opening Range Low
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
        {"name": "filter_above_orh", "type": "combo", "default": "No", "options": ["No", "Yes"]},
        {"name": "filter_below_orl", "type": "combo", "default": "No", "options": ["No", "Yes"]},
    ]

    def __init__(
        self, id: int, params: dict[str, Any], graph_context: dict[str, Any] | None = None
    ):
        super().__init__(id, params, graph_context)
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

        if not isinstance(or_minutes, int | float) or or_minutes <= 0:
            raise ValueError("Opening range minutes must be positive")
        if not isinstance(rel_vol_threshold, int | float) or rel_vol_threshold < 0:
            raise ValueError("Relative volume threshold cannot be negative")
        if not isinstance(avg_period, int | float) or avg_period <= 0:
            raise ValueError("Average period must be positive")

    async def _calculate_orb_indicator(self, symbol: AssetSymbol, api_key: str) -> IndicatorResult:
        avg_period_raw = self.params["avg_period"]
        or_minutes_raw = self.params["or_minutes"]

        # Type guard: ensure avg_period is a number
        if not isinstance(avg_period_raw, int | float):
            raise ValueError(f"avg_period must be a number, got {type(avg_period_raw)}")

        avg_period = int(avg_period_raw)

        # Type guard: ensure or_minutes is a number
        if not isinstance(or_minutes_raw, int | float):
            raise ValueError(f"or_minutes must be a number, got {type(or_minutes_raw)}")

        or_minutes = int(or_minutes_raw)

        # Fetch 5-min bars for last avg_period +1 days
        fetch_params = {
            "multiplier": 5,
            "timespan": "minute",
            "lookback_period": f"{avg_period + 1} days",
            "adjusted": True,
            "sort": "asc",
            "limit": 50000,
        }

        logger.info("=" * 80)
        logger.info(f"ORB_FILTER: Starting bar fetch for {symbol.ticker} ({symbol.asset_class})")
        logger.info(f"ORB_FILTER: Fetch params: {fetch_params}")
        logger.info(f"ORB_FILTER: Request time: {datetime.now(pytz.timezone('US/Eastern'))}")
        logger.info("=" * 80)

        bars, _metadata = await fetch_bars(symbol, api_key, fetch_params)

        if not bars:
            logger.warning(f"ORB_FILTER: No bars returned for {symbol.ticker}")
            return IndicatorResult(
                indicator_type=IndicatorType.ORB,
                timestamp=0,
                values=IndicatorValue(),
                params=self.params,
                error="No bars fetched",
            )
        
        # Log bar details for delay analysis
        if bars:
            from services.time_utils import utc_timestamp_ms_to_et_datetime
            current_time_et = datetime.now(pytz.timezone("US/Eastern"))
            first_bar_time = utc_timestamp_ms_to_et_datetime(bars[0]["timestamp"])
            last_bar_time = utc_timestamp_ms_to_et_datetime(bars[-1]["timestamp"])
            time_diff = current_time_et - last_bar_time
            delay_minutes = time_diff.total_seconds() / 60
            
            logger.info("=" * 80)
            logger.info(f"ORB_FILTER: Bars received for {symbol.ticker}")
            logger.info(f"ORB_FILTER: Total bars: {len(bars)}")
            logger.info(f"ORB_FILTER: First bar timestamp (ET): {first_bar_time}")
            logger.info(f"ORB_FILTER: Last bar timestamp (ET): {last_bar_time}")
            logger.info(f"ORB_FILTER: Current time (ET): {current_time_et}")
            logger.info(f"ORB_FILTER: Delay from last bar: {delay_minutes:.2f} minutes")
            
            if delay_minutes < 5:
                logger.info(f"ORB_FILTER: ✅ Data appears REAL-TIME for {symbol.ticker}")
            elif delay_minutes < 15:
                logger.warning(f"ORB_FILTER: ⚠️ Data appears SLIGHTLY DELAYED for {symbol.ticker} ({delay_minutes:.2f} min)")
            else:
                logger.warning(f"ORB_FILTER: ⚠️ Data appears SIGNIFICANTLY DELAYED for {symbol.ticker} ({delay_minutes:.2f} min)")
            logger.info("=" * 80)

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
        or_high = result.get("or_high")
        or_low = result.get("or_low")

        # Type guard: ensure rel_vol is a number
        if not isinstance(rel_vol_raw, int | float):
            raise ValueError(f"rel_vol must be a number, got {type(rel_vol_raw)}")

        rel_vol = float(rel_vol_raw)

        # Get the latest timestamp from bars for the result
        latest_timestamp = bars[-1]["timestamp"] if bars else 0

        # Get current price from the latest bar
        current_price = bars[-1]["close"] if bars else None

        values = IndicatorValue(
            lines={"rel_vol": rel_vol, "or_high": or_high, "or_low": or_low, "current_price": current_price},
            series=[{"direction": direction}]
        )

        return IndicatorResult(
            indicator_type=IndicatorType.ORB,
            timestamp=latest_timestamp,
            values=values,
            params=self.params,
        )

    def _should_pass_filter(self, indicator_result: IndicatorResult) -> bool:
        if indicator_result.error:
            logger.debug(f"ORB_FILTER: Filter failed due to error: {indicator_result.error}")
            return False
        if not indicator_result.values.lines:
            logger.debug("ORB_FILTER: Filter failed - no lines data")
            return False
        if not indicator_result.values.series:
            logger.debug("ORB_FILTER: Filter failed - no series data")
            return False

        rel_vol = indicator_result.values.lines.get("rel_vol", 0)
        if math.isnan(rel_vol):
            logger.debug("ORB_FILTER: Filter failed - rel_vol is NaN")
            return False
        directions = [s["direction"] for s in indicator_result.values.series if "direction" in s]
        direction = directions[0] if directions else "doji"

        if direction == "doji":
            logger.debug("ORB_FILTER: Filter failed - direction is 'doji'")
            return False

        rel_vol_threshold = self.params.get("rel_vol_threshold", 0.0)
        if not isinstance(rel_vol_threshold, int | float):
            raise ValueError(f"rel_vol_threshold must be a number, got {type(rel_vol_threshold)}")

        if rel_vol < float(rel_vol_threshold):
            logger.debug(f"ORB_FILTER: Filter failed - rel_vol {rel_vol}% < threshold {rel_vol_threshold}%")
            return False

        param_dir = self.params["direction"]
        if param_dir == "both":
            return True
        if direction != param_dir:
            logger.debug(f"ORB_FILTER: Filter failed - direction {direction} != filter direction {param_dir}")
            return False
        return True

    def _should_pass_additional_filters(self, indicator_result: IndicatorResult) -> bool:
        """Check additional price-based filters (ORH/ORL)."""
        if not indicator_result.values.lines:
            return True  # If no lines data, skip additional filters
        
        current_price = indicator_result.values.lines.get("current_price")
        or_high = indicator_result.values.lines.get("or_high")
        or_low = indicator_result.values.lines.get("or_low")
        
        # Check filter_above_orh
        filter_above_orh = self.params.get("filter_above_orh", "No")
        if filter_above_orh == "Yes":
            if current_price is None or or_high is None:
                return False  # Can't filter if we don't have the data
            if not (current_price > or_high):
                return False  # Price must be above ORH
        
        # Check filter_below_orl
        filter_below_orl = self.params.get("filter_below_orl", "No")
        if filter_below_orl == "Yes":
            if current_price is None or or_low is None:
                return False  # Can't filter if we don't have the data
            if not (current_price < or_low):
                return False  # Price must be below ORL
        
        return True

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
        
        # Log input symbols for debugging - use print to ensure visibility
        input_symbols = [s.ticker for s in ohlcv_bundle.keys()]
        print(f"🔵 ORB_FILTER: Processing {total_symbols} symbols: {', '.join(sorted(input_symbols))}")
        logger.info(f"ORB_FILTER: Processing {total_symbols} symbols: {', '.join(sorted(input_symbols))}")
        
        # Check specifically for PDD
        pdd_in_bundle = any(s.ticker.upper() == "PDD" for s in ohlcv_bundle.keys())
        if not pdd_in_bundle:
            print(f"⚠️ ORB_FILTER: PDD is NOT in the input bundle!")
            logger.warning(f"ORB_FILTER: PDD is NOT in the input bundle!")
        else:
            print(f"✅ ORB_FILTER: PDD IS in the input bundle")
            logger.info(f"ORB_FILTER: PDD IS in the input bundle")

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
                            
                            # Debug logging for filter decisions
                            passes_main = self._should_pass_filter(indicator_result)
                            passes_additional = self._should_pass_additional_filters(indicator_result)
                            
                            # Special logging for PDD
                            is_pdd = symbol.ticker.upper() == "PDD"
                            
                            if not passes_main:
                                rel_vol = indicator_result.values.lines.get("rel_vol", 0) if indicator_result.values.lines else None
                                direction = indicator_result.values.series[0].get("direction", "unknown") if indicator_result.values.series else "unknown"
                                rel_vol_threshold = self.params.get("rel_vol_threshold", 100.0)
                                param_dir = self.params.get("direction", "both")
                                msg = f"❌ ORB_FILTER: {symbol.ticker} FAILED main filter - rel_vol: {rel_vol}% (threshold: {rel_vol_threshold}%), direction: {direction} (filter: {param_dir}), error: {indicator_result.error}"
                                if is_pdd:
                                    print(f"🔴 {msg}")
                                logger.info(msg)
                            
                            if passes_main and not passes_additional:
                                current_price = indicator_result.values.lines.get("current_price") if indicator_result.values.lines else None
                                or_high = indicator_result.values.lines.get("or_high") if indicator_result.values.lines else None
                                or_low = indicator_result.values.lines.get("or_low") if indicator_result.values.lines else None
                                filter_above_orh = self.params.get("filter_above_orh", "No")
                                filter_below_orl = self.params.get("filter_below_orl", "No")
                                msg = f"⚠️ ORB_FILTER: {symbol.ticker} PASSED main filter but FAILED additional filters - price: ${current_price}, ORH: ${or_high}, ORL: ${or_low}, filter_above_orh: {filter_above_orh}, filter_below_orl: {filter_below_orl}"
                                if is_pdd:
                                    print(f"🔴 {msg}")
                                logger.info(msg)
                            
                            if passes_main and passes_additional:
                                msg = f"✅ ORB_FILTER: {symbol.ticker} PASSED all filters - INCLUDED in output"
                                if is_pdd:
                                    print(f"🟢 {msg}")
                                logger.info(msg)
                            
                            if passes_main and passes_additional:
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

        # Final summary log
        passed_symbols = sorted([s.ticker for s in filtered_bundle.keys()])
        failed_symbols = sorted([s.ticker for s in ohlcv_bundle.keys() if s not in filtered_bundle])
        
        print(f"\n{'='*80}")
        print(f"🔵 ORB_FILTER SUMMARY:")
        print(f"   Total input symbols: {total_symbols}")
        print(f"   Symbols that PASSED: {len(passed_symbols)}")
        print(f"   Symbols that FAILED: {len(failed_symbols)}")
        print(f"\n   ✅ PASSED ({len(passed_symbols)}): {', '.join(passed_symbols) if passed_symbols else 'NONE'}")
        print(f"\n   ❌ FAILED ({len(failed_symbols)}): {', '.join(failed_symbols) if failed_symbols else 'NONE'}")
        
        # Special check for PDD
        pdd_passed = any(s.ticker.upper() == "PDD" for s in filtered_bundle.keys())
        pdd_failed = any(s.ticker.upper() == "PDD" for s in failed_symbols)
        if pdd_passed:
            print(f"\n   🟢 PDD STATUS: PASSED - Included in output")
        elif pdd_failed:
            print(f"\n   🔴 PDD STATUS: FAILED - Filtered out (check logs above for reason)")
        else:
            print(f"\n   ⚠️ PDD STATUS: NOT FOUND in input bundle")
        print(f"{'='*80}\n")
        
        logger.info(f"ORB_FILTER SUMMARY: {len(passed_symbols)} passed, {len(failed_symbols)} failed out of {total_symbols} total")
        
        return {"filtered_ohlcv_bundle": filtered_bundle}
