import logging
import pandas as pd
import numpy as np
from typing import Dict, Any, List
from nodes.core.market.indicators.base.base_indicator_node import BaseIndicatorNode
from core.types_registry import get_type, IndicatorResult, IndicatorType

logger = logging.getLogger(__name__)

class AtrXIndicatorNode(BaseIndicatorNode):
    ui_module = "market/AtrXIndicatorNodeUI"
    """
    Computes the ATRX indicator for a single asset's OHLCV data.
    ATRX = (Current Price - MA) / Smoothed ATR
    """
    inputs = {"ohlcv": get_type("OHLCV")}
    outputs = {"results": List[IndicatorResult]}
    default_params = {
        "length": 14,
        "smoothing": "RMA",
        "price": "Close",
        "ma_length": 50,
    }
    params_meta = [
        {"name": "length", "type": "integer", "default": 14},
        {"name": "smoothing", "type": "combo", "default": "RMA", "options": ["RMA", "EMA", "SMA"]},
        {"name": "price", "type": "string", "default": "Close"},
        {"name": "ma_length", "type": "integer", "default": 50},
    ]

    async def execute(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        ohlcv: List[Dict[str, float]] = inputs.get("ohlcv", [])
        if not ohlcv:
            return {"results": []}
        try:
            df_data = [
                {
                    "timestamp": pd.to_datetime(bar["timestamp"], unit="ms"),
                    "Open": bar["open"],
                    "High": bar["high"],
                    "Low": bar["low"],
                    "Close": bar["close"],
                    "Volume": bar["volume"],
                }
                for bar in ohlcv
            ]
            df = pd.DataFrame(df_data).set_index("timestamp")
            if df.empty:
                return {"results": []}
            atrx_value = self.indicators_service.calculate_atrx(
                df,
                length=self.params.get("length", 14),
                ma_length=self.params.get("ma_length", 50),
                smoothing=self.params.get("smoothing", "RMA"),
                price=self.params.get("price", "Close"),
            )
            result = IndicatorResult(
                indicator_type=IndicatorType.ATRX,
                timestamp=int(df.index[-1].timestamp() * 1000),
                values={"single": atrx_value},
            )
            return {"results": [result]}
        except Exception as e:
            logger.warning(f"Error computing ATRX: {e}")
            return {"results": []}
