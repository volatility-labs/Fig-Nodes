import logging
from typing import Any

import httpx

from core.api_key_vault import APIKeyVault
from core.types_registry import AssetSymbol, OHLCVBar, get_type
from nodes.core.market.filters.base.base_filter_node import BaseFilter

logger = logging.getLogger(__name__)


class IndustryFilter(BaseFilter):
    """
    Filters OHLCV bundles based on company industry from Massive.com API (formerly Polygon.io) Ticker Overview API.
    Uses sic_description for matching (e.g., 'Computer Programming Services').

    Note: Polygon.io has rebranded to Massive.com. The API endpoints have been updated
    to use api.massive.com, but the API routes remain unchanged.

    Requires Massive.com API key (POLYGON_API_KEY) from vault.
    """

    inputs = {"ohlcv_bundle": get_type("OHLCVBundle")}
    outputs = {"filtered_ohlcv_bundle": get_type("OHLCVBundle")}
    default_params = {
        "allowed_industries": [],  # List of sic_description strings to match (exact, case-insensitive)
        "date": None,  # Optional date for historical overview (YYYY-MM-DD)
    }
    params_meta = [
        {
            "name": "allowed_industries",
            "type": "combo",
            "default": [],
            "options": [],
            "description": "List of industry sic_description strings to match (exact, case-insensitive)",
        },
        {
            "name": "date",
            "type": "text",
            "default": None,
            "description": "Optional date for historical overview (YYYY-MM-DD)",
        },
    ]

    def __init__(
        self,
        id: int,
        params: dict[str, Any] | None = None,
        graph_context: dict[str, Any] | None = None,
    ):  # Changed from node_id: str
        super().__init__(id, params or {}, graph_context)
        allowed_industries_param = self.params.get("allowed_industries", [])
        if isinstance(allowed_industries_param, list):
            self.allowed_industries = [str(ind).lower() for ind in allowed_industries_param]
        else:
            self.allowed_industries = []

    async def _fetch_industry(self, symbol: AssetSymbol, api_key: str) -> str:
        """Fetch sic_description from Massive.com API (formerly Polygon.io)."""
        url = f"https://api.massive.com/v3/reference/tickers/{symbol.ticker}"
        params: dict[str, str] = {"apiKey": api_key}
        date_value = self.params.get("date")
        if date_value:
            params["date"] = str(date_value)

        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(url, params=params)
                response.raise_for_status()
                data = response.json()
                return data.get("results", {}).get("sic_description", "").lower()
            except Exception as e:
                logger.warning(f"Failed to fetch industry for {symbol}: {e}")
                return ""

    async def _filter_condition_async(
        self, symbol: AssetSymbol, ohlcv_data: list[OHLCVBar]
    ) -> bool:
        api_key = APIKeyVault().get("POLYGON_API_KEY")
        if not api_key:
            raise ValueError("Massive.com API key (POLYGON_API_KEY) not found in vault")

        industry = await self._fetch_industry(symbol, api_key)
        return industry in self.allowed_industries

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
                logger.warning(f"Failed to process filter for {symbol}: {e}")
                continue

        return {"filtered_ohlcv_bundle": filtered_bundle}
