from typing import Dict, Any, List
import asyncio
import requests
from nodes.base.base_node import Base
from core.types_registry import AssetSymbol, InstrumentType, AssetClass
from core.types_registry import get_type


class InstrumentResolver(Base):
    inputs = {"symbols": get_type("AssetSymbolList")}
    outputs = {"resolved_symbols": get_type("AssetSymbolList")}
    default_params = {
        "exchange": "binance",
        "instrument_type": "PERPETUAL",
        "quote_currency": "USDT",
    }

    async def _execute_impl(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        symbols: List[AssetSymbol] = inputs.get("symbols", [])
        exchange = self.params.get("exchange")
        target_type = getattr(InstrumentType, self.params.get("instrument_type").upper())
        quote_currency = self.params.get("quote_currency")

        resolved = []
        for sym in symbols:
            if sym.asset_class != AssetClass.CRYPTO:
                resolved.append(sym)
                continue

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
                                instrument_type=target_type,
                                metadata={"contract_type": ex_sym["contractType"], "status": ex_sym["status"], "exchange": exchange},
                            )
                            resolved.append(resolved_sym)
                            break

        return {"resolved_symbols": resolved}


