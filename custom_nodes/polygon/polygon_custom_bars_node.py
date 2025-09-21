from typing import Dict, Any, List
import httpx
import logging
from datetime import datetime, timedelta
from nodes.base.base_node import BaseNode
from core.types_registry import get_type, AssetSymbol, OHLCVBar

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

    def _calculate_date_range(self, lookback_period: str) -> tuple[str, str]:
        """Calculate from_date and to_date based on lookback period."""
        now = datetime.now()

        # Parse lookback period
        parts = lookback_period.split()
        if len(parts) != 2:
            raise ValueError(f"Invalid lookback period format: {lookback_period}")

        amount = int(parts[0])
        unit = parts[1].lower()

        # Calculate from_date
        if unit == "day" or unit == "days":
            from_date = now - timedelta(days=amount)
        elif unit == "week" or unit == "weeks":
            from_date = now - timedelta(weeks=amount)
        elif unit == "month" or unit == "months":
            # Approximate months as 30 days
            from_date = now - timedelta(days=amount * 30)
        elif unit == "year" or unit == "years":
            # Approximate years as 365 days
            from_date = now - timedelta(days=amount * 365)
        else:
            raise ValueError(f"Unsupported time unit: {unit}")

        # Format dates as YYYY-MM-DD
        to_date = now.strftime("%Y-%m-%d")
        from_date_str = from_date.strftime("%Y-%m-%d")

        return from_date_str, to_date

    async def execute(self, inputs: Dict[str, Any]) -> Dict[str, List[OHLCVBar]]:
        symbol: AssetSymbol = inputs.get("symbol")
        if not symbol:
            raise ValueError("Symbol input is required")

        api_key = inputs.get("api_key")
        if not api_key:
            raise ValueError("Polygon API key input is required")

        multiplier = self.params.get("multiplier", 1)
        timespan = self.params.get("timespan", "day")
        lookback_period = self.params.get("lookback_period", "3 months")
        adjusted = self.params.get("adjusted", True)
        sort = self.params.get("sort", "asc")
        limit = self.params.get("limit", 5000)

        # Calculate date range based on lookback period
        from_date, to_date = self._calculate_date_range(lookback_period)

        # Construct API URL
        ticker = str(symbol)
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

            if data.get("status") not in ["OK", "DELAYED"]:
                error_msg = data.get("error", "Unknown error")
                raise ValueError(f"Polygon API error: {error_msg}")

            results = data.get("results", [])
            if not results:
                # Return empty list
                return {"ohlcv": []}

            # Convert results to list of dictionaries
            bars = []
            for result in results:
                bar = {
                    "timestamp": result["t"],  # Unix timestamp in milliseconds
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
                if "otc" in result:
                    bar["otc"] = result["otc"]  # OTC ticker flag

                bars.append(bar)

            return {"ohlcv": bars}
