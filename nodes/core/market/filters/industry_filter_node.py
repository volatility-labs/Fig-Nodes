import logging
import asyncio
import httpx
from typing import Dict, Any, List
from nodes.core.market.filters.base.base_filter_node import BaseFilterNode
from core.types_registry import get_type, AssetSymbol, OHLCVBar, APIKey

logger = logging.getLogger(__name__)


class IndustryFilterNode(BaseFilterNode):
    """
    Filters OHLCV bundles based on company industry from Polygon.io Ticker Overview API.
    Uses sic_description for matching (e.g., 'Computer Programming Services').
    Requires Polygon API key as input.
    """
    inputs = {
        "ohlcv_bundle": get_type("OHLCVBundle"),
        "api_key": get_type("APIKey")
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

    def __init__(self, node_id: str, params: Dict[str, Any]):
        super().__init__(node_id, params)
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

    def _filter_condition(self, symbol: AssetSymbol, ohlcv_data: List[OHLCVBar]) -> bool:
        api_key = self.inputs.get("api_key")  # Assuming API key is passed in execute inputs
        if not api_key:
            raise ValueError("API key required for industry filtering")

        # Run async fetch in sync context (use asyncio.run for simplicity, or make execute handle it)
        industry = asyncio.run(self._fetch_industry(symbol, api_key))
        return industry in self.allowed_industries
