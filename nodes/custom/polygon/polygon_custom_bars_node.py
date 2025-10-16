from typing import Dict, Any, List
import httpx
import logging
from datetime import datetime, timedelta
from nodes.base.base_node import Base
from core.types_registry import get_type, AssetSymbol, OHLCVBar
from core.api_key_vault import APIKeyVault
from services.polygon_service import fetch_bars

logger = logging.getLogger(__name__)


class PolygonCustomBars(Base):
    ui_module = "market/PolygonCustomBarsNodeUI"
    """
    Fetches custom aggregate bars (OHLCV) for a symbol from Polygon.io
    """
    inputs = {"symbol": get_type("AssetSymbol")}
    outputs = {"ohlcv": get_type("OHLCV")}
    default_params = {
        "multiplier": 1,
        "timespan": "day",
        "lookback_period": "3 months",
        "adjusted": True,
        "sort": "asc",
        "limit": 5000,
    }
    params_meta = [
        {"name": "multiplier", "type": "number", "default": 1, "min": 1, "step": 1},
        {"name": "timespan", "type": "combo", "default": "day", "options": ["minute", "hour", "day", "week", "month", "quarter", "year"]},
        {"name": "lookback_period", "type": "combo", "default": "3 months", "options": ["1 day", "3 days", "1 week", "2 weeks", "1 month", "2 months", "3 months", "4 months", "6 months", "9 months", "1 year", "18 months", "2 years", "3 years", "5 years", "10 years"]},
        {"name": "adjusted", "type": "combo", "default": True, "options": [True, False]},
        {"name": "sort", "type": "combo", "default": "asc", "options": ["asc", "desc"]},
        {"name": "limit", "type": "number", "default": 5000, "min": 1, "max": 50000, "step": 1},
    ]

    async def _execute_impl(self, inputs: Dict[str, Any]) -> Dict[str, List[OHLCVBar]]:
        symbol: AssetSymbol = inputs.get("symbol")
        if not symbol:
            raise ValueError("Symbol input is required")

        api_key = APIKeyVault().get("POLYGON_API_KEY")
        if not api_key:
            raise ValueError("Polygon API key not found in vault")

        bars = await fetch_bars(symbol, api_key, self.params)
        return {"ohlcv": bars}
