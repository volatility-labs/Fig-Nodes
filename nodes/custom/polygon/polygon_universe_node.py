from typing import List, Dict, Any, Optional
import httpx
import logging
from nodes.base.base_node import Base
from core.types_registry import AssetSymbol, AssetClass, get_type
from core.api_key_vault import APIKeyVault

logger = logging.getLogger(__name__)

class PolygonUniverse(Base):
    inputs = {"filter_symbols": Optional[get_type("AssetSymbolList")]}
    outputs = {"symbols": get_type("AssetSymbolList")}
    required_keys = ["POLYGON_API_KEY"]
    uiModule = "PolygonUniverseNodeUI"
    params_meta = [
        {"name": "market", "type": "combo", "default": "stocks", "options": ["stocks", "crypto", "fx", "otc", "indices"], "label": "Market Type", "description": "Select the market type to fetch symbols from"},
        {"name": "min_change_perc", "type": "number", "default": None, "optional": True, "label": "Min Change", "unit": "%", "description": "Minimum daily percentage change (e.g., 5 for 5%)", "step": 0.01},
        {"name": "max_change_perc", "type": "number", "default": None, "optional": True, "label": "Max Change", "unit": "%", "description": "Maximum daily percentage change (e.g., 10 for 10%)", "step": 0.01},
        {"name": "min_volume", "type": "number", "default": None, "optional": True, "label": "Min Volume", "unit": "shares/contracts", "description": "Minimum daily trading volume in shares or contracts"},
        {"name": "min_price", "type": "number", "default": None, "optional": True, "label": "Min Price", "unit": "USD", "description": "Minimum closing price in USD"},
        {"name": "max_price", "type": "number", "default": None, "optional": True, "label": "Max Price", "unit": "USD", "description": "Maximum closing price in USD"},
        {"name": "include_otc", "type": "boolean", "default": False, "optional": True, "label": "Include OTC", "description": "Include over-the-counter symbols (stocks only)"},
    ]

    async def _execute_impl(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        print(f"DEBUG: PolygonUniverse node {self.id} starting execution")
        print(f"DEBUG: PolygonUniverse inputs: {list(inputs.keys())}")
        try:
            symbols = await self._fetch_symbols()
            print(f"DEBUG: PolygonUniverse fetched {len(symbols)} symbols")
            filter_symbols = self.collect_multi_input("filter_symbols", inputs)
            if filter_symbols:
                print(f"DEBUG: PolygonUniverse filtering with {len(filter_symbols)} filter symbols")
                filter_set = {str(s) for s in filter_symbols}
                symbols = [s for s in symbols if str(s) in filter_set]
                print(f"DEBUG: PolygonUniverse after filtering: {len(symbols)} symbols")
            print(f"DEBUG: PolygonUniverse node {self.id} completed successfully")
            return {"symbols": symbols}
        except Exception as e:
            print(f"ERROR_TRACE: Exception in PolygonUniverse node {self.id}: {type(e).__name__}: {str(e)}")
            logger.error(f"PolygonUniverse node {self.id} failed: {str(e)}", exc_info=True)
            raise

    async def _fetch_symbols(self) -> List[AssetSymbol]:
        print(f"DEBUG: PolygonUniverse fetching symbols for market: {self.params.get('market', 'stocks')}")
        api_key = APIKeyVault().get("POLYGON_API_KEY")
        if not api_key:
            print(f"ERROR_TRACE: POLYGON_API_KEY not found in vault")
            raise ValueError("POLYGON_API_KEY is required but not set in vault")
        print(f"DEBUG: PolygonUniverse API key found, length: {len(api_key)}")
        market = self.params.get("market", "stocks")

        if market == "stocks" or market == "otc":
            locale = "us"
            markets = "stocks"
        elif market == "indices":
            locale = "us"
            markets = "indices"
        else:
            locale = "global"
            markets = market

        base_url = f"https://api.polygon.io/v2/snapshot/locale/{locale}/markets/{markets}/tickers"
        params: Dict[str, Any] = {}
        if market == "otc" or (market == "stocks" and self.params.get("include_otc", False)):
            params["include_otc"] = True

        headers = {"Authorization": f"Bearer {api_key}"}
        symbols: List[AssetSymbol] = []
        print(f"DEBUG: PolygonUniverse making API request to: {base_url}")
        print(f"DEBUG: PolygonUniverse request params: {params}")
        async with httpx.AsyncClient() as client:
            response = await client.get(base_url, headers=headers, params=params)
            print(f"DEBUG: PolygonUniverse API response status: {response.status_code}")
            if response.status_code != 200:
                error_text = response.text if response.text else response.reason_phrase
                print(f"ERROR_TRACE: PolygonUniverse API error: {response.status_code} - {error_text}")
                raise ValueError(f"Failed to fetch snapshot: {response.status_code} - {error_text}")
            data = response.json()
            tickers_data = data.get("tickers", [])
            print(f"DEBUG: PolygonUniverse received {len(tickers_data)} tickers from API")

            min_change_perc = self.params.get("min_change_perc")
            max_change_perc = self.params.get("max_change_perc")
            min_volume = self.params.get("min_volume")
            min_price = self.params.get("min_price")
            max_price = self.params.get("max_price")

            # Validate change percentage range if both provided
            if min_change_perc is not None and max_change_perc is not None:
                assert isinstance(min_change_perc, (int, float)) and isinstance(max_change_perc, (int, float)), "Change bounds must be numeric"
                if min_change_perc > max_change_perc:
                    raise ValueError("min_change_perc cannot be greater than max_change_perc")

            for res in tickers_data:
                ticker = res["ticker"]

                # Apply filters
                todays_change_perc = res.get("todaysChangePerc", 0)
                if min_change_perc is not None and todays_change_perc < min_change_perc:
                    continue
                if max_change_perc is not None and todays_change_perc > max_change_perc:
                    continue

                day = res.get("day", {})
                volume = day.get("v", 0)
                if min_volume is not None and volume < min_volume:
                    continue

                price = day.get("c", 0)
                if min_price is not None and price < min_price:
                    continue
                if max_price is not None and price > max_price:
                    continue

                # Create AssetSymbol
                quote_currency = None
                base_ticker = ticker
                if market in ["crypto", "fx"] and ":" in ticker:
                    _, tick = ticker.split(":", 1)
                    if len(tick) > 3 and tick[-3:].isalpha() and tick[-3:].isupper():
                        base_ticker = tick[:-3]
                        quote_currency = tick[-3:]

                # Map market names to existing AssetClass values
                market_mapping = {
                    "crypto": AssetClass.CRYPTO,
                    "stocks": AssetClass.STOCKS,
                    "stock": AssetClass.STOCKS,
                }
                asset_class = market_mapping.get(market.lower(), AssetClass.STOCKS)

                metadata = {
                    "original_ticker": ticker,
                    "snapshot": res,
                }

                symbols.append(
                    AssetSymbol(
                        ticker=base_ticker,
                        asset_class=asset_class,
                        quote_currency=quote_currency,
                        metadata=metadata,
                    )
                )
        return symbols


