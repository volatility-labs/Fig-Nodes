from typing import Dict, Any
import httpx
import pandas as pd
import logging
from datetime import datetime
from nodes.base.base_node import BaseNode
from core.types_registry import get_type, AssetSymbol

logger = logging.getLogger(__name__)


class PolygonCustomBarsNode(BaseNode):
    ui_module = "PolygonCustomBarsNodeUI"
    """
    Fetches custom aggregate bars (OHLCV) for a symbol from Polygon.io
    """
    inputs = {"symbol": get_type("AssetSymbol"), "api_key": get_type("APIKey")}
    outputs = {"ohlcv": get_type("OHLCV")}
    default_params = {
        "multiplier": 1,
        "timespan": "day",
        "from_date": "",
        "to_date": "",
        "adjusted": True,
        "sort": "asc",
        "limit": 5000,
    }
    params_meta = [
        {"name": "multiplier", "type": "number", "default": 1, "min": 1, "step": 1},
        {"name": "timespan", "type": "combo", "default": "day", "options": ["minute", "hour", "day", "week", "month", "quarter", "year"]},
        {"name": "from_date", "type": "text", "default": ""},
        {"name": "to_date", "type": "text", "default": ""},
        {"name": "adjusted", "type": "combo", "default": True, "options": [True, False]},
        {"name": "sort", "type": "combo", "default": "asc", "options": ["asc", "desc"]},
        {"name": "limit", "type": "number", "default": 5000, "min": 1, "max": 50000, "step": 1},
    ]

    async def execute(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        symbol: AssetSymbol = inputs.get("symbol")
        if not symbol:
            raise ValueError("Symbol input is required")

        api_key = inputs.get("api_key")
        if not api_key:
            raise ValueError("Polygon API key input is required")

        multiplier = self.params.get("multiplier", 1)
        timespan = self.params.get("timespan", "day")
        from_date = self.params.get("from_date", "").strip()
        to_date = self.params.get("to_date", "").strip()
        adjusted = self.params.get("adjusted", True)
        sort = self.params.get("sort", "asc")
        limit = self.params.get("limit", 5000)

        if not from_date or not to_date:
            raise ValueError("Both from_date and to_date are required")

        # Construct API URL
        ticker = symbol.ticker.upper()
        url = f"https://api.polygon.io/v2/aggs/ticker/{ticker}/range/{multiplier}/{timespan}/{from_date}/{to_date}"
        params = {
            "adjusted": str(adjusted).lower(),
            "sort": sort,
            "limit": limit,
            "apiKey": api_key,  # Note: Polygon uses apiKey as query param
        }

        async with httpx.AsyncClient() as client:
            response = await client.get(url, params=params)
            if response.status_code != 200:
                logger.error(f"Polygon API error: {response.status_code} - {response.text}")
                raise ValueError(f"Failed to fetch bars: HTTP {response.status_code}")

            data = response.json()

            if data.get("status") != "OK":
                error_msg = data.get("error", "Unknown error")
                raise ValueError(f"Polygon API error: {error_msg}")

            results = data.get("results", [])
            if not results:
                # Return empty DataFrame with correct columns
                df = pd.DataFrame(columns=["open", "high", "low", "close", "volume"])
                df.index.name = "timestamp"
                return {"ohlcv": df}

            # Convert results to DataFrame
            bars = []
            for result in results:
                bar = {
                    "open": result["o"],
                    "high": result["h"],
                    "low": result["l"],
                    "close": result["c"],
                    "volume": result["v"],
                }
                # Add optional fields if present
                if "vw" in result:
                    bar["vw"] = result["vw"]  # Volume weighted average price
                if "n" in result:
                    bar["n"] = result["n"]  # Number of transactions

                bars.append(bar)

            df = pd.DataFrame(bars)
            df.index = pd.to_datetime([r["t"] for r in results], unit="ms", utc=True)
            df.index.name = "timestamp"

            return {"ohlcv": df}
