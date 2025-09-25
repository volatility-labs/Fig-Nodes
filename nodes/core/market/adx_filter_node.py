import pandas as pd
from typing import Dict, Any, List
from ta.trend import ADXIndicator
from nodes.core.market.base_indicator_filter_node import BaseIndicatorFilterNode
from core.types_registry import OHLCVBar


class ADXFilterNode(BaseIndicatorFilterNode):
    """
    Filters assets based on ADX (Average Directional Index) values.
    """

    default_params = {
        "min_adx": 25.0,
        "timeperiod": 14,
    }

    params_meta = [
        {"name": "min_adx", "type": "number", "default": 25.0, "min": 0.0, "max": 100.0, "step": 0.1},
        {"name": "timeperiod", "type": "number", "default": 14, "min": 1, "step": 1},
    ]

    def _calculate_indicator(self, ohlcv_data: List[OHLCVBar]) -> pd.Series:
        """Calculate ADX values."""
        df = pd.DataFrame(ohlcv_data)
        if len(df) < self.params["timeperiod"]:
            return pd.Series([0.0] * len(df))

        adx_indicator = ADXIndicator(
            high=df['high'],
            low=df['low'],
            close=df['close'],
            window=self.params["timeperiod"]
        )

        return adx_indicator.adx()

    def _should_pass_filter(self, indicator_values: pd.Series) -> bool:
        """Pass filter if ADX is above minimum threshold."""
        if len(indicator_values) == 0:
            return False

        # Use the most recent ADX value
        latest_adx = indicator_values.iloc[-1]

        # Handle NaN values (insufficient data)
        if pd.isna(latest_adx):
            return False

        return latest_adx >= self.params["min_adx"]
