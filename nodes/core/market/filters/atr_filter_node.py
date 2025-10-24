import logging

import pandas as pd

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
        if self.params["min_atr"] < 0:
            raise ValueError("Minimum ATR cannot be negative")
        if self.params["window"] <= 0:
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

        df = pd.DataFrame(ohlcv_data)
        if len(df) < self.params["window"]:
            return IndicatorResult(
                indicator_type=IndicatorType.ATR,
                timestamp=int(df["timestamp"].iloc[-1]),
                values=IndicatorValue(single=0.0),
                params=self.params,
                error="Insufficient data",
            )

        # Extract lists for the calculator
        highs = df["high"].tolist()
        lows = df["low"].tolist()
        closes = df["close"].tolist()

        # Use the calculator - returns full time series
        result = calculate_atr(highs, lows, closes, length=int(self.params["window"]))
        atr_series = result.get("atr", [])

        # Get the last value from the series
        if atr_series and len(atr_series) > 0:
            latest_atr = atr_series[-1]
        else:
            latest_atr = None

        if latest_atr is None:
            latest_atr = 0.0

        values = (
            IndicatorValue(single=latest_atr)
            if not pd.isna(latest_atr)
            else IndicatorValue(single=0.0)
        )

        return IndicatorResult(
            indicator_type=IndicatorType.ATR,
            timestamp=int(df["timestamp"].iloc[-1]),
            values=values,
            params=self.params,
        )

    def _should_pass_filter(self, indicator_result: IndicatorResult) -> bool:
        """Pass filter if ATR is above minimum threshold."""
        if indicator_result.error or not hasattr(indicator_result.values, "single"):
            return False

        latest_atr = indicator_result.values.single
        if pd.isna(latest_atr):
            return False

        return latest_atr >= self.params["min_atr"]
