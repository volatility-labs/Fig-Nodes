
import logging
import pandas as pd
from typing import Dict, Any, List
from nodes.core.market.indicators.base.base_indicator_node import BaseIndicatorNode
from core.types_registry import get_type, IndicatorResult, IndicatorType, IndicatorValue
from ta.volatility import AverageTrueRange

logger = logging.getLogger(__name__)

class ATRIndicatorNode(BaseIndicatorNode):
    """
    Computes the ATR indicator for a single asset's OHLCV data.
    """
    inputs = {"ohlcv": get_type("OHLCV")}
    outputs = {"results": List[IndicatorResult]}
    default_params = {
        "window": 14,
    }
    params_meta = [
        {"name": "window", "type": "integer", "default": 14, "min": 1, "step": 1},
    ]

    async def execute(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        ohlcv: List[Dict[str, float]] = inputs.get("ohlcv", [])
        if not ohlcv:
            return {"results": []}
        try:
            df_data = [
                {
                    'timestamp': pd.to_datetime(bar['timestamp'], unit='ms'),
                    'High': bar['high'],
                    'Low': bar['low'],
                    'Close': bar['close'],
                } for bar in ohlcv
            ]
            df = pd.DataFrame(df_data).set_index('timestamp')
            if df.empty or len(df) < self.params["window"]:
                raise ValueError("Insufficient data for ATR computation.")
            atr_indicator = AverageTrueRange(
                high=df['High'],
                low=df['Low'],
                close=df['Close'],
                window=self.params["window"]
            )
            atr_series = atr_indicator.average_true_range()
            latest_atr = atr_series.iloc[-1]
            result = IndicatorResult(
                indicator_type=IndicatorType.ATR,
                timestamp=int(df.index[-1].timestamp() * 1000),
                values=IndicatorValue(single=latest_atr if not pd.isna(latest_atr) else 0.0),
                params=self.params
            )
            return {"results": [result.to_dict()]}
        except Exception as e:
            logger.warning(f"Error computing ATR: {e}")
            return {"results": []}
