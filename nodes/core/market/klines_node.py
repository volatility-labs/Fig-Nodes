from typing import Dict, Any, List
from nodes.base.base_node import BaseNode
from core.types_registry import get_type, AssetSymbol, AssetClass, OHLCVBar


class KlinesNode(BaseNode):
    """
    Fetches K-line data for a symbol.
    """
    inputs = {}
    outputs = {"ohlcv": get_type("OHLCV")}
    default_params = {"symbol": get_type("AssetSymbol"), "timeframe": "1h"}
    required_asset_class = AssetClass.CRYPTO

    def __init__(self, node_id: str, params: Dict[str, Any]):
        super().__init__(node_id, params)

    async def execute(self, inputs: Dict[str, Any]) -> Dict[str, List[OHLCVBar]]:
        symbol: AssetSymbol = self.params.get("symbol")
        timeframe = self.params.get("timeframe")

        # Return empty list for OHLCV data
        return {"ohlcv": []}


