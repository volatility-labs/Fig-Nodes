import asyncio
import logging
import math
from datetime import datetime
from typing import Any

import pytz

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
from services.indicator_calculators.vbp_calculator import calculate_vbp
from services.polygon_service import fetch_bars
from services.rate_limiter import RateLimiter

logger = logging.getLogger(__name__)


class VBPLevelFilter(BaseIndicatorFilter):
    """
    Filters assets based on Volume Profile (VBP) levels and distance from support/resistance.

    Calculates significant price levels based on volume distribution and checks if current price
    is within specified distance from support (below) and resistance (above).

    Can either use weekly bars (fetched directly from Polygon) or aggregate daily bars to weekly.

    Parameters:
    - bins: Number of bins for volume histogram (default: 50)
    - lookback_years: Number of years to look back for volume data (default: 2)
    - num_levels: Number of significant volume levels to identify (default: 5)
    - max_distance_to_support: Maximum % distance to nearest support level (default: 5.0)
    - min_distance_to_resistance: Minimum % distance to nearest resistance level (default: 5.0)
    - use_weekly: If True, fetch weekly bars from Polygon (default: False, uses daily bars from upstream)
    """

    inputs = {
        "ohlcv_bundle": get_type("OHLCVBundle"),
    }

    default_params = {
        "bins": 50,
        "lookback_years": 2,
        "lookback_years_2": None,
        "num_levels": 5,
        "max_distance_to_support": 5.0,
        "min_distance_to_resistance": 5.0,
        "use_weekly": False,
        "max_concurrent": 10,
        "rate_limit_per_second": 95,
        "use_dollar_weighted": False,
        "use_close_only": False,
    }

    params_meta = [
        {
            "name": "bins",
            "type": "number",
            "default": 50,
            "min": 10,
            "max": 200,
            "step": 5,
            "label": "Number of Bins",
            "description": "Number of bins for volume histogram. More bins = finer granularity",
        },
        {
            "name": "lookback_years",
            "type": "number",
            "default": 2,
            "min": 1,
            "max": 10,
            "step": 1,
            "label": "Lookback Period (Years)",
            "description": "Number of years to look back for volume data",
        },
        {
            "name": "lookback_years_2",
            "type": "number",
            "default": None,
            "min": 1,
            "max": 10,
            "step": 1,
            "label": "Second Lookback Period (Years)",
            "description": "Optional second lookback period. If set, combines levels from both periods",
        },
        {
            "name": "num_levels",
            "type": "number",
            "default": 5,
            "min": 1,
            "max": 20,
            "step": 1,
            "label": "Number of Levels",
            "description": "Number of significant volume levels to identify",
        },
        {
            "name": "max_distance_to_support",
            "type": "number",
            "default": 5.0,
            "min": 0.0,
            "max": 50.0,
            "step": 0.1,
            "precision": 2,
            "label": "Max Distance to Support (%)",
            "description": "Maximum % distance to nearest support level",
        },
        {
            "name": "min_distance_to_resistance",
            "type": "number",
            "default": 5.0,
            "min": 0.0,
            "max": 50.0,
            "step": 0.1,
            "precision": 2,
            "label": "Min Distance to Resistance (%)",
            "description": "Minimum % distance to nearest resistance level",
        },
        {
            "name": "use_weekly",
            "type": "combo",
            "default": False,
            "options": [True, False],
            "label": "Use Weekly Bars",
            "description": "If true, fetch weekly bars from Polygon. If false, aggregate daily bars to weekly",
        },
        {
            "name": "use_dollar_weighted",
            "type": "combo",
            "default": False,
            "options": [True, False],
            "label": "Use Dollar Weighted Volume",
            "description": "If true, use dollar-weighted volume (volume * close) instead of raw volume",
        },
        {
            "name": "use_close_only",
            "type": "combo",
            "default": False,
            "options": [True, False],
            "label": "Use Close Price Only",
            "description": "If true, bin by close price only. If false, use HLC average (typical price)",
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
        bins_raw = self.params.get("bins", 50)
        lookback_years_raw = self.params.get("lookback_years", 2)
        num_levels_raw = self.params.get("num_levels", 5)

        if not isinstance(bins_raw, int | float) or bins_raw < 10:
            raise ValueError("Number of bins must be at least 10")
        if not isinstance(lookback_years_raw, int | float) or lookback_years_raw < 1:
            raise ValueError("Lookback period must be at least 1 year")
        if not isinstance(num_levels_raw, int | float) or num_levels_raw < 1:
            raise ValueError("Number of levels must be at least 1")

    async def _fetch_weekly_bars(self, symbol: AssetSymbol, api_key: str) -> list[OHLCVBar]:
        """Fetch weekly bars directly from Polygon API."""
        lookback_years_raw = self.params.get("lookback_years", 2)
        if not isinstance(lookback_years_raw, int | float):
            raise ValueError(f"lookback_years must be a number, got {type(lookback_years_raw)}")

        lookback_years = int(lookback_years_raw)
        lookback_days = lookback_years * 365

        fetch_params = {
            "multiplier": 1,
            "timespan": "week",
            "lookback_period": f"{lookback_days} days",
            "adjusted": True,
            "sort": "asc",
            "limit": 50000,
        }

        bars = await fetch_bars(symbol, api_key, fetch_params)
        return bars

    def _aggregate_to_weekly(self, ohlcv_data: list[OHLCVBar]) -> list[OHLCVBar]:
        """Aggregate daily bars to weekly bars."""
        if not ohlcv_data:
            return []

        # Group by week
        weekly_groups: dict[str, list[OHLCVBar]] = {}

        for bar in ohlcv_data:
            dt = datetime.fromtimestamp(bar["timestamp"] / 1000, tz=pytz.UTC)
            # Create a unique week identifier: year-week
            year = dt.isocalendar()[0]
            week = dt.isocalendar()[1]
            week_key = f"{year}-W{week:02d}"

            if week_key not in weekly_groups:
                weekly_groups[week_key] = []
            weekly_groups[week_key].append(bar)

        weekly_bars: list[OHLCVBar] = []
        for week_key in sorted(weekly_groups.keys()):
            group = weekly_groups[week_key]
            if not group:
                continue

            weekly_bar: OHLCVBar = {
                "timestamp": group[0]["timestamp"],
                "open": group[0]["open"],
                "high": max(bar["high"] for bar in group),
                "low": min(bar["low"] for bar in group),
                "close": group[-1]["close"],
                "volume": sum(bar.get("volume", 0.0) or 0.0 for bar in group),
            }
            weekly_bars.append(weekly_bar)

        return weekly_bars

    def _find_significant_levels(
        self, histogram: list[dict[str, Any]], num_levels: int
    ) -> list[dict[str, Any]]:
        """Find the most significant volume levels from histogram."""
        if not histogram:
            return []

        # Sort by volume descending
        def volume_key(x: dict[str, Any]) -> float:
            vol = x.get("volume", 0.0)
            return float(vol) if isinstance(vol, int | float) else 0.0

        sorted_bins = sorted(histogram, key=volume_key, reverse=True)

        # Take top num_levels
        return sorted_bins[:num_levels]

    def _calculate_indicator(self, ohlcv_data: list[OHLCVBar]) -> IndicatorResult:
        """Calculate VBP levels and return IndicatorResult. Supports two lookback periods."""
        if not ohlcv_data:
            return IndicatorResult(
                indicator_type=IndicatorType.VBP,
                timestamp=0,
                values=IndicatorValue(lines={}),
                params=self.params,
                error="No OHLCV data",
            )

        # Get lookback periods
        lookback_years_1_raw = self.params.get("lookback_years", 2)
        lookback_years_2_raw = self.params.get("lookback_years_2")

        if not isinstance(lookback_years_1_raw, int | float):
            raise ValueError(f"lookback_years must be a number, got {type(lookback_years_1_raw)}")

        lookback_years_1 = int(lookback_years_1_raw)

        # Calculate VBP levels for first period
        all_levels: list[dict[str, Any]] = []

        cutoff_timestamp_1 = ohlcv_data[-1]["timestamp"] - (
            lookback_years_1 * 365 * 24 * 60 * 60 * 1000
        )
        filtered_data_1 = [bar for bar in ohlcv_data if bar["timestamp"] >= cutoff_timestamp_1]

        if len(filtered_data_1) < 10:
            return IndicatorResult(
                indicator_type=IndicatorType.VBP,
                timestamp=ohlcv_data[-1]["timestamp"],
                values=IndicatorValue(lines={}),
                params=self.params,
                error=f"Insufficient data for period 1: need at least 10 bars, got {len(filtered_data_1)}",
            )

        # Aggregate to weekly if needed
        if not self.params.get("use_weekly", False):
            filtered_data_1 = self._aggregate_to_weekly(filtered_data_1)

        if len(filtered_data_1) < 10:
            return IndicatorResult(
                indicator_type=IndicatorType.VBP,
                timestamp=ohlcv_data[-1]["timestamp"],
                values=IndicatorValue(lines={}),
                params=self.params,
                error=f"Insufficient data after aggregation (period 1): need at least 10 bars, got {len(filtered_data_1)}",
            )

        # Use the existing calculate_vbp function
        bins_raw = self.params.get("bins", 50)
        if not isinstance(bins_raw, (int | float)):
            raise ValueError(f"bins must be a number, got {type(bins_raw)}")
        bins = int(bins_raw)

        use_dollar_weighted_raw = self.params.get("use_dollar_weighted", False)
        use_close_only_raw = self.params.get("use_close_only", False)
        use_dollar_weighted = (
            bool(use_dollar_weighted_raw) if use_dollar_weighted_raw is not None else False
        )
        use_close_only = bool(use_close_only_raw) if use_close_only_raw is not None else False

        vbp_result_1 = calculate_vbp(filtered_data_1, bins, use_dollar_weighted, use_close_only)

        if vbp_result_1.get("pointOfControl") is not None:
            # Extract significant levels from histogram
            num_levels_raw = self.params.get("num_levels", 5)
            if not isinstance(num_levels_raw, int | float):
                raise ValueError(f"num_levels must be a number, got {type(num_levels_raw)}")
            num_levels_1 = int(num_levels_raw)

            significant_levels_1 = self._find_significant_levels(
                vbp_result_1["histogram"], num_levels_1
            )
            all_levels.extend(significant_levels_1)

        # Calculate VBP levels for second period if specified
        if lookback_years_2_raw is not None:
            if not isinstance(lookback_years_2_raw, (int | float)):
                raise ValueError(
                    f"lookback_years_2 must be a number, got {type(lookback_years_2_raw)}"
                )

            lookback_years_2 = int(lookback_years_2_raw)
            cutoff_timestamp_2 = ohlcv_data[-1]["timestamp"] - (
                lookback_years_2 * 365 * 24 * 60 * 60 * 1000
            )
            filtered_data_2 = [bar for bar in ohlcv_data if bar["timestamp"] >= cutoff_timestamp_2]

            if len(filtered_data_2) >= 10:
                # Aggregate to weekly if needed
                if not self.params.get("use_weekly", False):
                    filtered_data_2 = self._aggregate_to_weekly(filtered_data_2)

                if len(filtered_data_2) >= 10:
                    vbp_result_2 = calculate_vbp(
                        filtered_data_2, bins, use_dollar_weighted, use_close_only
                    )

                    if vbp_result_2.get("pointOfControl") is not None:
                        # Extract significant levels from histogram
                        num_levels_raw = self.params.get("num_levels", 5)
                        if not isinstance(num_levels_raw, (int | float)):
                            raise ValueError(
                                f"num_levels must be a number, got {type(num_levels_raw)}"
                            )
                        num_levels_2 = int(num_levels_raw)

                        significant_levels_2 = self._find_significant_levels(
                            vbp_result_2["histogram"], num_levels_2
                        )
                        all_levels.extend(significant_levels_2)

        if not all_levels:
            return IndicatorResult(
                indicator_type=IndicatorType.VBP,
                timestamp=ohlcv_data[-1]["timestamp"],
                values=IndicatorValue(lines={}),
                params=self.params,
                error="No valid levels found",
            )

        # Get current price
        current_price = ohlcv_data[-1]["close"]

        # Combine levels and sort by volume
        def volume_sort_key(x: dict[str, Any]) -> float:
            vol = x.get("volume", 0.0)
            return float(vol) if isinstance(vol, (int | float)) else 0.0

        all_levels.sort(key=volume_sort_key, reverse=True)

        # Take top num_levels per period (or combined if two periods)
        num_levels_raw = self.params.get("num_levels", 5)
        if not isinstance(num_levels_raw, (int | float)):
            raise ValueError(f"num_levels must be a number, got {type(num_levels_raw)}")
        num_levels = int(num_levels_raw)

        if lookback_years_2_raw is not None:
            # If two periods, take top num_levels from combined list
            combined_levels: list[dict[str, Any]] = all_levels[: num_levels * 2]
        else:
            combined_levels: list[dict[str, Any]] = all_levels[:num_levels]

        # Remove duplicates based on price (within small tolerance)
        unique_levels: list[dict[str, Any]] = []
        seen_prices: set[float] = set()
        for level in combined_levels:
            price_level = level.get("priceLevel", 0.0)
            if not isinstance(price_level, (int | float)):
                continue
            price_rounded = round(float(price_level), 2)
            if price_rounded not in seen_prices:
                unique_levels.append(level)
                seen_prices.add(price_rounded)

        # Calculate support/resistance
        def get_price_level(level: dict[str, Any]) -> float:
            pl = level.get("priceLevel", 0.0)
            return float(pl) if isinstance(pl, (int | float)) else 0.0

        support_levels = [
            level for level in unique_levels if get_price_level(level) < current_price
        ]
        resistance_levels = [
            level for level in unique_levels if get_price_level(level) > current_price
        ]

        if support_levels:
            closest_support = max(support_levels, key=get_price_level)
            closest_support_price = get_price_level(closest_support)
        else:
            # No support found, use lowest level
            if unique_levels:
                closest_support_price = min(get_price_level(level) for level in unique_levels)
            else:
                closest_support_price = current_price

        if resistance_levels:
            closest_resistance = min(resistance_levels, key=get_price_level)
            closest_resistance_price = get_price_level(closest_resistance)
        else:
            # No resistance found, use highest level
            if unique_levels:
                closest_resistance_price = max(get_price_level(level) for level in unique_levels)
            else:
                closest_resistance_price = current_price

        has_resistance_above = len(resistance_levels) > 0

        distance_to_support = (
            abs(current_price - closest_support_price) / current_price * 100
            if current_price > 0
            else 0
        )

        if has_resistance_above:
            distance_to_resistance = (
                abs(closest_resistance_price - current_price) / current_price * 100
                if current_price > 0
                else 0
            )
        else:
            distance_to_resistance = float("inf")

        logger.debug(
            f"VBP calculation: current_price={current_price:.2f}, closest_support={closest_support_price:.2f}, "
            f"closest_resistance={closest_resistance_price:.2f}, distance_to_support={distance_to_support:.2f}%, "
            f"distance_to_resistance={distance_to_resistance:.2f}%, num_levels={len(unique_levels)}, "
            f"has_resistance_above={has_resistance_above}"
        )

        return IndicatorResult(
            indicator_type=IndicatorType.VBP,
            timestamp=ohlcv_data[-1]["timestamp"],
            values=IndicatorValue(
                lines={
                    "current_price": current_price,
                    "closest_support": closest_support_price,
                    "closest_resistance": closest_resistance_price,
                    "distance_to_support": distance_to_support,
                    "distance_to_resistance": distance_to_resistance,
                    "num_levels": len(unique_levels),
                    "has_resistance_above": has_resistance_above,
                }
            ),
            params=self.params,
        )

    def _should_pass_filter(self, indicator_result: IndicatorResult) -> bool:
        """Pass filter if distance to support and resistance meet criteria."""
        if indicator_result.error:
            logger.debug(f"VBP filter FAILED: {indicator_result.error}")
            return False

        lines = indicator_result.values.lines

        distance_to_support_raw = lines.get("distance_to_support", 0)
        distance_to_resistance_raw = lines.get("distance_to_resistance", 0)
        has_resistance_above = lines.get("has_resistance_above", True)

        if not math.isfinite(distance_to_support_raw):
            logger.debug("VBP filter FAILED: distance_to_support is not finite")
            return False

        distance_to_support = float(distance_to_support_raw)

        max_distance_support_raw = self.params.get("max_distance_to_support", 5.0)
        min_distance_resistance_raw = self.params.get("min_distance_to_resistance", 5.0)

        if not isinstance(max_distance_support_raw, (int | float)):
            raise ValueError(
                f"max_distance_to_support must be a number, got {type(max_distance_support_raw)}"
            )
        if not isinstance(min_distance_resistance_raw, (int | float)):
            raise ValueError(
                f"min_distance_to_resistance must be a number, got {type(min_distance_resistance_raw)}"
            )

        max_distance_support = float(max_distance_support_raw)
        min_distance_resistance = float(min_distance_resistance_raw)

        # Check if within max distance to support
        if distance_to_support > max_distance_support:
            logger.debug(
                f"VBP filter FAILED: distance_to_support={distance_to_support:.2f}% > max={max_distance_support:.2f}%"
            )
            return False

        # If no resistance levels above, automatically pass (price is above all levels)
        if not has_resistance_above:
            logger.debug("VBP filter PASSED: No resistance levels above (above all levels)")
            return True

        # Check if at least min distance to resistance (only if resistance exists)
        if not math.isfinite(distance_to_resistance_raw):
            logger.debug("VBP filter FAILED: distance_to_resistance is not finite")
            return False

        distance_to_resistance = float(distance_to_resistance_raw)

        if distance_to_resistance < min_distance_resistance:
            logger.debug(
                f"VBP filter FAILED: distance_to_resistance={distance_to_resistance:.2f}% < min={min_distance_resistance:.2f}%"
            )
            return False

        logger.debug(
            f"VBP filter PASSED: distance_to_support={distance_to_support:.2f}% <= max={max_distance_support:.2f}%, "
            f"distance_to_resistance={distance_to_resistance:.2f}% >= min={min_distance_resistance:.2f}%"
        )
        return True

    async def _execute_impl(self, inputs: dict[str, Any]) -> NodeOutputs:
        """Override to handle weekly bar fetching when use_weekly=True."""
        ohlcv_bundle: dict[AssetSymbol, list[OHLCVBar]] = inputs.get("ohlcv_bundle", {})

        if not ohlcv_bundle:
            return {"filtered_ohlcv_bundle": {}}

        # If use_weekly is True, fetch weekly bars from Polygon for each symbol
        if self.params.get("use_weekly", False):
            api_key = APIKeyVault().get("POLYGON_API_KEY")
            if not api_key:
                raise ValueError("Polygon API key not found in vault")

            max_concurrent_raw = self.params.get("max_concurrent", 10)
            if not isinstance(max_concurrent_raw, int):
                raise ValueError(f"max_concurrent must be an int, got {type(max_concurrent_raw)}")
            max_concurrent: int = max_concurrent_raw

            rate_limit_raw = self.params.get("rate_limit_per_second", 95)
            if not isinstance(rate_limit_raw, int):
                raise ValueError(
                    f"rate_limit_per_second must be an int, got {type(rate_limit_raw)}"
                )
            rate_limit: int = rate_limit_raw

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

                            if self._is_stopped:
                                logger.debug(f"Worker {worker_id} stopped after rate limiting")
                                break

                            # Report progress
                            try:
                                progress_pre = (
                                    (completed_count / total_symbols) * 100
                                    if total_symbols
                                    else 0.0
                                )
                                progress_text_pre = f"{completed_count}/{total_symbols}"
                                self.report_progress(progress_pre, progress_text_pre)
                            except Exception:
                                logger.debug("Progress pre-update failed; continuing")

                            # Fetch weekly bars
                            try:
                                weekly_bars = await self._fetch_weekly_bars(symbol, api_key)
                                if weekly_bars:
                                    updated_data = weekly_bars
                                else:
                                    updated_data = ohlcv_data

                                # Calculate indicator
                                indicator_result = self._calculate_indicator(updated_data)

                                if self._should_pass_filter(indicator_result):
                                    filtered_bundle[symbol] = updated_data

                                completed_count += 1
                                progress = (completed_count / total_symbols) * 100
                                progress_text = f"{completed_count}/{total_symbols}"
                                self.report_progress(progress, progress_text)
                            except asyncio.CancelledError:
                                self.force_stop()
                                raise
                            except Exception as e:
                                logger.error(
                                    f"Error processing VBP for {symbol}: {str(e)}", exc_info=True
                                )
                        finally:
                            queue.task_done()
                    except asyncio.CancelledError:
                        self.force_stop()
                        raise

            # Enforce conservative concurrency
            effective_concurrency = min(max_concurrent, self._max_safe_concurrency)
            self.workers.clear()
            for i in range(min(effective_concurrency, total_symbols)):
                self.workers.append(asyncio.create_task(worker(i)))

            if self.workers:
                results = await asyncio.gather(*self.workers, return_exceptions=True)
                for res in results:
                    if isinstance(res, asyncio.CancelledError):
                        raise res
                    if isinstance(res, Exception):
                        logger.error(f"Worker task error: {res}", exc_info=True)

            return {"filtered_ohlcv_bundle": filtered_bundle}

        # Call parent's execute implementation when not fetching weekly bars
        return await super()._execute_impl({"ohlcv_bundle": ohlcv_bundle})
