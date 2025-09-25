import pandas as pd
import numpy as np
from typing import Dict, Any, List
from ta.momentum import RSIIndicator
from nodes.core.market.base_indicator_filter_node import BaseIndicatorFilterNode
from core.types_registry import OHLCVBar


class RSIFilterNode(BaseIndicatorFilterNode):
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

    def _calculate_indicator(self, ohlcv_data: List[OHLCVBar]) -> pd.Series:
        """Calculate RSI values."""
        df = pd.DataFrame(ohlcv_data)
        if len(df) < self.params["timeperiod"]:
            return pd.Series([np.nan] * len(df))  # Insufficient data

        rsi_indicator = RSIIndicator(
            close=df['close'],
            window=self.params["timeperiod"]
        )

        return rsi_indicator.rsi()

    def _should_pass_filter(self, indicator_values: pd.Series) -> bool:
        """Pass filter if RSI is within the specified range."""
        if len(indicator_values) == 0:
            return False

        # Use the most recent RSI value
        latest_rsi = indicator_values.iloc[-1]

        # Handle NaN values (insufficient data)
        if pd.isna(latest_rsi):
            return False

        min_rsi = self.params["min_rsi"]
        max_rsi = self.params["max_rsi"]

        return min_rsi <= latest_rsi <= max_rsi
