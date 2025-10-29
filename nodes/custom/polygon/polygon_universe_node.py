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
        {"name": "include_otc", "type": "combo", "default": False, "options": [True, False], "optional": True, "label": "Include OTC", "description": "Include over-the-counter symbols (stocks only)"},
        {"name": "include_etfs", "type": "combo", "default": False, "options": [True, False], "optional": True, "label": "Include ETFs", "description": "Include ETFs/ETPs (stocks only, default: exclude)"},
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
        include_etfs = self.params.get("include_etfs", False)
        include_otc = self.params.get("include_otc", False)

        # Use /v3/reference/tickers for proper type metadata
        base_url = "https://api.polygon.io/v3/reference/tickers"
        params: Dict[str, Any] = {
            "active": True,
            "limit": 1000,
            "apiKey": api_key
        }
        
        # Set market parameter
        if market == "stocks":
            params["market"] = "stocks"
        elif market == "otc":
            params["market"] = "otc"
        elif market == "crypto":
            params["market"] = "crypto"
        elif market == "fx":
            params["market"] = "fx"
        elif market == "indices":
            params["market"] = "indices"

        symbols: List[AssetSymbol] = []
        print(f"DEBUG: PolygonUniverse making API request to: {base_url}")
        print(f"DEBUG: PolygonUniverse request params: {params}")
        
        async with httpx.AsyncClient() as client:
            next_url = base_url
            page_count = 0
            total_fetched = 0
            
            while next_url and page_count < 10:  # Limit to 10 pages to avoid infinite loops
                if page_count > 0:
                    # Use next_url for pagination
                    response = await client.get(next_url + f"&apiKey={api_key}")
                else:
                    response = await client.get(base_url, params=params)
                
                print(f"DEBUG: PolygonUniverse API response status: {response.status_code}")
                if response.status_code != 200:
                    error_text = response.text if response.text else response.reason_phrase
                    print(f"ERROR_TRACE: PolygonUniverse API error: {response.status_code} - {error_text}")
                    raise ValueError(f"Failed to fetch tickers: {response.status_code} - {error_text}")
                
                data = response.json()
                tickers_data = data.get("results", [])
                total_fetched += len(tickers_data)
                print(f"DEBUG: PolygonUniverse received {len(tickers_data)} tickers on page {page_count + 1} (total: {total_fetched})")

                for res in tickers_data:
                    ticker = res.get("ticker", "")
                    if not ticker:
                        continue
                    
                    ticker_type = res.get("type", "")
                    ticker_market = res.get("market", "")
                    
                    # ETF filtering for stocks market
                    if market == "stocks" and not include_etfs:
                        # Check if this is an ETF using the type field
                        # Common ETF types: "ETF", "ETN", "ETP"
                        if ticker_type in ["ETF", "ETN", "ETP"] or "ETF" in ticker_type.upper() or "ETP" in ticker_type.upper():
                            print(f"DEBUG: Skipping ETF {ticker} (type: {ticker_type})")
                            continue
                    
                    # OTC filtering for stocks market
                    if market == "stocks" and not include_otc:
                        # Skip if ticker market is "otc"
                        if ticker_market == "otc" or ticker_market == "OTC":
                            print(f"DEBUG: Skipping OTC {ticker} (market: {ticker_market})")
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
                        "otc": AssetClass.STOCKS,
                    }
                    asset_class = market_mapping.get(market.lower(), AssetClass.STOCKS)

                    metadata = {
                        "original_ticker": ticker,
                        "ticker_details": res,
                    }

                    symbols.append(
                        AssetSymbol(
                            ticker=base_ticker,
                            asset_class=asset_class,
                            quote_currency=quote_currency,
                            metadata=metadata,
                        )
                    )
                
                # Check for pagination
                next_url = data.get("next_url")
                page_count += 1
                
                # Break if we've fetched enough
                if len(symbols) >= 1000:  # Reasonable limit
                    print(f"DEBUG: Reached symbol limit, stopping pagination")
                    break
        
        print(f"DEBUG: PolygonUniverse total symbols after filtering: {len(symbols)}")
        return symbols


