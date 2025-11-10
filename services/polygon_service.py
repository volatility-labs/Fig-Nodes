import asyncio
import json
import logging
from datetime import datetime, timedelta
from typing import Any, cast

import httpx
import pytz

from core.types_registry import AssetClass, AssetSymbol, OHLCVBar

logger = logging.getLogger(__name__)


async def fetch_bars(
    symbol: AssetSymbol, api_key: str, params: dict[str, Any]
) -> tuple[list[OHLCVBar], dict[str, Any]]:
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
        Tuple of (list of OHLCVBar objects, metadata dict with data_status)
        metadata contains:
        - data_status: "real-time", "delayed", or "market-closed"
        - api_status: "OK" or "DELAYED" from API response
        - market_open: bool indicating if US market is open
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

    # Prefer millisecond timestamps for more precise, up-to-now queries
    to_ms = int(now.timestamp() * 1000)
    from_ms = int(from_date.timestamp() * 1000)

    # Construct API URL and fetch (copied from PolygonCustomBarsNode.execute)
    ticker = str(symbol)
    # Add "X:" prefix for crypto tickers as required by Massive.com API
    if symbol.asset_class == AssetClass.CRYPTO:
        ticker = f"X:{ticker}"
    url = f"https://api.massive.com/v2/aggs/ticker/{ticker}/range/{multiplier}/{timespan}/{from_ms}/{to_ms}"
    query_params = {
        "adjusted": str(adjusted).lower(),
        "sort": sort,
        "limit": limit,
        "apiKey": api_key,
    }

    # Use shorter timeout for better cancellation responsiveness
    timeout = httpx.Timeout(10.0, connect=5.0)  # modestly higher to reduce spurious timeouts

    current_time_utc = datetime.now(pytz.timezone("UTC"))
    current_time_et = current_time_utc.astimezone(pytz.timezone("US/Eastern"))

    logger.info("=" * 80)
    logger.info(f"POLYGON_SERVICE: Fetching bars for {symbol.ticker} ({symbol.asset_class})")
    logger.info(f"POLYGON_SERVICE: Request time (UTC): {current_time_utc}")
    logger.info(f"POLYGON_SERVICE: Request time (ET): {current_time_et}")
    logger.info(f"POLYGON_SERVICE: Date range (ms): {from_ms} to {to_ms}")
    logger.info(
        f"POLYGON_SERVICE: Parameters: multiplier={multiplier}, timespan={timespan}, limit={limit}"
    )
    logger.info("=" * 80)

    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            # simple retry for transient connect timeouts
            response: httpx.Response | None = None
            for attempt in range(2):
                try:
                    response = await client.get(url, params=query_params)
                    break
                except httpx.ConnectTimeout:
                    if attempt == 1:
                        raise
                    await asyncio.sleep(0.5)
            if response is None:
                raise RuntimeError("No response received from Massive aggregates endpoint")

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

            # Determine data status based on market state and API status
            from services.time_utils import is_us_market_open

            # Crypto trades 24/7; always treat as open
            if symbol.asset_class == AssetClass.CRYPTO:
                market_is_open = True
            else:
                market_is_open = is_us_market_open()

            if not market_is_open:
                data_status = "market-closed"
            elif api_status == "OK":
                data_status = "real-time"
            elif api_status == "DELAYED":
                data_status = "delayed"
            else:
                data_status = "unknown"

            metadata = {
                "data_status": data_status,
                "api_status": api_status,
                "market_open": market_is_open,
            }

            results = data.get("results", [])
            bars: list[OHLCVBar] = []
            
            # Track if we need to append current bar from snapshot
            needs_current_bar = False
            current_bar_dict: OHLCVBar | None = None

            if not results:
                logger.warning(f"POLYGON_SERVICE: No bars returned for {symbol.ticker}")
                
                # For crypto symbols, try snapshot fallback when no aggregates available
                if symbol.asset_class == AssetClass.CRYPTO and timespan == "minute":
                    logger.info(f"POLYGON_SERVICE: Attempting snapshot fallback for crypto {symbol.ticker}")
                    
                    try:
                        snapshot_bars, snapshot_metadata = await create_current_bar_from_snapshot(symbol, api_key)
                        if snapshot_bars:
                            logger.info(f"POLYGON_SERVICE: ✅ Using snapshot fallback for {symbol.ticker}")
                            # Merge metadata
                            metadata.update(snapshot_metadata)
                            return snapshot_bars, metadata
                        else:
                            logger.warning(f"POLYGON_SERVICE: Snapshot fallback also failed for {symbol.ticker}")
                    except Exception as e:
                        logger.error(f"POLYGON_SERVICE: Snapshot fallback error for {symbol.ticker}: {e}")
            else:
                logger.info(f"POLYGON_SERVICE: Processing {len(results)} bars for {symbol.ticker}")
                
                # Check if the latest bar is too old for crypto (more than 30 minutes)
                # We'll fill in missing intervals with snapshot data to keep bars recent
                if results and symbol.asset_class == AssetClass.CRYPTO and timespan == "minute":
                    # Determine which bar is most recent based on sort order
                    sort_order = params.get("sort", "asc")
                    if sort_order == "desc":
                        latest_bar = results[0]  # Most recent is first
                    else:
                        latest_bar = results[-1]  # Most recent is last
                    
                    latest_timestamp_ms = latest_bar.get("t", 0)
                    if isinstance(latest_timestamp_ms, int):
                        # Convert timestamp to datetime for comparison
                        latest_time_utc = datetime.fromtimestamp(latest_timestamp_ms / 1000, tz=pytz.UTC)
                        current_time_utc = datetime.now(pytz.UTC)
                        age_minutes = (current_time_utc - latest_time_utc).total_seconds() / 60
                        
                        logger.info(f"POLYGON_SERVICE: Latest bar for {symbol.ticker} is {age_minutes:.1f} minutes old")
                        
                        if age_minutes > 30:  # If latest bar is more than 30 minutes old
                            logger.warning(f"POLYGON_SERVICE: Latest bar for {symbol.ticker} is {age_minutes:.1f} minutes old, filling missing intervals with snapshot")
                            
                            try:
                                # Get current price from snapshot
                                current_price, snapshot_metadata = await fetch_current_snapshot(symbol, api_key)
                                
                                if current_price is not None:
                                    # Calculate interval based on multiplier (1min, 5min, 15min, 30min)
                                    interval_minutes = multiplier
                                    
                                    # Round current time down to the nearest interval
                                    # e.g., if it's 5:37 PM and using 5min bars, round to 5:35 PM
                                    current_minute = current_time_utc.minute
                                    rounded_minute = (current_minute // interval_minutes) * interval_minutes
                                    rounded_time = current_time_utc.replace(minute=rounded_minute, second=0, microsecond=0)
                                    
                                    # Create bar at the rounded interval timestamp
                                    current_bar_dict = {
                                        "timestamp": int(rounded_time.timestamp() * 1000),
                                        "open": current_price,
                                        "high": current_price,
                                        "low": current_price,
                                        "close": current_price,
                                        "volume": 0.0,
                                    }
                                    needs_current_bar = True
                                    logger.info(f"POLYGON_SERVICE: ✅ Will append current snapshot bar for {symbol.ticker} at interval {rounded_time.strftime('%Y-%m-%d %H:%M:%S UTC')}")
                                else:
                                    logger.warning(f"POLYGON_SERVICE: Could not get current price for {symbol.ticker} from snapshot")
                            except Exception as e:
                                logger.error(f"POLYGON_SERVICE: Snapshot injection error for {symbol.ticker}: {e}", exc_info=True)
                                # Continue with stale bars if fallback fails

                # Track timestamps for delay analysis
                timestamps_ms: list[int] = []
                for result_item in results:
                    if not isinstance(result_item, dict):
                        continue
                    result_dict = cast(dict[str, Any], result_item)
                    ts_val = result_dict.get("t")
                    if not isinstance(ts_val, int):
                        continue
                    timestamp_ms = ts_val
                    timestamps_ms.append(timestamp_ms)
                    bar: OHLCVBar = {
                        "timestamp": timestamp_ms,
                        "open": float(result_dict.get("o", 0.0)),
                        "high": float(result_dict.get("h", 0.0)),
                        "low": float(result_dict.get("l", 0.0)),
                        "close": float(result_dict.get("c", 0.0)),
                        "volume": float(result_dict.get("v", 0.0)),
                    }
                    bars.append(bar)

                # Append current bar from snapshot if latest aggregate bar is too old
                if needs_current_bar and current_bar_dict:
                    # Determine correct position based on sort order
                    sort_order = params.get("sort", "asc")
                    if sort_order == "desc":
                        # For descending sort, prepend to make it the newest (first)
                        bars.insert(0, current_bar_dict)
                        logger.info(f"POLYGON_SERVICE: ✅ Prepended current snapshot bar (newest) to {len(bars)} total bars for {symbol.ticker}")
                    else:
                        # For ascending sort, append to make it the newest (last)
                        bars.append(current_bar_dict)
                        logger.info(f"POLYGON_SERVICE: ✅ Appended current snapshot bar (newest) to {len(bars)} total bars for {symbol.ticker}")
                    
                    # Log the timestamp of the appended bar for debugging
                    appended_timestamp = current_bar_dict["timestamp"]
                    appended_time = datetime.fromtimestamp(appended_timestamp / 1000, tz=pytz.UTC)
                    logger.info(f"POLYGON_SERVICE: Appended bar timestamp: {appended_time.strftime('%Y-%m-%d %H:%M:%S UTC')}")
                    
                    # Log the total bars and timestamps for verification
                    if sort_order == "desc":
                        newest_bar = bars[0]
                    else:
                        newest_bar = bars[-1]
                    newest_ts = newest_bar["timestamp"]
                    newest_time = datetime.fromtimestamp(newest_ts / 1000, tz=pytz.UTC)
                    logger.info(f"POLYGON_SERVICE: Total bars after append: {len(bars)}, newest bar time: {newest_time.strftime('%Y-%m-%d %H:%M:%S UTC')}")

                # Include appended bar timestamp in analysis if present
                if needs_current_bar and current_bar_dict:
                    appended_ts = current_bar_dict["timestamp"]
                    timestamps_ms.append(appended_ts)
                
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
                        # Override status if delay suggests real-time but API says delayed
                        if api_status == "DELAYED" and delay_minutes < 5:
                            data_status = "real-time"
                    elif delay_minutes < 15:
                        logger.warning(
                            f"POLYGON_SERVICE: ⚠️ Data appears SLIGHTLY DELAYED (delay {delay_minutes:.2f} minutes)"
                        )
                        # Override status based on actual delay if significant
                        if delay_minutes >= 15:
                            data_status = "delayed"
                    else:
                        logger.warning(
                            f"POLYGON_SERVICE: ⚠️ Data appears SIGNIFICANTLY DELAYED (delay {delay_minutes:.2f} minutes)"
                        )
                        # Always mark as delayed if delay is significant, regardless of API status
                        data_status = "delayed"

                    # Update metadata with refined status based on actual delay
                    metadata["data_status"] = data_status
                    logger.info(
                        f"POLYGON_SERVICE: Final data status: {data_status} (API status: {api_status})"
                    )

                    logger.info(f"POLYGON_SERVICE: Total bars processed: {len(bars)}")
                    logger.info("=" * 80)

            return bars, metadata

    except asyncio.CancelledError:
        print(f"STOP_TRACE: CancelledError caught in fetch_bars for {symbol}")
        # Re-raise immediately for proper cancellation propagation
        raise
    except Exception as e:
        print(f"STOP_TRACE: Exception in fetch_bars for {symbol}: {e}")
        # Wrap other exceptions but let CancelledError through immediately
        raise


# -------------------------- Massive.com Helpers ---------------------------


def massive_build_snapshot_tickers(filter_symbols: list[AssetSymbol]) -> list[str]:
    tickers: list[str] = []
    for sym in filter_symbols:
        if sym.asset_class == AssetClass.CRYPTO:
            tickers.append(f"X:{str(sym)}")
        else:
            tickers.append(sym.ticker.upper())
    return tickers


def massive_get_numeric_from_dict(data: dict[str, Any], key: str, default: float) -> float:
    value = data.get(key, default)
    if isinstance(value, int | float):
        return float(value)
    return default


def massive_parse_ticker_for_market(ticker: str, market: str) -> tuple[str, str | None]:
    if market not in ["crypto", "fx"] or ":" not in ticker:
        return ticker, None
    _, tick = ticker.split(":", 1)
    if len(tick) > 3 and tick[-3:].isalpha() and tick[-3:].isupper():
        return tick[:-3], tick[-3:]
    return ticker, None


def massive_compute_closed_change_perc(
    prev_day: dict[str, Any], last_trade: dict[str, Any]
) -> tuple[float, float | None]:
    prev_close = massive_get_numeric_from_dict(prev_day, "c", 0.0)
    last_trade_price = massive_get_numeric_from_dict(last_trade, "p", 0.0)
    price = last_trade_price if last_trade_price > 0 else prev_close
    change_perc = None
    if last_trade_price > 0 and prev_close > 0:
        change_perc = ((last_trade_price - prev_close) / prev_close) * 100.0
    return price, change_perc


async def massive_fetch_ticker_types(client: httpx.AsyncClient, api_key: str) -> set[str]:
    url = "https://api.massive.com/v3/reference/tickers/types"
    params: dict[str, str] = {"apiKey": api_key}
    try:
        response = await client.get(url, params=params)
        response.raise_for_status()
        data = response.json()
        results = data.get("results", [])
        etf_type_codes: set[str] = set()
        for item in results:
            if not isinstance(item, dict):
                continue
            item_dict: dict[str, Any] = item
            code_raw: Any = item_dict.get("code")
            desc_raw: Any = item_dict.get("description")
            code = code_raw if isinstance(code_raw, str) else ""
            description = desc_raw.lower() if isinstance(desc_raw, str) else ""
            type_code = code.lower()
            if (
                "etf" in type_code
                or "etn" in type_code
                or "etp" in type_code
                or "exchange traded" in description
            ):
                etf_type_codes.add(code)
        return etf_type_codes
    except Exception:
        return {"ETF", "ETN", "ETP"}


async def massive_fetch_filtered_tickers_for_list(
    client: httpx.AsyncClient,
    api_key: str,
    market: str,
    exclude_etfs: bool,
    tickers: list[str],
) -> set[str]:
    etf_types: set[str] = set()
    if market in ["stocks", "otc"]:
        etf_types = await massive_fetch_ticker_types(client, api_key)
    ref_market = "otc" if market == "otc" else market
    allowed: set[str] = set()

    for ticker in tickers:
        params: dict[str, Any] = {"active": True, "limit": 1, "apiKey": api_key}
        if market in ["stocks", "otc", "crypto", "fx", "indices"]:
            params["market"] = ref_market
        params["ticker"] = ticker
        response = await client.get("https://api.massive.com/v3/reference/tickers", params=params)
        if response.status_code != 200:
            allowed.add(ticker)
            continue
        data = response.json()
        results = data.get("results", [])
        if not isinstance(results, list) or not results:
            allowed.add(ticker)
            continue
        results_list: list[Any] = results
        first_item_raw = results_list[0]
        if not isinstance(first_item_raw, dict):
            allowed.add(ticker)
            continue
        first_item: dict[str, Any] = first_item_raw
        type_val: Any = first_item.get("type")
        market_val: Any = first_item.get("market")
        type_str = type_val if isinstance(type_val, str) else ""
        market_str = market_val if isinstance(market_val, str) else ""
        is_etf = (
            (type_str in etf_types)
            or ("etf" in type_str.lower())
            or ("etn" in type_str.lower())
            or ("etp" in type_str.lower())
            or (market_str == "etp")
        )
        if exclude_etfs and is_etf:
            continue
        if not exclude_etfs and not is_etf:
            continue
        allowed.add(ticker)
    return allowed


async def massive_fetch_filtered_tickers(
    client: httpx.AsyncClient,
    api_key: str,
    market: str,
    exclude_etfs: bool,
) -> set[str]:
    ref_market = "otc" if market == "otc" else market
    needs_etf_filter = market in ["stocks", "otc"]
    ref_params: dict[str, Any] = {"active": True, "limit": 1000, "apiKey": api_key}
    if market in ["stocks", "otc", "crypto", "fx", "indices"]:
        ref_params["market"] = ref_market
    etf_types: set[str] = set()
    if needs_etf_filter:
        etf_types = await massive_fetch_ticker_types(client, api_key)
    ticker_set: set[str] = set()
    ref_url = "https://api.massive.com/v3/reference/tickers"
    next_url: str | None = ref_url
    page_count = 0
    while next_url:
        if page_count > 0:
            if "?" in next_url:
                url_to_fetch = f"{next_url}&apiKey={api_key}"
            else:
                url_to_fetch = f"{next_url}?apiKey={api_key}"
            response = await client.get(url_to_fetch)
        else:
            response = await client.get(ref_url, params=ref_params)
        if response.status_code != 200:
            break
        data = response.json()
        results = data.get("results", [])
        for item in results:
            if not isinstance(item, dict):
                continue
            item_dict: dict[str, Any] = item
            ticker_raw: Any = item_dict.get("ticker")
            if not isinstance(ticker_raw, str) or not ticker_raw:
                continue
            ticker = ticker_raw
            type_val: Any = item_dict.get("type")
            market_val: Any = item_dict.get("market")
            ticker_type = type_val if isinstance(type_val, str) else ""
            ticker_market = market_val if isinstance(market_val, str) else ""
            if etf_types:
                is_etf = (
                    ticker_type in etf_types
                    or "etf" in ticker_type.lower()
                    or "etn" in ticker_type.lower()
                    or "etp" in ticker_type.lower()
                    or ticker_market == "etp"
                )
                if exclude_etfs and is_etf:
                    continue
                if not exclude_etfs and not is_etf:
                    continue
            ticker_set.add(ticker)
        next_url = data.get("next_url")
        page_count += 1
    return ticker_set


async def massive_fetch_snapshot(
    client: httpx.AsyncClient,
    api_key: str,
    locale: str,
    markets: str,
    market: str,
    tickers: list[str] | None,
    include_otc: bool,
) -> list[dict[str, Any]]:
    url = f"https://api.massive.com/v2/snapshot/locale/{locale}/markets/{markets}/tickers"
    params: dict[str, Any] = {}
    if include_otc and market in ["stocks", "otc"]:
        params["include_otc"] = True
    if tickers:
        params["tickers"] = ",".join(tickers)
    params["apiKey"] = api_key
    response = await client.get(url, params=params)
    if response.status_code != 200:
        error_text = response.text if response.text else response.reason_phrase
        raise ValueError(f"Failed to fetch snapshot: {response.status_code} - {error_text}")
    data = response.json()
    tickers_raw = data.get("tickers", [])
    tickers_list_any: list[Any] = tickers_raw if isinstance(tickers_raw, list) else []
    ticker_dicts: list[dict[str, Any]] = []
    for t in tickers_list_any:
        if isinstance(t, dict):
            try:
                sanitized: dict[str, Any] = json.loads(json.dumps(t))
            except Exception:
                sanitized = {}
            ticker_dicts.append(sanitized)
    return ticker_dicts


async def fetch_current_snapshot(symbol: AssetSymbol, api_key: str) -> tuple[float | None, dict[str, Any]]:
    """
    Fetches the current price for a symbol using the Massive.com snapshot API.
    
    Args:
        symbol: AssetSymbol to fetch snapshot for
        api_key: API key for Massive.com
    
    Returns:
        Tuple of (current price or None, metadata dict)
    """
    ticker = str(symbol)
    if symbol.asset_class == AssetClass.CRYPTO:
        ticker = f"X:{ticker}"
        locale = "global"
        markets = "crypto"
    else:
        ticker = ticker.upper()
        locale = "us"
        markets = "stocks"
    
    client = httpx.AsyncClient(timeout=httpx.Timeout(5.0))
    try:
        snapshots = await massive_fetch_snapshot(
            client, api_key, locale, markets, str(symbol.asset_class).lower(), [ticker], False
        )
        if snapshots:
            # Try lastTrade first, fallback to day's open/high/low/close
            last_trade = snapshots[0].get("lastTrade", {})
            price = massive_get_numeric_from_dict(last_trade, "p", 0.0)
            if price <= 0:
                # Fallback to prevDay or current day values
                prev_day = snapshots[0].get("prevDay", {})
                price = massive_get_numeric_from_dict(prev_day, "c", 0.0)
                if price <= 0:
                    day = snapshots[0].get("day", {})
                    price = massive_get_numeric_from_dict(day, "c", 0.0)
            
            if price > 0:
                return price, {"data_status": "real-time", "source": "snapshot"}
        
        logger.warning(f"POLYGON_SERVICE: No valid price found in snapshot for {symbol.ticker}")
        return None, {"data_status": "error", "source": "snapshot"}
    except Exception as e:
        logger.error(f"POLYGON_SERVICE: Error fetching snapshot for {symbol.ticker}: {e}")
        return None, {"data_status": "error", "source": "snapshot"}
    finally:
        await client.aclose()


async def create_current_bar_from_snapshot(symbol: AssetSymbol, api_key: str) -> tuple[list[OHLCVBar], dict[str, Any]]:
    """
    Creates a single synthetic current bar from snapshot data as a fallback.
    
    Args:
        symbol: AssetSymbol to create bar for
        api_key: API key for Massive.com
    
    Returns:
        Tuple of (list with one OHLCVBar or empty list, metadata dict)
    """
    current_price, snapshot_metadata = await fetch_current_snapshot(symbol, api_key)
    if current_price is None:
        return [], snapshot_metadata
    
    now = datetime.now(pytz.UTC)
    # Create a simple current bar using current price (no volume available in basic snapshot)
    current_bar: OHLCVBar = {
        "timestamp": int(now.timestamp() * 1000),
        "open": current_price,
        "high": current_price,
        "low": current_price,
        "close": current_price,
        "volume": 0.0,  # Volume not available in snapshot; set to 0
    }
    
    # Update metadata for fallback
    snapshot_metadata["data_status"] = "real-time"  # Snapshot is always current
    snapshot_metadata["api_status"] = "OK"
    snapshot_metadata["market_open"] = (symbol.asset_class == AssetClass.CRYPTO)
    snapshot_metadata["fallback"] = True
    
    logger.info(f"POLYGON_SERVICE: Created synthetic current bar for {symbol.ticker} from snapshot")
    return [current_bar], snapshot_metadata
