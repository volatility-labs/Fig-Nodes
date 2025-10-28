import logging
from typing import Any

import httpx

from core.api_key_vault import APIKeyVault
from core.types_registry import AssetSymbol, NodeCategory, OHLCVBar, get_type
from nodes.core.market.filters.base.base_filter_node import BaseFilter

logger = logging.getLogger(__name__)


class ETFFilter(BaseFilter):
    CATEGORY = NodeCategory.MARKET
    """
    Filters ETFs out of OHLCV bundles to keep only stocks.
    
    Checks ticker details from Polygon.io API to determine if an asset is an ETF.
    Only keeps non-ETF assets in the output.
    """

    inputs = {"ohlcv_bundle": get_type("OHLCVBundle")}
    outputs = {"filtered_ohlcv_bundle": get_type("OHLCVBundle")}
    default_params = {
        "exclude_etfs": True,  # True = filter out ETFs, False = keep only ETFs
    }
    params_meta = [
        {
            "name": "exclude_etfs",
            "type": "combo",
            "default": True,
            "options": [True, False],
            "label": "Exclude ETFs",
            "description": "If true, filters out ETFs (keeps only stocks). If false, keeps only ETFs.",
        },
    ]

    def __init__(self, id: int, params: dict[str, Any] | None = None):
        super().__init__(id, params or {})
        self.exclude_etfs = self.params.get("exclude_etfs", True)

    async def _is_etf(self, symbol: AssetSymbol, api_key: str) -> bool:
        """Check if symbol is an ETF using Polygon API."""
        url = f"https://api.polygon.io/v3/reference/tickers/{symbol.ticker}"
        params: dict[str, str] = {"apiKey": api_key}

        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(url, params=params)
                response.raise_for_status()
                data = response.json()
                results = data.get("results", {})
                
                # Check multiple fields that indicate ETF status
                market_type = results.get("market", "")
                type_field = results.get("type", "")
                asset_type = results.get("asset_class", "")
                
                # Common ETF indicators in Polygon API
                is_etf = (
                    market_type == "etp" or  # Exchange Traded Product
                    type_field == "ETF" or
                    "etf" in market_type.lower() or
                    "etf" in type_field.lower()
                )
                
                return is_etf
            except Exception as e:
                logger.warning(f"Failed to fetch ETF status for {symbol}: {e}")
                # If we can't determine, default behavior: exclude from results
                return self.exclude_etfs

    async def _filter_condition_async(
        self, symbol: AssetSymbol, ohlcv_data: list[OHLCVBar]
    ) -> bool:
        api_key = APIKeyVault().get("POLYGON_API_KEY")
        if not api_key:
            raise ValueError("Polygon API key not found in vault")

        is_etf = await self._is_etf(symbol, api_key)
        
        # If exclude_etfs is True, pass filter when NOT an ETF
        # If exclude_etfs is False, pass filter when IS an ETF
        return not is_etf if self.exclude_etfs else is_etf

    async def _execute_impl(self, inputs: dict[str, Any]) -> dict[str, Any]:
        ohlcv_bundle: dict[AssetSymbol, list[OHLCVBar]] = inputs.get("ohlcv_bundle", {})

        if not ohlcv_bundle:
            return {"filtered_ohlcv_bundle": {}}

        filtered_bundle = {}

        for symbol, ohlcv_data in ohlcv_bundle.items():
            if not ohlcv_data:
                continue

            try:
                if await self._filter_condition_async(symbol, ohlcv_data):
                    filtered_bundle[symbol] = ohlcv_data
            except Exception as e:
                logger.error(f"Error filtering ETF for {symbol}: {e}")
                # Skip this symbol on error
                continue

        return {"filtered_ohlcv_bundle": filtered_bundle}

