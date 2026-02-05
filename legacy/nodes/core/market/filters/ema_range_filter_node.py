import numpy as np

from core.types_registry import IndicatorResult, IndicatorType, IndicatorValue, OHLCVBar
from nodes.core.market.filters.base.base_indicator_filter_node import BaseIndicatorFilter
from services.indicator_calculators.ema_calculator import calculate_ema


class EmaRangeFilter(BaseIndicatorFilter):
    """
    Filters assets where EMA(10, high-low range) > close / 100
    """

    default_params = {
        "timeperiod": 10,
        "divisor": 100.0,
    }

    params_meta = [
        {"name": "timeperiod", "type": "number", "default": 10, "min": 1, "step": 1},
        {"name": "divisor", "type": "number", "default": 100.0, "min": 1.0, "step": 1.0},
    ]

    def _validate_indicator_params(self):
        timeperiod = self.params.get("timeperiod", 10)
        divisor = self.params.get("divisor", 100.0)
        if not isinstance(timeperiod, (int, float)) or timeperiod < 1:
            raise ValueError("Time period must be at least 1")
        if not isinstance(divisor, (int, float)) or divisor <= 0:
            raise ValueError("Divisor must be positive")

    def _calculate_indicator(self, ohlcv_data: list[OHLCVBar]) -> IndicatorResult:
        if not ohlcv_data:
            return IndicatorResult(
                indicator_type=IndicatorType.EMA_RANGE,
                values=IndicatorValue(lines={"ema_range": np.nan, "close": np.nan}),
                params=self.params,
                error="No data",
            )

        timeperiod_value = self.params.get("timeperiod", 10)
        if not isinstance(timeperiod_value, (int, float)):
            timeperiod_value = 10
        timeperiod = int(timeperiod_value)
        if len(ohlcv_data) < timeperiod:
            return IndicatorResult(
                indicator_type=IndicatorType.EMA_RANGE,
                timestamp=ohlcv_data[-1]["timestamp"],
                values=IndicatorValue(
                    lines={"ema_range": np.nan, "close": ohlcv_data[-1]["close"]}
                ),
                params=self.params,
                error="Insufficient data",
            )

        # Calculate price range
        highs = [bar["high"] for bar in ohlcv_data]
        lows = [bar["low"] for bar in ohlcv_data]
        closes = [bar["close"] for bar in ohlcv_data]
        price_range = [high - low for high, low in zip(highs, lows)]

        # Calculate EMA using the calculator
        ema_result = calculate_ema(price_range, period=timeperiod)
        ema_values = ema_result.get("ema", [])
        latest_ema = ema_values[-1] if ema_values else np.nan
        latest_close = closes[-1]

        values = IndicatorValue(
            lines={
                "ema_range": latest_ema if latest_ema is not None else np.nan,
                "close": latest_close,
            }
        )

        return IndicatorResult(
            indicator_type=IndicatorType.EMA_RANGE,
            timestamp=ohlcv_data[-1]["timestamp"],
            values=values,
            params=self.params,
        )

    def _should_pass_filter(self, indicator_result: IndicatorResult) -> bool:
        if indicator_result.error or not hasattr(indicator_result.values, "lines"):
            return False

        values = indicator_result.values.lines
        if "ema_range" not in values or "close" not in values:
            return False

        ema_range = values["ema_range"]
        close = values["close"]
        if np.isnan(ema_range) or np.isnan(close):
            return False

        divisor = self.params.get("divisor", 100.0)
        if not isinstance(divisor, (int, float)):
            divisor = 100.0

        return ema_range > close / divisor
