import asyncio
import logging
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
from services.indicator_calculators.evwma_calculator import (
    calculate_evwma,
    calculate_rolling_correlation,
)
from services.polygon_service import fetch_bars
from services.rate_limiter import RateLimiter

logger = logging.getLogger(__name__)


class EVWMAFilter(BaseIndicatorFilter):
    """
    EVWMA (Exponential Volume Weighted Moving Average) Filter

    Filters symbols based on EVWMA alignment and correlation across multiple timeframes.

    Requires warm-up period for accurate calculations.

    Note: Higher timeframes (4hr, 1day, weekly) are less accurate than shorter ones (1min, 5min, 15min).
    """

    inputs = {
        "ohlcv_bundle": get_type("OHLCVBundle"),
    }

    default_params = {
        "evwma1_timeframe": "1min",
        "evwma2_timeframe": "5min",
        "evwma3_timeframe": "15min",
        "length": 325,
        "use_cum_volume": False,
        "roll_window": 325,
        "corr_smooth_window": 1,
        "correlation_threshold": 0.6,
        "require_alignment": True,
        "require_price_above_evwma": True,
        "max_concurrent": 10,
        "rate_limit_per_second": 95,
    }

    params_meta = [
        {
            "name": "evwma1_timeframe",
            "type": "combo",
            "default": "1min",
            "options": ["", "1min", "5min", "15min", "30min", "1hr", "4hr", "1day", "weekly"],
            "label": "EVWMA 1 Timeframe",
            "description": "First EVWMA timeframe (leave blank to skip). Shorter timeframes (1min, 5min, 15min) are more accurate.",
        },
        {
            "name": "evwma2_timeframe",
            "type": "combo",
            "default": "5min",
            "options": ["", "1min", "5min", "15min", "30min", "1hr", "4hr", "1day", "weekly"],
            "label": "EVWMA 2 Timeframe",
            "description": "Second EVWMA timeframe (leave blank to skip). Shorter timeframes (1min, 5min, 15min) are more accurate.",
        },
        {
            "name": "evwma3_timeframe",
            "type": "combo",
            "default": "15min",
            "options": ["", "1min", "5min", "15min", "30min", "1hr", "4hr", "1day", "weekly"],
            "label": "EVWMA 3 Timeframe",
            "description": "Third EVWMA timeframe (leave blank to skip). Shorter timeframes (1min, 5min, 15min) are more accurate.",
        },
        {
            "name": "length",
            "type": "number",
            "default": 325,
            "min": 1,
            "step": 1,
            "label": "EVWMA Length",
            "description": "Period for EVWMA calculation",
        },
        {
            "name": "use_cum_volume",
            "type": "boolean",
            "default": False,
            "label": "Use Cumulative Volume",
            "description": "Use cumulative volume instead of rolling window volume",
        },
        {
            "name": "roll_window",
            "type": "number",
            "default": 325,
            "min": 1,
            "step": 1,
            "label": "Rolling Window",
            "description": "Window size for rolling correlation calculation",
        },
        {
            "name": "corr_smooth_window",
            "type": "number",
            "default": 1,
            "min": 1,
            "step": 1,
            "label": "Correlation Smoothing Window",
            "description": "Window size for smoothing correlation values",
        },
        {
            "name": "correlation_threshold",
            "type": "number",
            "default": 0.6,
            "min": 0.0,
            "max": 1.0,
            "step": 0.01,
            "label": "Correlation Threshold",
            "description": "Minimum correlation between EVWMAs to pass filter",
        },
        {
            "name": "require_alignment",
            "type": "boolean",
            "default": True,
            "label": "Require Alignment",
            "description": "Require EVWMAs to be in descending order (shorter > longer timeframe)",
        },
        {
            "name": "require_price_above_evwma",
            "type": "boolean",
            "default": True,
            "label": "Require Price Above EVWMA",
            "description": "Require current price to be above all EVWMAs",
        },
    ]

    def __init__(
        self,
        id: int,
        params: dict[str, Any] | None = None,
        graph_context: dict[str, Any] | None = None,
    ):
        super().__init__(id, params or {}, graph_context)
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
        """Validate filter parameters."""
        length = self.params.get("length", 325)
        if not isinstance(length, (int, float)) or length <= 0:
            raise ValueError("length must be a positive number")

        roll_window = self.params.get("roll_window", 325)
        if not isinstance(roll_window, (int, float)) or roll_window <= 0:
            raise ValueError("roll_window must be a positive number")

        corr_smooth_window = self.params.get("corr_smooth_window", 1)
        if not isinstance(corr_smooth_window, (int, float)) or corr_smooth_window <= 0:
            raise ValueError("corr_smooth_window must be a positive number")

        correlation_threshold = self.params.get("correlation_threshold", 0.6)
        if (
            not isinstance(correlation_threshold, (int, float))
            or correlation_threshold < 0
            or correlation_threshold > 1
        ):
            raise ValueError("correlation_threshold must be between 0 and 1")

    def _timeframe_to_multiplier_timespan(self, timeframe: str) -> tuple[int, str]:
        """Convert timeframe string to multiplier and timespan for Polygon API."""
        timeframe_map = {
            "1min": (1, "minute"),
            "5min": (5, "minute"),
            "15min": (15, "minute"),
            "30min": (30, "minute"),
            "1hr": (1, "hour"),
            "4hr": (4, "hour"),
            "1day": (1, "day"),
            "weekly": (1, "week"),
        }
        return timeframe_map.get(timeframe, (1, "minute"))

    def _calculate_lookback_days(self, timeframe: str, length: int) -> int:
        """Calculate lookback period in days based on timeframe and length."""
        if timeframe == "1min":
            return max(1, int(length / (390 * 60))) + 1  # 390 minutes per trading day
        elif timeframe.endswith("min"):
            mins = int(timeframe.replace("min", ""))
            return max(1, int(length * mins / (390 * 60))) + 1
        elif timeframe == "1hr":
            return max(1, int(length / 390)) + 1
        elif timeframe == "4hr":
            return max(1, int(length * 4 / 390)) + 1
        elif timeframe == "1day":
            return max(1, length) + 1
        elif timeframe == "weekly":
            return max(7, length * 7) + 1
        else:
            return 30

    def _smooth_correlation(
        self, correlations: list[float | None], window: int
    ) -> list[float | None]:
        """Smooth correlation values using rolling mean."""
        if window <= 1:
            return correlations

        results: list[float | None] = [None] * len(correlations)

        for i in range(len(correlations)):
            window_start = max(0, i - window + 1)
            window_values = correlations[window_start : i + 1]
            valid_values = [v for v in window_values if v is not None]

            if valid_values:
                results[i] = sum(valid_values) / len(valid_values)
            else:
                results[i] = None

        return results

    async def _calculate_evwma_indicator(
        self, symbol: AssetSymbol, api_key: str, ohlcv_data: list[OHLCVBar]
    ) -> IndicatorResult:
        """Calculate EVWMA indicator across multiple timeframes."""
        evwma1_tf_raw = self.params.get("evwma1_timeframe", "1min")
        evwma2_tf_raw = self.params.get("evwma2_timeframe", "5min")
        evwma3_tf_raw = self.params.get("evwma3_timeframe", "15min")
        length_raw = self.params.get("length", 325)
        use_cum_volume_raw = self.params.get("use_cum_volume", False)
        roll_window_raw = self.params.get("roll_window", 325)
        corr_smooth_window_raw = self.params.get("corr_smooth_window", 1)
        threshold_raw = self.params.get("correlation_threshold", 0.6)
        require_alignment_raw = self.params.get("require_alignment", True)
        require_price_above_evwma_raw = self.params.get("require_price_above_evwma", True)

        # Type guards and conversions
        evwma1_tf = str(evwma1_tf_raw) if isinstance(evwma1_tf_raw, str) else "1min"
        evwma2_tf = str(evwma2_tf_raw) if isinstance(evwma2_tf_raw, str) else "5min"
        evwma3_tf = str(evwma3_tf_raw) if isinstance(evwma3_tf_raw, str) else "15min"
        length = int(length_raw) if isinstance(length_raw, (int | float)) else 325
        use_cum_volume = bool(use_cum_volume_raw) if isinstance(use_cum_volume_raw, bool) else False
        roll_window = int(roll_window_raw) if isinstance(roll_window_raw, (int | float)) else 325
        corr_smooth_window = (
            int(corr_smooth_window_raw) if isinstance(corr_smooth_window_raw, (int | float)) else 1
        )
        threshold = float(threshold_raw) if isinstance(threshold_raw, (int | float)) else 0.6
        require_alignment = (
            bool(require_alignment_raw) if isinstance(require_alignment_raw, bool) else True
        )
        require_price_above_evwma = (
            bool(require_price_above_evwma_raw)
            if isinstance(require_price_above_evwma_raw, bool)
            else True
        )

        # Get selected timeframes (non-empty)
        selected_timeframes = [tf for tf in [evwma1_tf, evwma2_tf, evwma3_tf] if tf]

        if not selected_timeframes:
            return IndicatorResult(
                indicator_type=IndicatorType.EVWMA,
                timestamp=0,
                values=IndicatorValue(),
                params=self.params,
                error="No EVWMA timeframes selected",
            )

        # Get current price from input data (most recent bar)
        if not ohlcv_data:
            return IndicatorResult(
                indicator_type=IndicatorType.EVWMA,
                timestamp=0,
                values=IndicatorValue(),
                params=self.params,
                error="No OHLCV data provided",
            )

        current_price = ohlcv_data[-1]["close"]
        latest_timestamp = ohlcv_data[-1]["timestamp"]

        # Fetch data for each timeframe and calculate EVWMA
        evwma_series: dict[str, list[float | None]] = {}
        evwma_latest_values: dict[str, float] = {}
        evwma_latest_closes: dict[str, float] = {}

        for i, timeframe in enumerate(selected_timeframes):
            multiplier, timespan = self._timeframe_to_multiplier_timespan(timeframe)
            lookback_days = self._calculate_lookback_days(timeframe, length)

            fetch_params = {
                "multiplier": multiplier,
                "timespan": timespan,
                "lookback_period": f"{lookback_days} days",
                "adjusted": True,
                "sort": "asc",
                "limit": 50000,
            }

            bars, _metadata = await fetch_bars(symbol, api_key, fetch_params)

            if not bars or len(bars) < length:
                return IndicatorResult(
                    indicator_type=IndicatorType.EVWMA,
                    timestamp=latest_timestamp,
                    values=IndicatorValue(),
                    params=self.params,
                    error=f"Insufficient data for {timeframe} EVWMA: {len(bars) if bars else 0} bars",
                )

            # Calculate EVWMA
            evwma_result = calculate_evwma(bars, length, use_cum_volume, roll_window)
            evwma_values = evwma_result.get("evwma", [])

            if not evwma_values or len(evwma_values) < length:
                return IndicatorResult(
                    indicator_type=IndicatorType.EVWMA,
                    timestamp=latest_timestamp,
                    values=IndicatorValue(),
                    params=self.params,
                    error=f"Insufficient EVWMA data for {timeframe}",
                )

            evwma_name = f"evwma{i + 1}"
            evwma_series[evwma_name] = evwma_values

            # Get latest EVWMA value
            latest_evwma = None
            for val in reversed(evwma_values):
                if val is not None:
                    latest_evwma = val
                    break

            if latest_evwma is not None:
                evwma_latest_values[evwma_name] = latest_evwma
                evwma_latest_closes[evwma_name] = bars[-1]["close"]

        # Check price above EVWMA if required
        if require_price_above_evwma:
            for evwma_name, latest_evwma in evwma_latest_values.items():
                # For 1min timeframe, compare with current price from input
                if evwma_name == "evwma1" and selected_timeframes[0] == "1min":
                    if current_price <= latest_evwma:
                        return IndicatorResult(
                            indicator_type=IndicatorType.EVWMA,
                            timestamp=latest_timestamp,
                            values=IndicatorValue(),
                            params=self.params,
                            error=f"Price {current_price} not above {evwma_name} {latest_evwma}",
                        )
                else:
                    # For other timeframes, compare with latest close from that timeframe
                    latest_close = evwma_latest_closes.get(evwma_name)
                    if latest_close is None or latest_close <= latest_evwma:
                        return IndicatorResult(
                            indicator_type=IndicatorType.EVWMA,
                            timestamp=latest_timestamp,
                            values=IndicatorValue(),
                            params=self.params,
                            error=f"Price {latest_close} not above {evwma_name} {latest_evwma}",
                        )

        # If only one EVWMA selected, check if we have enough data
        if len(evwma_series) == 1:
            ev1 = list(evwma_series.values())[0]
            valid_count = sum(1 for v in ev1 if v is not None)
            if valid_count < length:
                return IndicatorResult(
                    indicator_type=IndicatorType.EVWMA,
                    timestamp=latest_timestamp,
                    values=IndicatorValue(),
                    params=self.params,
                    error="Insufficient valid EVWMA data",
                )

            # Single EVWMA passes if price is above (already checked)
            return IndicatorResult(
                indicator_type=IndicatorType.EVWMA,
                timestamp=latest_timestamp,
                values=IndicatorValue(
                    lines={
                        "current_price": current_price,
                        "evwma1": evwma_latest_values.get("evwma1", 0.0),
                    }
                ),
                params=self.params,
            )

        # Align all EVWMAs to the shortest timeframe (most granular)
        # Find the most granular timeframe (longest series)
        base_series = None
        max_length = 0

        for name, series in evwma_series.items():
            valid_count = sum(1 for v in series if v is not None)
            if valid_count > max_length:
                max_length = valid_count
                base_series = series

        if base_series is None:
            return IndicatorResult(
                indicator_type=IndicatorType.EVWMA,
                timestamp=latest_timestamp,
                values=IndicatorValue(),
                params=self.params,
                error="No valid base series found",
            )

        # Align all series to base length (forward fill from the end)
        aligned_series: dict[str, list[float | None]] = {}
        base_length = len(base_series)

        for name, series in evwma_series.items():
            aligned: list[float | None] = []
            # Forward fill from the end
            last_value: float | None = None
            for i in range(base_length - 1, -1, -1):
                if i < len(series) and series[i] is not None:
                    last_value = series[i]
                aligned.insert(0, last_value)
            aligned_series[name] = aligned

        # Check alignment if required and we have multiple EVWMAs
        if require_alignment and len(evwma_series) >= 2:
            latest_values = [
                evwma_latest_values.get(f"evwma{i + 1}") for i in range(len(selected_timeframes))
            ]
            valid_values = [v for v in latest_values if v is not None]

            if len(valid_values) >= 2:
                # Check that values are in descending order (shorter timeframe > longer timeframe)
                for i in range(len(valid_values) - 1):
                    if valid_values[i] <= valid_values[i + 1]:
                        return IndicatorResult(
                            indicator_type=IndicatorType.EVWMA,
                            timestamp=latest_timestamp,
                            values=IndicatorValue(),
                            params=self.params,
                            error=f"EVWMAs not aligned: {valid_values}",
                        )

        # Calculate correlations if we have at least 2 EVWMAs
        correlation_passed = True
        if len(evwma_series) >= 2:
            evwma_names = list(aligned_series.keys())
            all_correlations: list[list[float | None]] = []

            # Calculate correlation between all pairs
            for i in range(len(evwma_names)):
                for j in range(i + 1, len(evwma_names)):
                    corr = calculate_rolling_correlation(
                        aligned_series[evwma_names[i]], aligned_series[evwma_names[j]], roll_window
                    )
                    all_correlations.append(corr)

            if not all_correlations:
                return IndicatorResult(
                    indicator_type=IndicatorType.EVWMA,
                    timestamp=latest_timestamp,
                    values=IndicatorValue(),
                    params=self.params,
                    error="No correlations calculated",
                )

            # Average correlations across pairs
            avg_correlations: list[float | None] = []
            for k in range(len(all_correlations[0])):
                values_at_k = [corr[k] for corr in all_correlations if k < len(corr)]
                valid_values = [v for v in values_at_k if v is not None]
                if valid_values:
                    avg_correlations.append(sum(valid_values) / len(valid_values))
                else:
                    avg_correlations.append(None)

            # Smooth correlations
            smoothed_correlations = self._smooth_correlation(avg_correlations, corr_smooth_window)

            # Get final correlation
            final_corr = None
            for val in reversed(smoothed_correlations):
                if val is not None:
                    final_corr = val
                    break

            if final_corr is None or final_corr < threshold:
                correlation_passed = False

        # Build result
        lines: dict[str, Any] = {
            "current_price": current_price,
        }
        for name, value in evwma_latest_values.items():
            lines[name] = value

        if len(evwma_series) >= 2:
            lines["correlation_passed"] = 1.0 if correlation_passed else 0.0

        return IndicatorResult(
            indicator_type=IndicatorType.EVWMA,
            timestamp=latest_timestamp,
            values=IndicatorValue(lines=lines),
            params=self.params,
            error=None if correlation_passed else "Correlation below threshold",
        )

    def _calculate_indicator(self, ohlcv_data: list[OHLCVBar]) -> IndicatorResult:
        """Not used - we override _execute_impl instead."""
        raise NotImplementedError("Use async _calculate_evwma_indicator instead")

    def _should_pass_filter(self, indicator_result: IndicatorResult) -> bool:
        """Determine if the asset should pass based on IndicatorResult."""
        if indicator_result.error:
            return False

        if not indicator_result.values.lines:
            return False

        # Check correlation if multiple EVWMAs
        correlation_passed = indicator_result.values.lines.get("correlation_passed", 1.0)
        return correlation_passed > 0.5

    async def _execute_impl(self, inputs: dict[str, Any]) -> NodeOutputs:
        """Override to handle async data fetching for multiple timeframes."""
        api_key = APIKeyVault().get("POLYGON_API_KEY")
        if not api_key:
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
                                (completed_count / total_symbols) * 100 if total_symbols else 0.0
                            )
                            progress_text_pre = f"{completed_count}/{total_symbols}"
                            self.report_progress(progress_pre, progress_text_pre)
                        except Exception:
                            logger.debug("Progress pre-update failed; continuing")

                        # Calculate EVWMA indicator
                        try:
                            indicator_result = await self._calculate_evwma_indicator(
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
                                f"Error processing EVWMA for {symbol}: {str(e)}", exc_info=True
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
