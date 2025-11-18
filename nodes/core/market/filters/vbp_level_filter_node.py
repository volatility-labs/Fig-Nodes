import asyncio
import logging
import math
from datetime import datetime, timedelta
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

# Constants
MIN_BARS_REQUIRED = 10
DAYS_PER_YEAR = 365.25
PRICE_ROUNDING_PRECISION = 2


class VBPLevelFilter(BaseIndicatorFilter):
    """
    Filters assets based on Volume Profile (VBP) levels and distance from support/resistance.

    Calculates significant price levels based on volume distribution and checks if current price
    is within specified distance from support (below) and resistance (above).

    Can either use weekly bars (fetched directly from Polygon) or aggregate daily bars to weekly.
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

    # Type conversion helpers
    def _get_int_param(self, key: str, default: int) -> int:
        """Get and validate an integer parameter."""
        raw = self.params.get(key, default)
        if not isinstance(raw, int | float):
            raise ValueError(f"{key} must be a number, got {type(raw)}")
        return int(raw)

    def _get_float_param(self, key: str, default: float) -> float:
        """Get and validate a float parameter."""
        raw = self.params.get(key, default)
        if not isinstance(raw, int | float):
            raise ValueError(f"{key} must be a number, got {type(raw)}")
        return float(raw)

    def _get_bool_param(self, key: str, default: bool) -> bool:
        """Get and validate a boolean parameter."""
        raw = self.params.get(key, default)
        return bool(raw) if raw is not None else default

    def _get_optional_int_param(self, key: str) -> int | None:
        """Get and validate an optional integer parameter."""
        raw = self.params.get(key)
        if raw is None:
            return None
        if not isinstance(raw, int | float):
            raise ValueError(f"{key} must be a number or None, got {type(raw)}")
        return int(raw)

    # Data fetching and aggregation
    async def _fetch_weekly_bars(self, symbol: AssetSymbol, api_key: str) -> list[OHLCVBar]:
        """Fetch weekly bars directly from Polygon API."""
        lookback_years = self._get_int_param("lookback_years", 2)
        lookback_days = lookback_years * 365

        fetch_params = {
            "multiplier": 1,
            "timespan": "week",
            "lookback_period": f"{lookback_days} days",
            "adjusted": True,
            "sort": "asc",
            "limit": 50000,
        }

        bars, _metadata = await fetch_bars(symbol, api_key, fetch_params)
        return bars

    def _aggregate_to_weekly(self, ohlcv_data: list[OHLCVBar]) -> list[OHLCVBar]:
        """Aggregate daily bars to weekly bars."""
        if not ohlcv_data:
            return []

        weekly_groups: dict[str, list[OHLCVBar]] = {}

        for bar in ohlcv_data:
            dt = datetime.fromtimestamp(bar["timestamp"] / 1000, tz=pytz.UTC)
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

    def _filter_by_lookback_period(
        self, ohlcv_data: list[OHLCVBar], lookback_years: int
    ) -> list[OHLCVBar]:
        """Filter bars by lookback period using calendar-aware calculation."""
        if not ohlcv_data:
            return []

        last_ts = ohlcv_data[-1]["timestamp"]
        last_dt = datetime.fromtimestamp(last_ts / 1000, tz=pytz.UTC)
        cutoff_dt = last_dt - timedelta(days=lookback_years * DAYS_PER_YEAR)
        cutoff_timestamp = int(cutoff_dt.timestamp() * 1000)

        return [bar for bar in ohlcv_data if bar["timestamp"] >= cutoff_timestamp]

    def _prepare_data_for_vbp(self, ohlcv_data: list[OHLCVBar]) -> list[OHLCVBar]:
        """Prepare data for VBP calculation by aggregating to weekly if needed."""
        if self._get_bool_param("use_weekly", False):
            return ohlcv_data
        return self._aggregate_to_weekly(ohlcv_data)

    # VBP calculation helpers
    def _find_significant_levels(
        self, histogram: list[dict[str, Any]], num_levels: int
    ) -> list[dict[str, Any]]:
        """Find the most significant volume levels from histogram."""
        if not histogram:
            return []

        def volume_key(x: dict[str, Any]) -> float:
            vol = x.get("volume", 0.0)
            return float(vol) if isinstance(vol, int | float) else 0.0

        sorted_bins = sorted(histogram, key=volume_key, reverse=True)
        return sorted_bins[:num_levels]

    def _calculate_vbp_for_period(
        self, ohlcv_data: list[OHLCVBar], lookback_years: int
    ) -> list[dict[str, Any]]:
        """Calculate VBP levels for a single lookback period."""
        filtered_data = self._filter_by_lookback_period(ohlcv_data, lookback_years)

        if len(filtered_data) < MIN_BARS_REQUIRED:
            return []

        prepared_data = self._prepare_data_for_vbp(filtered_data)

        if len(prepared_data) < MIN_BARS_REQUIRED:
            return []

        bins = self._get_int_param("bins", 50)
        use_dollar_weighted = self._get_bool_param("use_dollar_weighted", False)
        use_close_only = self._get_bool_param("use_close_only", False)

        vbp_result = calculate_vbp(prepared_data, bins, use_dollar_weighted, use_close_only)

        if vbp_result.get("pointOfControl") is None:
            return []

        num_levels = self._get_int_param("num_levels", 5)
        return self._find_significant_levels(vbp_result["histogram"], num_levels)

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

        # Calculate levels for first period
        lookback_years_1 = self._get_int_param("lookback_years", 2)
        all_levels = self._calculate_vbp_for_period(ohlcv_data, lookback_years_1)

        # Calculate levels for second period if specified
        lookback_years_2 = self._get_optional_int_param("lookback_years_2")
        if lookback_years_2 is not None:
            levels_2 = self._calculate_vbp_for_period(ohlcv_data, lookback_years_2)
            all_levels.extend(levels_2)

        if not all_levels:
            return IndicatorResult(
                indicator_type=IndicatorType.VBP,
                timestamp=ohlcv_data[-1]["timestamp"],
                values=IndicatorValue(lines={}),
                params=self.params,
                error="No valid levels found",
            )

        # Process levels and calculate distances
        return self._build_indicator_result(ohlcv_data, all_levels)

    def _get_price_level(self, level: dict[str, Any]) -> float:
        """Extract price level from a VBP level dict."""
        pl = level.get("priceLevel", 0.0)
        return float(pl) if isinstance(pl, (int | float)) else 0.0

    def _deduplicate_levels(
        self, levels: list[dict[str, Any]], max_levels: int
    ) -> list[dict[str, Any]]:
        """Deduplicate and limit levels by price."""

        # Sort by volume descending
        def volume_sort_key(x: dict[str, Any]) -> float:
            vol = x.get("volume", 0.0)
            return float(vol) if isinstance(vol, (int | float)) else 0.0

        sorted_levels = sorted(levels, key=volume_sort_key, reverse=True)
        top_levels = sorted_levels[:max_levels]

        # Remove duplicates based on price (within small tolerance)
        unique_levels: list[dict[str, Any]] = []
        seen_prices: set[float] = set()

        for level in top_levels:
            price_level = self._get_price_level(level)
            price_rounded = round(price_level, PRICE_ROUNDING_PRECISION)

            if price_rounded not in seen_prices:
                unique_levels.append(level)
                seen_prices.add(price_rounded)

        return unique_levels

    def _calculate_support_resistance(
        self, current_price: float, unique_levels: list[dict[str, Any]]
    ) -> tuple[float, float, bool]:
        """Calculate closest support and resistance levels."""
        support_levels = [
            level for level in unique_levels if self._get_price_level(level) < current_price
        ]
        resistance_levels = [
            level for level in unique_levels if self._get_price_level(level) > current_price
        ]

        # Find closest support
        if support_levels:
            closest_support_price = max(self._get_price_level(level) for level in support_levels)
        else:
            closest_support_price = (
                min(self._get_price_level(level) for level in unique_levels)
                if unique_levels
                else current_price
            )

        # Find closest resistance
        if resistance_levels:
            closest_resistance_price = min(
                self._get_price_level(level) for level in resistance_levels
            )
        else:
            closest_resistance_price = (
                max(self._get_price_level(level) for level in unique_levels)
                if unique_levels
                else current_price
            )

        has_resistance_above = len(resistance_levels) > 0
        return closest_support_price, closest_resistance_price, has_resistance_above

    def _calculate_distances(
        self,
        current_price: float,
        support_price: float,
        resistance_price: float,
        has_resistance: bool,
    ) -> tuple[float, float]:
        """Calculate percentage distances to support and resistance."""
        distance_to_support = (
            abs(current_price - support_price) / current_price * 100 if current_price > 0 else 0
        )

        if has_resistance:
            distance_to_resistance = (
                abs(resistance_price - current_price) / current_price * 100
                if current_price > 0
                else 0
            )
        else:
            distance_to_resistance = float("inf")

        return distance_to_support, distance_to_resistance

    def _build_indicator_result(
        self, ohlcv_data: list[OHLCVBar], all_levels: list[dict[str, Any]]
    ) -> IndicatorResult:
        """Build IndicatorResult from calculated levels."""
        current_price = ohlcv_data[-1]["close"]
        num_levels = self._get_int_param("num_levels", 5)

        # Determine max levels based on whether second period is used
        lookback_years_2 = self._get_optional_int_param("lookback_years_2")
        max_levels = num_levels * 2 if lookback_years_2 is not None else num_levels

        unique_levels = self._deduplicate_levels(all_levels, max_levels)

        support_price, resistance_price, has_resistance_above = self._calculate_support_resistance(
            current_price, unique_levels
        )

        distance_to_support, distance_to_resistance = self._calculate_distances(
            current_price, support_price, resistance_price, has_resistance_above
        )

        logger.debug(
            f"VBP calculation: current_price={current_price:.2f}, "
            f"closest_support={support_price:.2f}, closest_resistance={resistance_price:.2f}, "
            f"distance_to_support={distance_to_support:.2f}%, "
            f"distance_to_resistance={distance_to_resistance:.2f}%, "
            f"num_levels={len(unique_levels)}, has_resistance_above={has_resistance_above}"
        )

        return IndicatorResult(
            indicator_type=IndicatorType.VBP,
            timestamp=ohlcv_data[-1]["timestamp"],
            values=IndicatorValue(
                lines={
                    "current_price": current_price,
                    "closest_support": support_price,
                    "closest_resistance": resistance_price,
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
        max_distance_support = self._get_float_param("max_distance_to_support", 5.0)

        if distance_to_support > max_distance_support:
            logger.debug(
                f"VBP filter FAILED: distance_to_support={distance_to_support:.2f}% > "
                f"max={max_distance_support:.2f}%"
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
        min_distance_resistance = self._get_float_param("min_distance_to_resistance", 5.0)

        if distance_to_resistance < min_distance_resistance:
            logger.debug(
                f"VBP filter FAILED: distance_to_resistance={distance_to_resistance:.2f}% < "
                f"min={min_distance_resistance:.2f}%"
            )
            return False

        logger.debug(
            f"VBP filter PASSED: distance_to_support={distance_to_support:.2f}% <= "
            f"max={max_distance_support:.2f}%, distance_to_resistance={distance_to_resistance:.2f}% >= "
            f"min={min_distance_resistance:.2f}%"
        )
        return True

    async def _calculate_vbp_indicator(
        self, symbol: AssetSymbol, api_key: str, ohlcv_data: list[OHLCVBar]
    ) -> IndicatorResult:
        """Calculate VBP indicator, fetching weekly bars if needed."""
        if self._get_bool_param("use_weekly", False):
            weekly_bars = await self._fetch_weekly_bars(symbol, api_key)
            calculation_data = weekly_bars if weekly_bars else ohlcv_data
        else:
            calculation_data = ohlcv_data

        return self._calculate_indicator(calculation_data)

    async def _execute_impl(self, inputs: dict[str, Any]) -> NodeOutputs:
        """Override to handle weekly bar fetching when use_weekly=True."""
        ohlcv_bundle: dict[AssetSymbol, list[OHLCVBar]] = inputs.get("ohlcv_bundle", {})

        if not ohlcv_bundle:
            return {"filtered_ohlcv_bundle": {}}

        # If use_weekly is True, fetch weekly bars from Polygon for each symbol
        if self._get_bool_param("use_weekly", False):
            api_key = APIKeyVault().get("POLYGON_API_KEY")
            if not api_key:
                raise ValueError("Polygon API key not found in vault")

            max_concurrent = self._get_int_param("max_concurrent", 10)
            rate_limit = self._get_int_param("rate_limit_per_second", 95)

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

                            # Calculate indicator on fetched data (for filtering)
                            try:
                                indicator_result = await self._calculate_vbp_indicator(
                                    symbol, api_key, ohlcv_data
                                )

                                # Always output original input bars (preserve data fidelity)
                                if self._should_pass_filter(indicator_result):
                                    filtered_bundle[symbol] = ohlcv_data

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
