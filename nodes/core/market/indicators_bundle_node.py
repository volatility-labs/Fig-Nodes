import logging
from typing import Dict, Any, List
import pandas as pd
from nodes.base.base_node import BaseNode
from core.types_registry import get_type, AssetSymbol, OHLCVBar
from services.indicators_service import IndicatorsService

logger = logging.getLogger(__name__)


class IndicatorsBundleNode(BaseNode):
    """
    Computes a bundle of indicators for the given k-line data.
    """
    inputs = {"klines": get_type("OHLCVBundle")}
    outputs = {"indicators": Dict[AssetSymbol, Dict[str, Any]]}
    default_params = {"timeframe": "1d"}

    def __init__(self, node_id: str, params: Dict[str, Any]):
        super().__init__(node_id, params)
        self.indicators_service = IndicatorsService()

    async def execute(self, inputs: Dict[str, Any]) -> Dict[str, Dict[AssetSymbol, Dict[str, Any]]]:
        bundle = inputs.get("klines", {})
        if not bundle:
            collected = {}
            i = 0
            while True:
                key = f"klines_{i}"
                if key not in inputs:
                    break
                val = inputs[key]
                if val is not None and isinstance(val, dict):
                    collected.update(val)
                i += 1
            bundle = collected
        if not bundle:
            return {"indicators": {}}

        timeframe = self.params.get("timeframe", "1d")
        indicators_bundle = {}

        for symbol, klines_list in bundle.items():
            if klines_list is None or not klines_list:
                continue

            try:
                # Convert OHLCV bars to DataFrame
                df_data = []
                for bar in klines_list:
                    df_data.append({
                        'timestamp': pd.to_datetime(bar['timestamp'], unit='ms'),
                        'Open': bar['open'],
                        'High': bar['high'],
                        'Low': bar['low'],
                        'Close': bar['close'],
                        'Volume': bar['volume']
                    })

                if not df_data:
                    continue

                df = pd.DataFrame(df_data)
                df.set_index('timestamp', inplace=True)

                # Compute indicators
                indicators = self.indicators_service.compute_indicators(df, timeframe)
                indicators_bundle[symbol] = indicators

            except Exception as e:
                logger.warning(f"Failed to compute indicators for {symbol}: {e}")
                continue

        return {"indicators": indicators_bundle}


