from typing import Dict, Any, List, Optional
import asyncio
import requests
from nodes.base.base_node import BaseNode
from core.types_registry import AssetSymbol, InstrumentType, AssetClass

class InstrumentResolverNode(BaseNode):
    inputs = {"symbols": List[AssetSymbol]}
    outputs = {"resolved_symbols": List[AssetSymbol]}
    default_params = {
        "exchange": "binance",
        "instrument_type": "PERPETUAL",
        "quote_currency": "USDT"
    }

    async def execute(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        symbols: List[AssetSymbol] = inputs.get("symbols", [])
        exchange = self.params.get("exchange")
        target_type = getattr(InstrumentType, self.params.get("instrument_type").upper())
        quote_currency = self.params.get("quote_currency")

        resolved = []
        for sym in symbols:
            if sym.asset_class != AssetClass.CRYPTO:
                # Only support crypto for now
                resolved.append(sym)
                continue

            # Query exchange API (example for Binance)
            if exchange == "binance":
                response = await asyncio.to_thread(requests.get, f"https://fapi.binance.com/fapi/v1/exchangeInfo")
                if response.status_code == 200:
                    info = response.json()
                    for ex_sym in info["symbols"]:
                        if ex_sym["baseAsset"].upper() == sym.ticker and ex_sym["quoteAsset"] == quote_currency and ex_sym["contractType"] == target_type.name:
                            resolved_sym = AssetSymbol(
                                ticker=sym.ticker,
                                asset_class=sym.asset_class,
                                quote_currency=quote_currency,
                                exchange=exchange,
                                instrument_type=target_type,
                                metadata={"contract_type": ex_sym["contractType"], "status": ex_sym["status"]}
                            )
                            resolved.append(resolved_sym)
                            break
            # Add more exchanges as needed

        return {"resolved_symbols": resolved}
