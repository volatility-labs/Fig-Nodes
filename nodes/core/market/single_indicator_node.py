import logging
from typing import Dict, Any, List
import pandas as pd
import numpy as np
from nodes.base.base_node import BaseNode
from core.types_registry import get_type, IndicatorResult, IndicatorType, IndicatorValue
from services.indicators_service import IndicatorsService

logger = logging.getLogger(__name__)


class SingleIndicatorNode(BaseNode):
    """
    Computes technical indicators for a single asset's OHLCV data.
    Outputs a list of IndicatorResult for the requested indicators.
    """
    inputs = {"ohlcv": get_type("OHLCV")}
    outputs = {"results": List[IndicatorResult]}
    default_params = {
        "indicators": [IndicatorType.MACD, IndicatorType.RSI, IndicatorType.ADX],
        "timeframe": "1d",
    }
    params_meta = [
        {"name": "indicators", "type": "combo", "default": [IndicatorType.MACD, IndicatorType.RSI, IndicatorType.ADX], "options": [e.name for e in IndicatorType], "multiple": True},
        {"name": "timeframe", "type": "combo", "default": "1d", "options": ["1m", "5m", "15m", "1h", "4h", "1d", "1w", "1M"]},
    ]

    def __init__(self, node_id: str, params: Dict[str, Any]):
        super().__init__(node_id, params)
        self.indicators_service = IndicatorsService()

    async def execute(self, inputs: Dict[str, Any]) -> Dict[str, List[IndicatorResult]]:
        bars: List[Dict[str, Any]] = inputs.get("ohlcv", [])
        if not bars:
            logger.warning("No OHLCV data provided for single indicator computation.")
            return {"results": []}

        try:
            # Convert bars to DataFrame
            df_data = [
                {
                    'timestamp': pd.to_datetime(bar['timestamp'], unit='ms'),
                    'Open': bar['open'],
                    'High': bar['high'],
                    'Low': bar['low'],
                    'Close': bar['close'],
                    'Volume': bar['volume']
                }
                for bar in bars
            ]
            df = pd.DataFrame(df_data).set_index('timestamp')

            if df.empty or len(df) < 14:
                logger.warning("Insufficient data for indicators (need at least 14 bars).")
                return {"results": []}

            # Compute indicators using service
            raw_indicators = self.indicators_service.compute_indicators(df, self.params.get("timeframe", "1d"))

            results: List[IndicatorResult] = []
            for ind_type in self.params.get("indicators", []):
                try:
                    values = self._map_to_indicator_value(ind_type, raw_indicators)
                    result = IndicatorResult(
                        indicator_type=ind_type,
                        timestamp=int(df.index[-1].timestamp() * 1000),  # Unix ms
                        values=values,
                        params=self.params
                    )
                    results.append(result)
                except Exception as e:
                    logger.warning(f"Failed to compute {ind_type.name}: {e}")
                    results.append(IndicatorResult(
                        indicator_type=ind_type,
                        timestamp=int(df.index[-1].timestamp() * 1000),
                        error=str(e)
                    ))

            return {"results": results}
        except Exception as e:
            logger.error(f"Error in SingleIndicatorNode execute: {e}")
            return {"results": []}

    def _map_to_indicator_value(self, ind_type: IndicatorType, raw: Dict[str, Any]) -> IndicatorValue:
        """
        Maps raw indicator values from IndicatorsService to IndicatorValue format.
        Handles heterogeneous outputs per indicator type.
        """
        if ind_type == IndicatorType.EVWMA:
            return {"single": raw.get("evwma", np.nan)}
        elif ind_type == IndicatorType.EIS:
            return {"single": float(raw.get("eis_bullish", False) or raw.get("eis_bearish", False))}
        elif ind_type == IndicatorType.ADX:
            return {"single": raw.get("adx", np.nan)}
        elif ind_type == IndicatorType.HURST:
            return {"single": raw.get("hurst", np.nan)}
        elif ind_type == IndicatorType.VOLUME_RATIO:
            return {"single": raw.get("volume_ratio", 1.0)}
        elif ind_type == IndicatorType.MACD:
            # MACD has lines: macd, signal, histogram
            # Note: IndicatorsService doesn't compute full MACD; adapt or extend service
            return {"lines": {
                "macd": np.nan,  # Placeholder; extend service if needed
                "signal": np.nan,
                "histogram": np.nan
            }}
        elif ind_type == IndicatorType.RSI:
            # RSI series over time
            return {"series": []}  # Placeholder; compute via pandas-ta or extend
        else:
            raise ValueError(f"Unsupported indicator type: {ind_type.name}")

        # Fallback for unmapped
        return {"single": np.nan}

