import logging
import math
from typing import List
from nodes.core.market.filters.base.base_indicator_filter_node import BaseIndicatorFilter
from core.types_registry import OHLCVBar, IndicatorResult, IndicatorType, IndicatorValue

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
        "fast_ema_period": 10,      # Fast EMA period
        "slow_ema_period": 30,      # Slow EMA period
        "widening": True,           # True for widening, False for narrowing
    }

    params_meta = [
        {
            "name": "fast_ema_period",
            "type": "number",
            "default": 10,
            "min": 2,
            "step": 1,
            "label": "Fast EMA Period",
            "description": "Period for the faster EMA (e.g., 10)"
        },
        {
            "name": "slow_ema_period",
            "type": "number",
            "default": 30,
            "min": 2,
            "step": 1,
            "label": "Slow EMA Period",
            "description": "Period for the slower EMA (e.g., 30)"
        },
        {
            "name": "widening",
            "type": "boolean",
            "default": True,
            "label": "Check for Widening",
            "description": "True: filter for widening EMAs, False: filter for narrowing EMAs"
        },
    ]

    def _validate_indicator_params(self):
        if self.params["fast_ema_period"] >= self.params["slow_ema_period"]:
            raise ValueError("Fast EMA period must be less than slow EMA period")
        if self.params["fast_ema_period"] < 2 or self.params["slow_ema_period"] < 2:
            raise ValueError("EMA periods must be at least 2")

    def _calculate_ema(self, prices: List[float], period: int) -> List[float]:
        """Calculate Exponential Moving Average using Wilder's smoothing method."""
        if len(prices) < period:
            return []

        # Calculate multiplier
        multiplier = 2.0 / (period + 1)

        # Initialize EMA with SMA for first value
        ema_values = [sum(prices[:period]) / period]

        # Calculate subsequent EMAs
        for price in prices[period:]:
            ema = (price * multiplier) + (ema_values[-1] * (1 - multiplier))
            ema_values.append(ema)

        return ema_values

    def _calculate_indicator(self, ohlcv_data: List[OHLCVBar]) -> IndicatorResult:
        """Calculate EMA difference and compare widening/narrowing."""
        if not ohlcv_data:
            return IndicatorResult(
                indicator_type=IndicatorType.EMA,
                timestamp=0,
                values=IndicatorValue(lines={"ema_difference": 0.0, "is_widening": False}),
                params=self.params,
                error="No data"
            )

        # Need enough data for both EMAs plus one comparison period
        min_data_needed = max(self.params["fast_ema_period"], self.params["slow_ema_period"]) + 1
        if len(ohlcv_data) < min_data_needed:
            return IndicatorResult(
                indicator_type=IndicatorType.EMA,
                timestamp=ohlcv_data[-1]['timestamp'],
                values=IndicatorValue(lines={"ema_difference": 0.0, "is_widening": False}),
                params=self.params,
                error=f"Insufficient data: need at least {min_data_needed} bars"
            )

        # Extract close prices
        close_prices = [bar['close'] for bar in ohlcv_data]

        # Calculate EMAs
        fast_ema = self._calculate_ema(close_prices, self.params["fast_ema_period"])
        slow_ema = self._calculate_ema(close_prices, self.params["slow_ema_period"])

        if len(fast_ema) < 2 or len(slow_ema) < 2:
            return IndicatorResult(
                indicator_type=IndicatorType.EMA,
                timestamp=ohlcv_data[-1]['timestamp'],
                values=IndicatorValue(lines={"ema_difference": 0.0, "is_widening": False}),
                params=self.params,
                error="Unable to calculate EMA difference"
            )

        # Calculate EMA differences for the last two periods
        current_fast = fast_ema[-1]
        current_slow = slow_ema[-1]
        current_diff = current_fast - current_slow

        prev_fast = fast_ema[-2]
        prev_slow = slow_ema[-2]
        prev_diff = prev_fast - prev_slow

        # Check if widening (current difference > previous difference)
        is_widening = current_diff > prev_diff

        return IndicatorResult(
            indicator_type=IndicatorType.EMA,
            timestamp=ohlcv_data[-1]['timestamp'],
            values=IndicatorValue(lines={
                "ema_difference": current_diff,
                "is_widening": is_widening,
                "fast_ema": current_fast,
                "slow_ema": current_slow,
                "prev_difference": prev_diff
            }),
            params=self.params
        )

    def _should_pass_filter(self, indicator_result: IndicatorResult) -> bool:
        """Pass filter if EMA widening/narrowing condition is met."""
        if indicator_result.error:
            return False

        lines = indicator_result.values.lines
        if "is_widening" not in lines:
            return False

        is_widening = lines["is_widening"]
        return is_widening == self.params["widening"]
