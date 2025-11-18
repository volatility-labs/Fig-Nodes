import logging

from core.types_registry import IndicatorResult, IndicatorType, IndicatorValue, OHLCVBar
from nodes.core.market.filters.base.base_indicator_filter_node import BaseIndicatorFilter
from services.indicator_calculators.ema_calculator import calculate_ema

logger = logging.getLogger(__name__)


class WideningEMAsFilter(BaseIndicatorFilter):
    """
    Filters assets based on whether the difference between two EMAs is widening or narrowing.

    Calculates the difference between two EMAs and compares it to the previous period's difference
    to determine if the EMAs are diverging (widening) or converging (narrowing).

    Formula: [EMA(fast_period) - EMA(slow_period)] compared to [previous EMA(fast_period) - EMA(slow_period)]

    Widening: Current difference > Previous difference
    Narrowing: Current difference < Previous difference

    Only assets meeting the widening/narrowing condition will pass the filter.
    """

    default_params = {
        "fast_ema_period": 10,  # Fast EMA period
        "slow_ema_period": 30,  # Slow EMA period
        "widening": True,  # True for widening, False for narrowing
    }

    params_meta = [
        {
            "name": "fast_ema_period",
            "type": "number",
            "default": 10,
            "min": 2,
            "step": 1,
            "label": "Fast EMA Period",
            "description": "Period for the faster EMA (e.g., 10)",
        },
        {
            "name": "slow_ema_period",
            "type": "number",
            "default": 30,
            "min": 2,
            "step": 1,
            "label": "Slow EMA Period",
            "description": "Period for the slower EMA (e.g., 30)",
        },
        {
            "name": "widening",
            "type": "text",
            "default": "true",
            "label": "Check for Widening",
            "description": "true: filter for widening EMAs, false: filter for narrowing EMAs",
        },
    ]

    def _validate_indicator_params(self):
        """Validate EMA period parameters."""
        fast_period = self.params.get("fast_ema_period", 10)
        slow_period = self.params.get("slow_ema_period", 30)

        if not isinstance(fast_period, (int, float)) or fast_period < 2:
            raise ValueError("Fast EMA period must be at least 2")
        if not isinstance(slow_period, (int, float)) or slow_period < 2:
            raise ValueError("Slow EMA period must be at least 2")
        if fast_period >= slow_period:
            raise ValueError("Fast EMA period must be less than slow EMA period")

    def _calculate_indicator(self, ohlcv_data: list[OHLCVBar]) -> IndicatorResult:
        """Calculate EMA difference and compare widening/narrowing."""
        if not ohlcv_data:
            return IndicatorResult(
                indicator_type=IndicatorType.EMA,
                timestamp=0,
                values=IndicatorValue(lines={"ema_difference": 0.0, "is_widening": False}),
                params=self.params,
                error="No data",
            )

        # Need enough data for both EMAs plus one comparison period
        fast_period_raw = self.params.get("fast_ema_period", 10)
        slow_period_raw = self.params.get("slow_ema_period", 30)

        if not isinstance(fast_period_raw, (int, float)):
            fast_period = 10
        else:
            fast_period = int(fast_period_raw)

        if not isinstance(slow_period_raw, (int, float)):
            slow_period = 30
        else:
            slow_period = int(slow_period_raw)

        min_data_needed = max(fast_period, slow_period) + 1

        if len(ohlcv_data) < min_data_needed:
            return IndicatorResult(
                indicator_type=IndicatorType.EMA,
                timestamp=ohlcv_data[-1]["timestamp"],
                values=IndicatorValue(lines={"ema_difference": 0.0, "is_widening": False}),
                params=self.params,
                error=f"Insufficient data: need at least {min_data_needed} bars",
            )

        # Extract close prices
        close_prices = [bar["close"] for bar in ohlcv_data]

        # Calculate EMAs using the calculator
        fast_ema_result = calculate_ema(close_prices, period=fast_period)
        slow_ema_result = calculate_ema(close_prices, period=slow_period)

        fast_ema_series = fast_ema_result.get("ema", [])
        slow_ema_series = slow_ema_result.get("ema", [])

        # Check if we have enough data for comparison
        if len(fast_ema_series) < 2 or len(slow_ema_series) < 2:
            return IndicatorResult(
                indicator_type=IndicatorType.EMA,
                timestamp=ohlcv_data[-1]["timestamp"],
                values=IndicatorValue(lines={"ema_difference": 0.0, "is_widening": False}),
                params=self.params,
                error="Unable to calculate EMA difference",
            )

        # Get the last two values from each EMA series
        current_fast = fast_ema_series[-1]
        prev_fast = fast_ema_series[-2]
        current_slow = slow_ema_series[-1]
        prev_slow = slow_ema_series[-2]

        # Check for None values (calculator returns None when insufficient data)
        if current_fast is None or prev_fast is None or current_slow is None or prev_slow is None:
            return IndicatorResult(
                indicator_type=IndicatorType.EMA,
                timestamp=ohlcv_data[-1]["timestamp"],
                values=IndicatorValue(lines={"ema_difference": 0.0, "is_widening": False}),
                params=self.params,
                error="EMA calculation returned None values",
            )

        # Calculate EMA differences for the last two periods
        current_diff = current_fast - current_slow
        prev_diff = prev_fast - prev_slow

        # Check if widening (current difference > previous difference)
        is_widening = current_diff > prev_diff

        return IndicatorResult(
            indicator_type=IndicatorType.EMA,
            timestamp=ohlcv_data[-1]["timestamp"],
            values=IndicatorValue(
                lines={
                    "ema_difference": current_diff,
                    "is_widening": is_widening,
                    "fast_ema": current_fast,
                    "slow_ema": current_slow,
                    "prev_difference": prev_diff,
                }
            ),
            params=self.params,
        )

    def _should_pass_filter(self, indicator_result: IndicatorResult) -> bool:
        """Pass filter if EMA widening/narrowing condition is met."""
        if indicator_result.error:
            return False

        lines = indicator_result.values.lines
        if "is_widening" not in lines:
            return False

        is_widening = lines["is_widening"]

        # Handle string "true"/"false" from UI
        widening_param = self.params.get("widening", True)
        if isinstance(widening_param, str):
            widening_param = widening_param.lower() == "true"

        return is_widening == widening_param
