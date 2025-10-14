from typing import Dict, Any
from core.types_registry import get_type
from nodes.base.base_node import BaseNode
from core.types_registry import AssetSymbol, AssetClass, InstrumentType
from core.types_registry import Provider


class AssetSymbolInputNode(BaseNode):
    """Node to create a single AssetSymbol from user parameters."""
    inputs = {}
    outputs = {"symbol": get_type("AssetSymbol")}
    default_params = {
        "ticker": "",
        "asset_class": AssetClass.CRYPTO,
        "quote_currency": "USDT",
        "provider": Provider.BINANCE.name,
        "instrument_type": InstrumentType.PERPETUAL.name,
    }
    params_meta = [
        {"name": "ticker", "type": "text", "default": ""},
        {"name": "asset_class", "type": "combo", "default": AssetClass.CRYPTO, "options": [AssetClass.CRYPTO, AssetClass.STOCKS]},
        {"name": "quote_currency", "type": "text", "default": "USDT"},
        {"name": "provider", "type": "combo", "default": Provider.BINANCE.name, "options": [p.name for p in Provider]},
        {"name": "instrument_type", "type": "combo", "default": InstrumentType.PERPETUAL.name, "options": [e.name for e in InstrumentType]},
    ]

    async def _execute_impl(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        try:
            symbol = AssetSymbol(
                ticker=self.params["ticker"].upper(),
                asset_class=self.params["asset_class"],
                quote_currency=self.params.get("quote_currency").upper(),
                provider=Provider[self.params["provider"]],
                instrument_type=InstrumentType[self.params["instrument_type"]],
            )
        except KeyError as e:
            raise ValueError(f"Invalid parameter for provider/instrument_type: {self.params}") from e
        return {"symbol": symbol}


