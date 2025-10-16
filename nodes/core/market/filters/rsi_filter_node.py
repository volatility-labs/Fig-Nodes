import pandas as pd
import numpy as np
from typing import Dict, Any, List
from ta.momentum import RSIIndicator
from nodes.core.market.filters.base.base_indicator_filter_node import BaseIndicatorFilter
from core.types_registry import OHLCVBar, IndicatorResult, IndicatorType, IndicatorValue


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
        {"name": "min_rsi", "type": "number", "default": 30.0, "min": 0.0, "max": 100.0, "step": 1.0},
        {"name": "max_rsi", "type": "number", "default": 70.0, "min": 0.0, "max": 100.0, "step": 1.0},
        {"name": "timeperiod", "type": "number", "default": 14, "min": 1, "step": 1},
    ]

    def _validate_indicator_params(self):
        min_rsi = self.params.get("min_rsi", 30.0)
        max_rsi = self.params.get("max_rsi", 70.0)
        if min_rsi >= max_rsi:
            raise ValueError("Minimum RSI must be less than maximum RSI")

    def _calculate_indicator(self, ohlcv_data: List[OHLCVBar]) -> IndicatorResult:
        """Calculate RSI and return as IndicatorResult."""
        if not ohlcv_data:
            return IndicatorResult(
                indicator_type=IndicatorType.RSI,
                timestamp=0,
                values=IndicatorValue(single=np.nan),
                params=self.params,
                error="No data"
            )

        df = pd.DataFrame(ohlcv_data)
        if len(df) < self.params["timeperiod"]:
            return IndicatorResult(
                indicator_type=IndicatorType.RSI,
                timestamp=int(df['timestamp'].iloc[-1]),
                values=IndicatorValue(single=np.nan),
                params=self.params,
                error="Insufficient data"
            )

        rsi_indicator = RSIIndicator(
            close=df['close'],
            window=self.params["timeperiod"]
        )
        rsi_series = rsi_indicator.rsi()
        latest_rsi = rsi_series.iloc[-1] if not rsi_series.empty else np.nan

        values = IndicatorValue(single=latest_rsi) if not pd.isna(latest_rsi) else IndicatorValue(single=np.nan)

        return IndicatorResult(
            indicator_type=IndicatorType.RSI,
            timestamp=int(df['timestamp'].iloc[-1]),
            values=values,
            params=self.params
        )

    def _should_pass_filter(self, indicator_result: IndicatorResult) -> bool:
        """Pass filter if RSI is within the specified range."""
        if indicator_result.error or not hasattr(indicator_result.values, 'single'):
            return False

        latest_rsi = indicator_result.values.single
        if pd.isna(latest_rsi):
            return False

        min_rsi = self.params["min_rsi"]
        max_rsi = self.params["max_rsi"]

        return min_rsi <= latest_rsi <= max_rsi
