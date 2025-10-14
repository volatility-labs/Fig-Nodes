import logging
import asyncio
import httpx
from typing import Dict, Any, List
from nodes.core.market.filters.base.base_filter_node import BaseFilterNode
from core.types_registry import get_type, AssetSymbol, OHLCVBar
from core.api_key_vault import APIKeyVault

logger = logging.getLogger(__name__)


class IndustryFilterNode(BaseFilterNode):
    """
    Filters OHLCV bundles based on company industry from Polygon.io Ticker Overview API.
    Uses sic_description for matching (e.g., 'Computer Programming Services').
    Requires Polygon API key from vault.
    """
    inputs = {
        "ohlcv_bundle": get_type("OHLCVBundle")
    }
    outputs = {"filtered_ohlcv_bundle": get_type("OHLCVBundle")}
    default_params = {
        "allowed_industries": [],  # List of sic_description strings to match (exact, case-insensitive)
        "date": None  # Optional date for historical overview (YYYY-MM-DD)
    }
    params_meta = [
        {"name": "allowed_industries", "type": "combo", "default": [], "options": [], "multiple": True},  # UI can populate common industries
        {"name": "date", "type": "string", "default": None}
    ]

    def __init__(self, id: int, params: Dict[str, Any] = None):  # Changed from node_id: str
        super().__init__(id, params)
        self.allowed_industries = [ind.lower() for ind in self.params.get("allowed_industries", [])]

    async def _fetch_industry(self, symbol: AssetSymbol, api_key: str) -> str:
        """Fetch sic_description from Polygon API."""
        url = f"https://api.polygon.io/v3/reference/tickers/{symbol.ticker}"
        params = {"apiKey": api_key}
        if self.params.get("date"):
            params["date"] = self.params["date"]

        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(url, params=params)
                response.raise_for_status()
                data = response.json()
                return data.get("results", {}).get("sic_description", "").lower()
            except Exception as e:
                logger.warning(f"Failed to fetch industry for {symbol}: {e}")
                return ""

    async def _filter_condition_async(self, symbol: AssetSymbol, ohlcv_data: List[OHLCVBar]) -> bool:
        api_key = APIKeyVault().get("POLYGON_API_KEY")
        if not api_key:
            raise ValueError("Polygon API key not found in vault")

        industry = await self._fetch_industry(symbol, api_key)
        return industry in self.allowed_industries

    async def _execute_impl(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        ohlcv_bundle: Dict[AssetSymbol, List[OHLCVBar]] = inputs.get("ohlcv_bundle", {})

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
                logger.warning(f"Failed to process filter for {symbol}: {e}")
                continue

        return {"filtered_ohlcv_bundle": filtered_bundle}
