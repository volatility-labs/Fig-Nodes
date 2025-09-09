from typing import List
import httpx
import logging
from nodes.base.universe_node import UniverseNode
from core.types_registry import AssetSymbol, AssetClass, register_asset_class

logger = logging.getLogger(__name__)


class PolygonUniverseNode(UniverseNode):
    params_meta = [
        {"name": "api_key", "type": "text", "default": ""},
        {"name": "market", "type": "combo", "default": "stocks", "options": ["stocks", "crypto", "fx", "otc", "indices"]},
    ]

    async def _fetch_symbols(self) -> List[AssetSymbol]:
        api_key = self.params.get("api_key")
        if not api_key:
            raise ValueError("Polygon API key is required")
        market = self.params.get("market", "stocks")
        if not hasattr(AssetClass, market.upper()):
            register_asset_class(market)
        asset_class = getattr(AssetClass, market.upper())
        base_url = "https://api.polygon.io/v3/reference/tickers"
        headers = {"Authorization": f"Bearer {api_key}"}
        params = {
            "market": market,
            "active": "true",
            "limit": 1000,
            "sort": "ticker",
            "order": "asc",
        }
        symbols: List[AssetSymbol] = []
        async with httpx.AsyncClient() as client:
            next_url = base_url
            while next_url:
                if next_url == base_url:
                    response = await client.get(next_url, headers=headers, params=params)
                else:
                    response = await client.get(next_url, headers=headers)
                if response.status_code != 200:
                    logger.error(f"Failed to fetch tickers: {response.status_code} - {response.text}")
                    break
                data = response.json()
                for res in data.get("results", []):
                    ticker = res["ticker"]
                    quote_currency = None
                    base_ticker = ticker
                    if market in ["crypto", "fx"] and ":" in ticker:
                        _, tick = ticker.split(":", 1)
                        if len(tick) > 3 and tick[-3:].isalpha():
                            base_ticker = tick[:-3]
                            quote_currency = tick[-3:]
                    symbols.append(
                        AssetSymbol(
                            ticker=base_ticker,
                            asset_class=asset_class,
                            quote_currency=quote_currency,
                            exchange=res.get("primary_exchange"),
                            metadata={
                                "name": res.get("name"),
                                "currency_name": res.get("currency_name"),
                                "locale": res.get("locale"),
                                "cik": res.get("cik"),
                                "composite_figi": res.get("composite_figi"),
                                "share_class_figi": res.get("share_class_figi"),
                                "original_ticker": ticker,
                            },
                        )
                    )
                next_url = data.get("next_url")
        return symbols


