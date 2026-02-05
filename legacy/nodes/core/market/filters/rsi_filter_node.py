import numpy as np

from core.types_registry import IndicatorResult, IndicatorType, IndicatorValue, OHLCVBar
from nodes.core.market.filters.base.base_indicator_filter_node import BaseIndicatorFilter
from services.indicator_calculators.rsi_calculator import calculate_rsi


class RSIFilter(BaseIndicatorFilter):
    """
    Filters assets based on RSI (Relative Strength Index) values.
    """

    default_params = {
        "min_rsi": 30.0,
        "max_rsi": 70.0,
        "timeperiod": 14,
    }

    params_meta = [
        {
            "name": "min_rsi",
            "type": "number",
            "default": 30.0,
            "min": 0.0,
            "max": 100.0,
            "step": 1.0,
        },
        {
            "name": "max_rsi",
            "type": "number",
            "default": 70.0,
            "min": 0.0,
            "max": 100.0,
            "step": 1.0,
        },
        {"name": "timeperiod", "type": "number", "default": 14, "min": 1, "step": 1},
    ]

    def _validate_indicator_params(self):
        min_rsi_value = self.params.get("min_rsi", 30.0)
        max_rsi_value = self.params.get("max_rsi", 70.0)
        timeperiod_value = self.params.get("timeperiod", 14)

        if not isinstance(min_rsi_value, (int, float)):
            raise ValueError("min_rsi must be a number")
        if not isinstance(max_rsi_value, (int, float)):
            raise ValueError("max_rsi must be a number")
        if not isinstance(timeperiod_value, int):
            raise ValueError("timeperiod must be an integer")

        self.min_rsi = float(min_rsi_value)
        self.max_rsi = float(max_rsi_value)
        self.timeperiod = int(timeperiod_value)

        if self.min_rsi >= self.max_rsi:
            raise ValueError("Minimum RSI must be less than maximum RSI")

    def _calculate_indicator(self, ohlcv_data: list[OHLCVBar]) -> IndicatorResult:
        """Calculate RSI and return as IndicatorResult."""
        if not ohlcv_data:
            return IndicatorResult(
                indicator_type=IndicatorType.RSI,
                timestamp=0,
                values=IndicatorValue(single=np.nan),
                params=self.params,
                error="No data",
            )

        data_length: int = len(ohlcv_data)
        if data_length < self.timeperiod:
            return IndicatorResult(
                indicator_type=IndicatorType.RSI,
                timestamp=ohlcv_data[-1]["timestamp"],
                values=IndicatorValue(single=np.nan),
                params=self.params,
                error="Insufficient data",
            )

        # Extract close prices
        close_prices: list[float] = [bar["close"] for bar in ohlcv_data]

        # Use the calculator - returns full time series
        result: dict[str, list[float | None]] = calculate_rsi(close_prices, length=self.timeperiod)
        rsi_series: list[float | None] = result.get("rsi", [])

        # Return the last value from the series (or NaN if empty)
        latest_rsi: float = np.nan
        if rsi_series and len(rsi_series) > 0:
            latest_rsi_raw: float | None = rsi_series[-1]
            latest_rsi = latest_rsi_raw if latest_rsi_raw is not None else np.nan

        return IndicatorResult(
            indicator_type=IndicatorType.RSI,
            timestamp=ohlcv_data[-1]["timestamp"],
            values=IndicatorValue(single=latest_rsi),
            params=self.params,
        )

    def _should_pass_filter(self, indicator_result: IndicatorResult) -> bool:
        """Pass filter if RSI is within the specified range."""
        if indicator_result.error or not hasattr(indicator_result.values, "single"):
            return False

        latest_rsi: float = indicator_result.values.single
        if np.isnan(latest_rsi):
            return False

        return self.min_rsi <= latest_rsi <= self.max_rsi
