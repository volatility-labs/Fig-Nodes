from typing import Dict, Any
import asyncio
import requests
import logging
from nodes.base_node import BaseNode
from core.types_registry import get_type, AssetSymbol, AssetClass

logger = logging.getLogger(__name__)

class BinancePerpsUniverseNode(BaseNode):
    inputs = {}
    outputs = {"symbols": get_type("AssetSymbolList")}
    required_asset_class = AssetClass.CRYPTO

    async def execute(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        attempts = 0
        max_attempts = 5
        backoff = 1
        while attempts < max_attempts:
            response = await asyncio.to_thread(requests.get, "https://fapi.binance.com/fapi/v1/exchangeInfo")
            if response.status_code == 200:
                info = response.json()
                symbols = [
                    AssetSymbol(
                        ticker=sym["baseAsset"].upper(),
                        asset_class=AssetClass.CRYPTO,
                        quote_currency=sym.get("quoteAsset"),
                        exchange="binance",
                        metadata={"contract_type": sym.get("contractType"), "status": sym.get("status")}
                    )
                    for sym in info["symbols"]
                    if sym.get("quoteAsset") == "USDT" and sym.get("contractType") == "PERPETUAL" and sym.get("status") == "TRADING"
                ]
                return {"symbols": symbols}
            elif response.status_code == 429:
                logger.warning(f"Rate limit hit for exchange info. Retrying after {backoff} seconds...")
                await asyncio.sleep(backoff)
                backoff *= 2
            else:
                logger.error(f"Failed to fetch exchange info: HTTP {response.status_code} - {response.text}")
                return {"symbols": []}
            attempts += 1
        logger.error("Max attempts reached for exchange info. Giving up.")
        return {"symbols": []} 