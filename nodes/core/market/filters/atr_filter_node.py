
import logging
import pandas as pd
from typing import Dict, Any, List
from ta.volatility import AverageTrueRange
from nodes.core.market.filters.base.base_indicator_filter_node import BaseIndicatorFilterNode
from core.types_registry import OHLCVBar, IndicatorResult, IndicatorType

logger = logging.getLogger(__name__)

class ATRFilterNode(BaseIndicatorFilterNode):
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

    def _calculate_indicator(self, ohlcv_data: List[OHLCVBar]) -> IndicatorResult:
        """Calculate ATR and return as IndicatorResult."""
        if not ohlcv_data:
            return IndicatorResult(
                indicator_type=IndicatorType.ATR,
                timestamp=0,
                values={"single": 0.0},
                params=self.params,
                error="No data"
            )

        df = pd.DataFrame(ohlcv_data)
        if len(df) < self.params["window"]:
            return IndicatorResult(
                indicator_type=IndicatorType.ATR,
                timestamp=int(df['timestamp'].iloc[-1]),
                values={"single": 0.0},
                params=self.params,
                error="Insufficient data"
            )

        atr_indicator = AverageTrueRange(
            high=df['high'],
            low=df['low'],
            close=df['close'],
            window=self.params["window"]
        )
        atr_series = atr_indicator.average_true_range()
        latest_atr = atr_series.iloc[-1] if not atr_series.empty else 0.0

        values = {"single": latest_atr} if not pd.isna(latest_atr) else {"single": 0.0}

        return IndicatorResult(
            indicator_type=IndicatorType.ATR,
            timestamp=int(df['timestamp'].iloc[-1]),
            values=values,
            params=self.params
        )

    def _should_pass_filter(self, indicator_result: IndicatorResult) -> bool:
        """Pass filter if ATR is above minimum threshold."""
        if "error" in indicator_result or "single" not in indicator_result["values"]:
            return False

        latest_atr = indicator_result["values"]["single"]
        if pd.isna(latest_atr):
            return False

        return latest_atr >= self.params["min_atr"]
