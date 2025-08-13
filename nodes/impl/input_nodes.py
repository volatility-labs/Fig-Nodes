from typing import Dict, Any
from core.types_registry import get_type
from nodes.base.base_node import BaseNode
from core.types_registry import AssetSymbol, AssetClass, InstrumentType
from core.types_registry import Provider

class TextInputNode(BaseNode):
    """Simple node that outputs a static text value from parameters."""
    inputs = {}
    outputs = {"text": str}
    default_params = {"value": ""}
    params_meta = [
        {"name": "value", "type": "textarea", "default": ""}
    ]

    async def execute(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        return {"text": self.params.get("value")}

class AssetSymbolInputNode(BaseNode):
    """Node to create a single AssetSymbol from user parameters."""
    inputs = {}
    outputs = {"symbol": get_type("AssetSymbol")}
    default_params = {
        "ticker": "",
        "asset_class": AssetClass.CRYPTO,
        "quote_currency": "USDT",
        "provider": Provider.BINANCE.name,  # Updated
        "instrument_type": InstrumentType.PERPETUAL.name
    }
    params_meta = [
        {"name": "ticker", "type": "text", "default": ""},
        {"name": "asset_class", "type": "combo", "default": AssetClass.CRYPTO, "options": [AssetClass.CRYPTO, AssetClass.STOCKS]},
        {"name": "quote_currency", "type": "text", "default": "USDT"},
        {"name": "provider", "type": "combo", "default": Provider.BINANCE.name, "options": [p.name for p in Provider]},
        {"name": "instrument_type", "type": "combo", "default": InstrumentType.PERPETUAL.name, "options": [e.name for e in InstrumentType]}
    ]

    async def execute(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        symbol = AssetSymbol(
            ticker=self.params["ticker"].upper(),
            asset_class=self.params["asset_class"],
            quote_currency=self.params.get("quote_currency").upper(),
            provider=Provider[self.params["provider"]],  # Updated
            instrument_type=InstrumentType[self.params["instrument_type"]]
        )
        # Optional: Add validation, e.g., if provider == Provider.POLYGON and asset_class == AssetClass.CRYPTO: raise ValueError(...)
        return {"symbol": symbol}
