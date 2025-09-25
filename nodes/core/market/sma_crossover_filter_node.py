import pandas as pd
from typing import Dict, Any, List
from ta.trend import SMAIndicator
from nodes.core.market.base_indicator_filter_node import BaseIndicatorFilterNode
from core.types_registry import OHLCVBar


class SMACrossoverFilterNode(BaseIndicatorFilterNode):
    """
    Filters assets where short-term SMA crosses above long-term SMA (bullish crossover).
    """

    default_params = {
        "short_period": 20,
        "long_period": 50,
    }

    params_meta = [
        {"name": "short_period", "type": "number", "default": 20, "min": 1, "step": 1},
        {"name": "long_period", "type": "number", "default": 50, "min": 1, "step": 1},
    ]

    def _validate_indicator_params(self):
        short_period = self.params.get("short_period", 20)
        long_period = self.params.get("long_period", 50)
        if short_period >= long_period:
            raise ValueError("Short period must be less than long period")

    def _calculate_indicator(self, ohlcv_data: List[OHLCVBar]) -> pd.Series:
        """Calculate SMA crossover signal."""
        df = pd.DataFrame(ohlcv_data)
        if len(df) < self.params["long_period"]:
            return pd.Series([False] * len(df))

        # Calculate SMAs
        short_sma = SMAIndicator(close=df['close'], window=self.params["short_period"]).sma_indicator()
        long_sma = SMAIndicator(close=df['close'], window=self.params["long_period"]).sma_indicator()

        # Check for crossover (short SMA crosses above long SMA)
        crossover_signal = (short_sma > long_sma) & (short_sma.shift(1) <= long_sma.shift(1))

        return crossover_signal

    def _should_pass_filter(self, indicator_values: pd.Series) -> bool:
        """Pass filter if there's a recent bullish crossover."""
        # Check if the most recent bar shows a crossover
        return indicator_values.iloc[-1] if len(indicator_values) > 0 else False
