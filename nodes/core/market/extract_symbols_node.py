import logging
from typing import Dict, Any, List
from nodes.base.base_node import BaseNode
from core.types_registry import get_type, AssetSymbol, OHLCVBar

logger = logging.getLogger(__name__)


class ExtractSymbolsNode(BaseNode):
    """
    Extracts a list of asset symbols from an OHLCV bundle.
    Takes an OHLCV bundle (Dict[AssetSymbol, List[OHLCVBar]]) and outputs
    just the list of AssetSymbol keys.
    """
    inputs = {"ohlcv_bundle": get_type("OHLCVBundle")}
    outputs = {"symbols": get_type("AssetSymbolList")}
    default_params = {}
    params_meta = []

    async def execute(self, inputs: Dict[str, Any]) -> Dict[str, List[AssetSymbol]]:
        ohlcv_bundle: Dict[AssetSymbol, List[OHLCVBar]] = inputs.get("ohlcv_bundle", {})

        # Extract the asset symbols (keys) from the OHLCV bundle
        symbols = list(ohlcv_bundle.keys())

        return {"symbols": symbols}
