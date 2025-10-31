import asyncio
import logging
from datetime import datetime, timedelta
from typing import Any

import httpx
import pytz

from core.types_registry import AssetClass, AssetSymbol, OHLCVBar

logger = logging.getLogger(__name__)


async def fetch_bars(symbol: AssetSymbol, api_key: str, params: dict[str, Any]) -> list[OHLCVBar]:
    """
    Fetches OHLCV bars for a symbol from Massive.com API (formerly Polygon.io).

    Note: Polygon.io has rebranded to Massive.com. The API endpoints have been updated
    to use api.massive.com, but the API routes remain unchanged.

    For crypto symbols, automatically adds "X:" prefix to the ticker (e.g., BTCUSD -> X:BTCUSD)
    as required by the Massive.com crypto aggregates API.

    Args:
        symbol: AssetSymbol to fetch bars for
        api_key: API key for Massive.com (POLYGON_API_KEY)
        params: Parameters including multiplier, timespan, lookback_period, etc.

    Returns:
        List of OHLCVBar objects
    """
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
    # Add "X:" prefix for crypto tickers as required by Massive.com API
    if symbol.asset_class == AssetClass.CRYPTO:
        ticker = f"X:{ticker}"
    url = f"https://api.massive.com/v2/aggs/ticker/{ticker}/range/{multiplier}/{timespan}/{from_date_str}/{to_date}"
    query_params = {
        "adjusted": str(adjusted).lower(),
        "sort": sort,
        "limit": limit,
        "apiKey": api_key,
    }

    # Use shorter timeout for better cancellation responsiveness
    timeout = httpx.Timeout(5.0, connect=2.0)  # 5s total, 2s connect

    current_time_utc = datetime.now(pytz.timezone("UTC"))
    current_time_et = current_time_utc.astimezone(pytz.timezone("US/Eastern"))

    logger.info("=" * 80)
    logger.info(f"POLYGON_SERVICE: Fetching bars for {symbol.ticker} ({symbol.asset_class})")
    logger.info(f"POLYGON_SERVICE: Request time (UTC): {current_time_utc}")
    logger.info(f"POLYGON_SERVICE: Request time (ET): {current_time_et}")
    logger.info(f"POLYGON_SERVICE: Date range: {from_date_str} to {to_date}")
    logger.info(
        f"POLYGON_SERVICE: Parameters: multiplier={multiplier}, timespan={timespan}, limit={limit}"
    )
    logger.info("=" * 80)

    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.get(url, params=query_params)
            print(f"STOP_TRACE: Completed client.get for {symbol}, status: {response.status_code}")
            logger.info(f"POLYGON_SERVICE: HTTP response status: {response.status_code}")

            if response.status_code != 200:
                logger.error(
                    f"POLYGON_SERVICE: HTTP error {response.status_code} for {symbol.ticker}"
                )
                raise ValueError(f"Failed to fetch bars: HTTP {response.status_code}")

            data = response.json()
            api_status = data.get("status")
            results_count = data.get("resultsCount", 0)

            logger.info("=" * 80)
            logger.info(f"POLYGON_SERVICE: API Response Status: {api_status}")
            logger.info(f"POLYGON_SERVICE: Results Count: {results_count}")

            if api_status == "DELAYED":
                logger.warning(
                    f"POLYGON_SERVICE: ⚠️ DELAYED DATA for {symbol.ticker} - Data may be delayed"
                )
            elif api_status == "OK":
                logger.info(
                    f"POLYGON_SERVICE: ✅ REAL-TIME DATA for {symbol.ticker} - Data is current"
                )
            else:
                logger.warning(
                    f"POLYGON_SERVICE: ⚠️ Unknown status '{api_status}' for {symbol.ticker}"
                )

            if data.get("status") not in ["OK", "DELAYED"]:
                error_msg = data.get("error", "Unknown error")
                logger.error(f"POLYGON_SERVICE: API error for {symbol.ticker}: {error_msg}")
                raise ValueError(f"Massive.com API error: {error_msg}")

            results = data.get("results", [])
            bars: list[OHLCVBar] = []

            if not results:
                logger.warning(f"POLYGON_SERVICE: No bars returned for {symbol.ticker}")
            else:
                logger.info(f"POLYGON_SERVICE: Processing {len(results)} bars for {symbol.ticker}")

                # Track timestamps for delay analysis
                timestamps_ms: list[int] = []
                for result in results:
                    if not isinstance(result, dict):
                        continue
                    timestamp_ms = result["t"]
                    if isinstance(timestamp_ms, int):
                        timestamps_ms.append(timestamp_ms)
                    bar: OHLCVBar = {
                        "timestamp": timestamp_ms,
                        "open": result["o"],
                        "high": result["h"],
                        "low": result["l"],
                        "close": result["c"],
                        "volume": result["v"],
                    }
                    bars.append(bar)

                if timestamps_ms:
                    # Convert timestamps to ET for analysis
                    from services.time_utils import utc_timestamp_ms_to_et_datetime

                    first_bar_time = utc_timestamp_ms_to_et_datetime(min(timestamps_ms))
                    last_bar_time = utc_timestamp_ms_to_et_datetime(max(timestamps_ms))

                    # Calculate delay from latest bar to current time
                    time_diff = current_time_et - last_bar_time
                    delay_minutes = time_diff.total_seconds() / 60

                    logger.info("=" * 80)
                    logger.info(f"POLYGON_SERVICE: Bar Timestamp Analysis for {symbol.ticker}")
                    logger.info(f"POLYGON_SERVICE: First bar timestamp (ET): {first_bar_time}")
                    logger.info(f"POLYGON_SERVICE: Last bar timestamp (ET): {last_bar_time}")
                    logger.info(f"POLYGON_SERVICE: Current time (ET): {current_time_et}")
                    logger.info(f"POLYGON_SERVICE: Time difference: {time_diff}")
                    logger.info(f"POLYGON_SERVICE: Delay (minutes): {delay_minutes:.2f}")

                    if delay_minutes < 5:
                        logger.info(
                            "POLYGON_SERVICE: ✅ Data appears REAL-TIME (delay < 5 minutes)"
                        )
                    elif delay_minutes < 15:
                        logger.warning(
                            f"POLYGON_SERVICE: ⚠️ Data appears SLIGHTLY DELAYED (delay {delay_minutes:.2f} minutes)"
                        )
                    else:
                        logger.warning(
                            f"POLYGON_SERVICE: ⚠️ Data appears SIGNIFICANTLY DELAYED (delay {delay_minutes:.2f} minutes)"
                        )

                    logger.info(f"POLYGON_SERVICE: Total bars processed: {len(bars)}")
                    logger.info("=" * 80)

            return bars
    except asyncio.CancelledError:
        print(f"STOP_TRACE: CancelledError caught in fetch_bars for {symbol}")
        # Re-raise immediately for proper cancellation propagation
        raise
    except Exception as e:
        print(f"STOP_TRACE: Exception in fetch_bars for {symbol}: {e}")
        # Wrap other exceptions but let CancelledError through immediately
        raise
