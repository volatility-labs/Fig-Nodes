import logging
from typing import Any

from core.types_registry import AssetSymbol, OHLCVBar, get_type
from nodes.base.base_node import Base

logger = logging.getLogger(__name__)


class ExtractSymbols(Base):
    """
    Extracts a list of asset symbols from an OHLCV bundle.
    Takes an OHLCV bundle (Dict[AssetSymbol, List[OHLCVBar]]) and outputs
    just the list of AssetSymbol keys.
    """

    inputs = {"ohlcv_bundle": get_type("OHLCVBundle")}
    outputs = {"symbols": get_type("AssetSymbolList")}
    default_params = {}
    params_meta = []

    async def _execute_impl(self, inputs: dict[str, Any]) -> dict[str, list[AssetSymbol]]:
        ohlcv_bundle: dict[AssetSymbol, list[OHLCVBar]] = inputs.get("ohlcv_bundle", {})

        # Extract the asset symbols (keys) from the OHLCV bundle
        symbols = list(ohlcv_bundle.keys())

        return {"symbols": symbols}
