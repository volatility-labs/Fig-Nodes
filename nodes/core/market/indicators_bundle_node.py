from typing import Dict, Any
from nodes.base.base_node import BaseNode
from core.types_registry import get_type
from core.types_registry import AssetSymbol


class IndicatorsBundleNode(BaseNode):
    """
    Computes a bundle of indicators for the given k-line data.
    """
    inputs = {"klines": get_type("OHLCVBundle")}
    outputs = {"indicators": Dict[AssetSymbol, Dict[str, Any]]}
    default_params = {"timeframe": "1h"}

    def __init__(self, node_id: str, params: Dict[str, Any]):
        super().__init__(node_id, params)

    async def execute(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
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

        timeframe = self.params.get("timeframe")
        indicators_bundle = {}
        for symbol, klines_df in bundle.items():
            if klines_df is None or klines_df.empty:
                continue
            indicators = {}
            indicators_bundle[symbol] = indicators

        return {"indicators": indicators_bundle}


