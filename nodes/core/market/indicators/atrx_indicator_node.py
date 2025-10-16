import logging
import pandas as pd
import numpy as np
from typing import Dict, Any, List
from nodes.core.market.indicators.base.base_indicator_node import BaseIndicatorNode
from core.types_registry import get_type, IndicatorResult, IndicatorType, IndicatorValue

logger = logging.getLogger(__name__)

class AtrXIndicatorNode(BaseIndicatorNode):
    ui_module = "market/AtrXIndicatorNodeUI"
    """
    Computes the ATRX indicator for a single asset's OHLCV data.
    ATRX = (Close - EMA(daily_avg)) / SMA(true_range)
    where daily_avg = (High + Low) / 2 and true_range = High - Low
    
    Following TradingView methodology for consistent results.
    """
    inputs = {"ohlcv": get_type("OHLCV")}
    outputs = {"results": List[IndicatorResult]}
    default_params = {
        "length": 14,  # ATR period (SMA of true range)
        "ma_length": 50,  # Trend EMA period
    }
    params_meta = [
        {"name": "length", "type": "integer", "default": 14, "description": "ATR period (SMA of true range)"},
        {"name": "ma_length", "type": "integer", "default": 50, "description": "Trend EMA period for daily average"},
    ]


    def _map_to_indicator_value(self, ind_type: IndicatorType, raw: Dict[str, Any]) -> IndicatorValue:
        """
        Satisfy BaseIndicatorNode's abstract contract. ATRX node uses its own
        _execute_impl path and does not rely on base mapping.
        """
        return IndicatorValue(single=float("nan"))

    async def _execute_impl(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        ohlcv: List[Dict[str, float]] = inputs.get("ohlcv", [])
        if not ohlcv:
            logger.warning("Empty OHLCV data provided to ATRX indicator")
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
                logger.warning("Empty DataFrame created from OHLCV data")
                return {"results": []}
            
            # Check for minimum data requirements
            min_required = max(self.params.get("length", 14), self.params.get("ma_length", 50))
            if len(df) < min_required:
                logger.warning(f"Insufficient data for ATRX calculation: {len(df)} bars, need {min_required}")
                return {"results": []}
            
            atrx_value = self.indicators_service.calculate_atrx(
                df,
                length=self.params.get("length", 14),
                ma_length=self.params.get("ma_length", 50),
                smoothing="SMA",  # Fixed to SMA as per TradingView methodology
                price="Close",    # Fixed to Close as per TradingView methodology
            )
            
            # Filter out NaN results (e.g., zero volatility cases)
            if np.isnan(atrx_value):
                logger.warning("ATRX calculation resulted in NaN (likely zero volatility)")
                return {"results": []}
            
            result = IndicatorResult(
                indicator_type=IndicatorType.ATRX,
                timestamp=int(df.index[-1].timestamp() * 1000),
                values=IndicatorValue(single=atrx_value),
            )
            return {"results": [result]}
            
        except Exception as e:
            logger.error(f"Error calculating ATRX indicator: {e}")
            return {"results": []}
