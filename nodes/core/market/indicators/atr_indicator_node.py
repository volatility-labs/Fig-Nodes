
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

    async def _execute_impl(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        ohlcv: List[Dict[str, float]] = inputs.get("ohlcv", [])
        if not ohlcv:
            return {"results": []}
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
            return {"results": []}
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

    def _map_to_indicator_value(self, ind_type: IndicatorType, raw: Dict[str, Any]) -> IndicatorValue:
        # This node computes ATR locally and does not use IndicatorsService mappings.
        # Implementing to satisfy BaseIndicatorNode's abstract method.
        raise ValueError(f"Unsupported indicator type for ATRIndicatorNode: {ind_type.name}")
