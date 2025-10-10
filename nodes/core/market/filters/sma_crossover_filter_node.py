import pandas as pd
import numpy as np
from typing import Dict, Any, List
from ta.trend import SMAIndicator
from nodes.core.market.filters.base.base_indicator_filter_node import BaseIndicatorFilterNode
from core.types_registry import OHLCVBar, IndicatorResult, IndicatorType, IndicatorValue


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

    def _calculate_indicator(self, ohlcv_data: List[OHLCVBar]) -> IndicatorResult:
        """Calculate SMA crossover signal and return as IndicatorResult."""
        if not ohlcv_data:
            return IndicatorResult(
                indicator_type=IndicatorType.SMA,
                timestamp=0,
                values={"single": False},
                params=self.params,
                error="No data"
            )

        df = pd.DataFrame(ohlcv_data)
        if len(df) < self.params["long_period"]:
            return IndicatorResult(
                indicator_type=IndicatorType.SMA,
                timestamp=int(df['timestamp'].iloc[-1]),
                values={"single": False},
                params=self.params,
                error="Insufficient data"
            )

        # Calculate SMAs
        short_sma = SMAIndicator(close=df['close'], window=self.params["short_period"]).sma_indicator()
        long_sma = SMAIndicator(close=df['close'], window=self.params["long_period"]).sma_indicator()

        # Check for crossover (short SMA crosses above long SMA)
        crossover_signal = (short_sma > long_sma) & (short_sma.shift(1) <= long_sma.shift(1))
        latest_crossover = crossover_signal.iloc[-1] if not crossover_signal.empty else False

        values: IndicatorValue = {"single": bool(latest_crossover)} if not pd.isna(latest_crossover) else {"single": False}

        return IndicatorResult(
            indicator_type=IndicatorType.SMA,
            timestamp=int(df['timestamp'].iloc[-1]),
            values=values,
            params=self.params
        )

    def _should_pass_filter(self, indicator_result: IndicatorResult) -> bool:
        """Pass filter if there's a recent bullish crossover."""
        if "error" in indicator_result or "single" not in indicator_result["values"]:
            return False

        latest_crossover = indicator_result["values"]["single"]
        return bool(latest_crossover)
