from typing import Dict, Any
from core.types_registry import get_type
from nodes.base.base_node import BaseNode
from core.types_registry import AssetSymbol, AssetClass, InstrumentType


class AssetSymbolInputNode(BaseNode):
    """Node to create a single AssetSymbol from user parameters."""
    inputs = {}
    outputs = {"symbol": get_type("AssetSymbol")}
    default_params = {
        "ticker": "",
        "asset_class": AssetClass.CRYPTO.name,
        "quote_currency": "USDT",
        "instrument_type": InstrumentType.PERPETUAL.name,
    }
    params_meta = [
        {"name": "ticker", "type": "text", "default": ""},
        {"name": "asset_class", "type": "combo", "default": AssetClass.CRYPTO.name, "options": [e.name for e in AssetClass]},
        {"name": "quote_currency", "type": "text", "default": "USDT"},
        {"name": "instrument_type", "type": "combo", "default": InstrumentType.PERPETUAL.name, "options": [e.name for e in InstrumentType]},
    ]

    async def _execute_impl(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        # Coerce params to enums and normalized cases
        ticker_value = (self.params.get("ticker") or "").upper()
        asset_class_param = self.params.get("asset_class", AssetClass.CRYPTO.name)
        instrument_type_param = self.params.get("instrument_type", InstrumentType.SPOT.name)
        quote_currency_value = (self.params.get("quote_currency") or None)
        if quote_currency_value:
            quote_currency_value = quote_currency_value.upper()

        # Accept both enum instance and name string for asset_class
        if isinstance(asset_class_param, AssetClass):
            asset_class_value = asset_class_param
        else:
            try:
                asset_class_value = AssetClass[str(asset_class_param).upper()]
            except Exception as e:
                raise ValueError(f"Invalid asset_class: {asset_class_param}") from e

        # Accept both enum instance and name string for instrument_type
        if isinstance(instrument_type_param, InstrumentType):
            instrument_type_value = instrument_type_param
        else:
            try:
                instrument_type_value = InstrumentType[str(instrument_type_param).upper()]
            except Exception as e:
                raise ValueError(f"Invalid instrument_type: {instrument_type_param}") from e

        symbol = AssetSymbol(
            ticker=ticker_value,
            asset_class=asset_class_value,
            quote_currency=quote_currency_value,
            instrument_type=instrument_type_value,
        )
        return {"symbol": symbol}


