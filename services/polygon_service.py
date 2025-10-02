from typing import List, Dict, Any
import httpx
from datetime import datetime, timedelta
from core.types_registry import AssetSymbol, OHLCVBar

async def fetch_bars(symbol: AssetSymbol, api_key: str, params: Dict[str, Any]) -> List[OHLCVBar]:
    print(f"STOP_TRACE: fetch_bars started for {symbol}")
    multiplier = params.get("multiplier", 1)
    timespan = params.get("timespan", "day")
    lookback_period = params.get("lookback_period", "3 months")
    adjusted = params.get("adjusted", True)
    sort = params.get("sort", "asc")
    limit = params.get("limit", 5000)

    # Calculate date range (copied from PolygonCustomBarsNode._calculate_date_range)
    now = datetime.now()
    parts = lookback_period.split()
    if len(parts) != 2:
        raise ValueError(f"Invalid lookback period format: {lookback_period}")
    amount = int(parts[0])
    unit = parts[1].lower()
    if unit in ("day", "days"):
        from_date = now - timedelta(days=amount)
    elif unit in ("week", "weeks"):
        from_date = now - timedelta(weeks=amount)
    elif unit in ("month", "months"):
        from_date = now - timedelta(days=amount * 30)
    elif unit in ("year", "years"):
        from_date = now - timedelta(days=amount * 365)
    else:
        raise ValueError(f"Unsupported time unit: {unit}")
    to_date = now.strftime("%Y-%m-%d")
    from_date_str = from_date.strftime("%Y-%m-%d")

    # Construct API URL and fetch (copied from PolygonCustomBarsNode.execute)
    ticker = str(symbol)
    url = f"https://api.polygon.io/v2/aggs/ticker/{ticker}/range/{multiplier}/{timespan}/{from_date_str}/{to_date}"
    query_params = {
        "adjusted": str(adjusted).lower(),
        "sort": sort,
        "limit": limit,
        "apiKey": api_key,
    }

    # Use shorter timeout for better cancellation responsiveness
    timeout = httpx.Timeout(5.0, connect=2.0)  # 5s total, 2s connect
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            print(f"STOP_TRACE: Awaiting client.get for {symbol}")
            response = await client.get(url, params=query_params)
            print(f"STOP_TRACE: Completed client.get for {symbol}, status: {response.status_code}")
            if response.status_code != 200:
                raise ValueError(f"Failed to fetch bars: HTTP {response.status_code}")
            data = response.json()
            if data.get("status") not in ["OK", "DELAYED"]:
                raise ValueError(f"Polygon API error: {data.get('error', 'Unknown error')}")
            results = data.get("results", [])
            bars = []
            for result in results:
                bar = {
                    "timestamp": result["t"],
                    "open": result["o"],
                    "high": result["h"],
                    "low": result["l"],
                    "close": result["c"],
                    "volume": result["v"],
                }
                if "vw" in result:
                    bar["vw"] = result["vw"]
                if "n" in result:
                    bar["n"] = result["n"]
                if "otc" in result:
                    bar["otc"] = result["otc"]
                bars.append(bar)
            return bars
    except asyncio.CancelledError:
        print(f"STOP_TRACE: CancelledError caught in fetch_bars for {symbol}")
        # Re-raise immediately for proper cancellation propagation
        raise
    except Exception as e:
        print(f"STOP_TRACE: Exception in fetch_bars for {symbol}: {e}")
        # Wrap other exceptions but let CancelledError through immediately
        raise
