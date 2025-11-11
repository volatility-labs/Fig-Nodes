from core.types_registry import IndicatorResult, IndicatorType, IndicatorValue, OHLCVBar
from nodes.core.market.filters.base.base_indicator_filter_node import BaseIndicatorFilter
from services.indicator_calculators.adx_calculator import calculate_adx


class ADXFilter(BaseIndicatorFilter):
    """
    Filters assets based on ADX (Average Directional Index) values.
    """

    default_params = {
        "min_adx": 25.0,
        "timeperiod": 14,
    }

    params_meta = [
        {
            "name": "min_adx",
            "type": "number",
            "default": 25.0,
            "min": 0.0,
            "max": 100.0,
            "step": 0.1,
        },
        {"name": "timeperiod", "type": "number", "default": 14, "min": 1, "step": 1},
    ]

    def _validate_indicator_params(self):
        min_adx = self.params.get("min_adx", 25.0)
        timeperiod = self.params.get("timeperiod", 14)
        if not isinstance(min_adx, (int, float)) or min_adx < 0:
            raise ValueError("Minimum ADX cannot be negative")
        if not isinstance(timeperiod, (int, float)) or timeperiod <= 0:
            raise ValueError("Time period must be positive")

    def _calculate_indicator(self, ohlcv_data: list[OHLCVBar]) -> IndicatorResult:
        """Calculate ADX and return as IndicatorResult."""
        if not ohlcv_data:
            return IndicatorResult(
                indicator_type=IndicatorType.ADX,
                timestamp=0,
                values=IndicatorValue(single=0.0),
                params=self.params,
                error="No data",
            )

        timeperiod_value = self.params.get("timeperiod", 14)
        if not isinstance(timeperiod_value, (int, float)):
            timeperiod_value = 14
        timeperiod = int(timeperiod_value)
        if len(ohlcv_data) < timeperiod:
            return IndicatorResult(
                indicator_type=IndicatorType.ADX,
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
        result = calculate_adx(highs, lows, closes, period=timeperiod)
        adx_series = result.get("adx", [])

        # Get the last value from the series
        if adx_series and len(adx_series) > 0:
            latest_adx = adx_series[-1]
        else:
            latest_adx = None

        if latest_adx is None:
            latest_adx = 0.0

        return IndicatorResult(
            indicator_type=IndicatorType.ADX,
            timestamp=ohlcv_data[-1]["timestamp"],
            values=IndicatorValue(single=latest_adx),
            params=self.params,
        )

    def _should_pass_filter(self, indicator_result: IndicatorResult) -> bool:
        """Pass filter if ADX is above minimum threshold."""
        if indicator_result.error or not hasattr(indicator_result.values, "single"):
            return False

        latest_adx = indicator_result.values.single
        min_adx = self.params.get("min_adx", 25.0)
        if not isinstance(min_adx, (int, float)):
            min_adx = 25.0

        return latest_adx >= min_adx
