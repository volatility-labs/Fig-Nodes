import logging

from core.types_registry import IndicatorResult, IndicatorType, IndicatorValue, OHLCVBar
from nodes.core.market.filters.base.base_indicator_filter_node import BaseIndicatorFilter
from services.indicator_calculators.atr_calculator import calculate_atr

logger = logging.getLogger(__name__)


class ATRFilter(BaseIndicatorFilter):
    """
    Filters assets based on ATR (Average True Range) values.
    """

    default_params = {
        "min_atr": 0.0,
        "window": 14,
    }

    params_meta = [
        {"name": "min_atr", "type": "number", "default": 0.0, "min": 0.0, "step": 0.1},
        {"name": "window", "type": "number", "default": 14, "min": 1, "step": 1},
    ]

    def _validate_indicator_params(self):
        min_atr = self.params.get("min_atr", 0.0)
        window = self.params.get("window", 14)
        if not isinstance(min_atr, (int, float)) or min_atr < 0:
            raise ValueError("Minimum ATR cannot be negative")
        if not isinstance(window, (int, float)) or window <= 0:
            raise ValueError("Window must be positive")

    def _calculate_indicator(self, ohlcv_data: list[OHLCVBar]) -> IndicatorResult:
        """Calculate ATR and return as IndicatorResult."""
        if not ohlcv_data:
            return IndicatorResult(
                indicator_type=IndicatorType.ATR,
                timestamp=0,
                values=IndicatorValue(single=0.0),
                params=self.params,
                error="No data",
            )

        window = self.params.get("window", 14)
        if not isinstance(window, (int, float)):
            window = 14
        window = int(window)

        if len(ohlcv_data) < window:
            return IndicatorResult(
                indicator_type=IndicatorType.ATR,
                timestamp=ohlcv_data[-1]["timestamp"],
                values=IndicatorValue(single=0.0),
                params=self.params,
                error="Insufficient data",
            )

        # Extract lists for the calculator
        highs = [bar["high"] for bar in ohlcv_data]
        lows = [bar["low"] for bar in ohlcv_data]
        closes = [bar["close"] for bar in ohlcv_data]

        # Use the calculator - returns full time series
        result = calculate_atr(highs, lows, closes, length=window)
        atr_series = result.get("atr", [])

        # Get the last value from the series
        if atr_series and len(atr_series) > 0:
            latest_atr = atr_series[-1]
        else:
            latest_atr = None

        if latest_atr is None:
            latest_atr = 0.0

        return IndicatorResult(
            indicator_type=IndicatorType.ATR,
            timestamp=ohlcv_data[-1]["timestamp"],
            values=IndicatorValue(single=latest_atr),
            params=self.params,
        )

    def _should_pass_filter(self, indicator_result: IndicatorResult) -> bool:
        """Pass filter if ATR is above minimum threshold."""
        if indicator_result.error or not hasattr(indicator_result.values, "single"):
            return False

        latest_atr = indicator_result.values.single
        min_atr = self.params.get("min_atr", 0.0)
        if not isinstance(min_atr, (int, float)):
            min_atr = 0.0

        return latest_atr >= min_atr
