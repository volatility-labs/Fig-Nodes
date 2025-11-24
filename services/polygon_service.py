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
    multiplier = params.get("multiplier", 1)
    timespan = params.get("timespan", "day")
    lookback_period = params.get("lookback_period", "3 months")
    adjusted = params.get("adjusted", True)
    sort = params.get("sort", "asc")
    limit = params.get("limit", 5000)

    # Massive.com aggregates API has a hard cap of 5000 bars per request
    # Even if you request more, API will only return max 5000
    # Use the actual API limit for our checks, not the requested limit
    ACTUAL_API_LIMIT = 5000
    effective_limit = min(limit, ACTUAL_API_LIMIT)
    
    # For crypto with long lookback periods, fetch newest first to avoid hitting API limits
    # This ensures we get the most recent data even if we hit the 5000 bar limit
    # We'll reverse the results to get chronological order (oldest first)
    fetch_newest_first = False
    
    # Estimate number of bars needed to determine if we might hit API limits
    # If we might hit the limit (5000 bars), we MUST fetch newest first to avoid stale data
    # This is especially important for charts which need to show the current price context
    parts = lookback_period.split()
    if len(parts) == 2:
        amount = int(parts[0])
        unit = parts[1].lower()
        
        # Trading hours per day (Crypto 24h, Stocks ~6.5h - use 16 to be safe including ext hours)
        # Trading days per week (Crypto 7, Stocks 5)
        if symbol.asset_class == AssetClass.CRYPTO:
            hours_per_day = 24
            days_per_week_factor = 1.0
        else:
            # Polygon aggregates often include extended hours or partial bars
            # Using a safer estimate of 16 hours/day for checks
            hours_per_day = 16  
            days_per_week_factor = 5/7
            
        # Convert lookback to days
        days_lookback = 0
        if unit in ("day", "days"):
            days_lookback = amount
        elif unit in ("week", "weeks"):
            days_lookback = amount * 7
        elif unit in ("month", "months"):
            days_lookback = amount * 30
        elif unit in ("year", "years"):
            days_lookback = amount * 365
            
        # Estimate bars based on timespan
        if timespan == "minute":
            # Bars per day * number of days * adjustment for trading days
            estimated_bars = (days_lookback * hours_per_day * 60) / multiplier * days_per_week_factor
        elif timespan == "hour":
            estimated_bars = (days_lookback * hours_per_day) / multiplier * days_per_week_factor
        elif timespan == "day":
            estimated_bars = days_lookback * days_per_week_factor
        else:
            estimated_bars = 0
            
        # If estimated bars exceeds 80% of the limit OR if the lookback is significant (>1 week for minute/hour)
        # we force newest first. This protects against data gaps and limits.
        # "Significant lookback" heuristic: >1000 estimated bars
        is_significant_request = estimated_bars > 1000
        
        # Always prefer newest-first if there's any risk of hitting limits or missing recent data
        if estimated_bars > effective_limit * 0.8 or is_significant_request:
            fetch_newest_first = True
            sort = "desc"
            logger.warning(f"POLYGON_SERVICE: 🔄 Smart fetch active: Requesting {estimated_bars:.0f} bars ({lookback_period}) for {symbol.ticker}. Fetching NEWEST first to ensure current data visibility (limit={effective_limit}).")

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

        logger.warning(f"POLYGON_SERVICE: HTTP response status: {response.status_code}")

        if response.status_code != 200:
            logger.error(f"POLYGON_SERVICE: HTTP error {response.status_code} for {symbol.ticker}")
            raise ValueError(f"Failed to fetch bars: HTTP {response.status_code}")

        data = response.json()
        api_status = data.get("status")
        results_count = data.get("resultsCount", 0)

        logger.warning(f"POLYGON_SERVICE: API Response Status: {api_status}, Results: {results_count}, Limit requested: {limit}")

        # Log raw API response details for debugging delay issues
        if logger.isEnabledFor(logging.DEBUG):
            results_preview = data.get("results", [])
            if results_preview:
                # Log first and last bar from API response
                first_bar_raw = results_preview[0] if isinstance(results_preview[0], dict) else {}
                last_bar_raw = results_preview[-1] if isinstance(results_preview[-1], dict) else {}
                first_ts = first_bar_raw.get("t") if isinstance(first_bar_raw, dict) else None
                last_ts = last_bar_raw.get("t") if isinstance(last_bar_raw, dict) else None
                logger.debug(
                    f"POLYGON_SERVICE: Raw API response for {symbol.ticker}: "
                    f"First bar t={first_ts}, Last bar t={last_ts}, "
                    f"Sort order: {sort}"
                )

        if data.get("status") not in ["OK", "DELAYED"]:
            error_msg = data.get("error", "Unknown error")
            logger.error(f"POLYGON_SERVICE: API error for {symbol.ticker}: {error_msg}")
            raise ValueError(f"Massive.com API error: {error_msg}")

        # Determine data status based on market state and API status
        from services.time_utils import is_us_market_open, utc_timestamp_ms_to_et_datetime

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
        
        # Check if we hit the API limit (API might cap at 5000 even if we request more)
        actual_results = len(results)
        if actual_results >= limit and results_count >= limit:
            logger.warning(
                f"POLYGON_SERVICE: Hit API limit for {symbol.ticker}: "
                f"requested {limit} bars, got {actual_results} bars. "
                f"Some data may be missing. Consider using shorter lookback period or fetching in chunks."
            )
        
        # If we fetched newest first, reverse to get chronological order (oldest first)
        if fetch_newest_first and results:
            results = list(reversed(results))
            logger.warning(f"POLYGON_SERVICE: 🔄 Reversed {len(results)} bars to chronological order (oldest first)")
        
        bars: list[OHLCVBar] = []
        # Track if we need to append current bar from snapshot
        needs_current_bar = False
        current_bar_dict: OHLCVBar | None = None

        if not results:
            logger.warning(f"POLYGON_SERVICE: No bars returned for {symbol.ticker}")

            # For crypto symbols, try snapshot fallback when no aggregates available
            if symbol.asset_class == AssetClass.CRYPTO and timespan == "minute":
                logger.info(
                    f"POLYGON_SERVICE: Attempting snapshot fallback for crypto {symbol.ticker}"
                )
                try:
                    snapshot_bars, snapshot_metadata = await create_current_bar_from_snapshot(
                        symbol, api_key
                    )
                    if snapshot_bars:
                        logger.info(f"POLYGON_SERVICE: Using snapshot fallback for {symbol.ticker}")
                        # Merge metadata
                        metadata.update(snapshot_metadata)
                        return snapshot_bars, metadata
                    else:
                        logger.warning(
                            f"POLYGON_SERVICE: Snapshot fallback failed for {symbol.ticker}"
                        )
                except Exception as e:
                    logger.error(
                        f"POLYGON_SERVICE: Snapshot fallback error for {symbol.ticker}: {e}"
                    )
        else:
            # Check if the latest bar is too old (more than 30 minutes)
            # We'll fill in missing intervals with snapshot data to keep bars recent
            # Apply to crypto with minute OR hour timespans (hourly bars can also be stale)
            if results and symbol.asset_class == AssetClass.CRYPTO and timespan in ["minute", "hour"]:
                # Determine which bar is most recent based on sort order
                sort_order = params.get("sort", "asc")
                if sort_order == "desc":
                    latest_bar = results[0]  # Most recent is first
                else:
                    latest_bar = results[-1]  # Most recent is last

                latest_timestamp_ms = latest_bar.get("t", 0)
                if isinstance(latest_timestamp_ms, int):
                    # Convert timestamp to datetime for comparison
                    latest_time_utc = datetime.fromtimestamp(
                        latest_timestamp_ms / 1000, tz=pytz.UTC
                    )
                    current_time_utc = datetime.now(pytz.UTC)
                    age_minutes = (current_time_utc - latest_time_utc).total_seconds() / 60

                    if age_minutes > 30:  # If latest bar is more than 30 minutes old
                        logger.warning(
                            f"POLYGON_SERVICE: Latest bar for {symbol.ticker} is {age_minutes:.1f} minutes old, fetching current snapshot"
                        )

                        try:
                            # Get current price from snapshot
                            logger.warning(f"POLYGON_SERVICE: Fetching snapshot for {symbol.ticker}...")
                            logger.warning(f"POLYGON_SERVICE: Symbol details - ticker={symbol.ticker}, asset_class={symbol.asset_class}")
                            current_price, snapshot_metadata = await fetch_current_snapshot(
                                symbol, api_key
                            )
                            logger.warning(f"POLYGON_SERVICE: Snapshot fetch returned: price={current_price}, metadata={snapshot_metadata}")

                            if current_price is not None:
                                logger.warning(f"POLYGON_SERVICE: ✅ Snapshot fetch successful for {symbol.ticker}, price=${current_price:.4f}")
                                # For hourly bars, use hour-based rounding instead of minute-based
                                if timespan == "hour":
                                    # Round to the current hour
                                    rounded_time = current_time_utc.replace(
                                        minute=0, second=0, microsecond=0
                                    )
                                else:
                                    # Calculate interval based on multiplier (1min, 5min, 15min, 30min)
                                    interval_minutes = multiplier
                                    # Round current time down to the nearest interval
                                    # e.g., if it's 5:37 PM and using 5min bars, round to 5:35 PM
                                    current_minute = current_time_utc.minute
                                    rounded_minute = (
                                        current_minute // interval_minutes
                                    ) * interval_minutes
                                    rounded_time = current_time_utc.replace(
                                        minute=rounded_minute, second=0, microsecond=0
                                    )

                                # Get the last completed bar's close to use as open for the snapshot bar
                                # This creates a proper OHLC candle instead of a full-body single-price candle
                                snapshot_open = current_price  # Default to current price if no previous bar
                                if bars:
                                    # Use the last bar's close as the open for the current bar
                                    # This represents the price at the start of the current hour/interval
                                    last_bar = bars[-1]
                                    snapshot_open = last_bar.get("close", current_price)
                                    logger.warning(
                                        f"POLYGON_SERVICE: Using last bar close ${snapshot_open:.4f} as open for snapshot bar"
                                    )

                                # Create proper OHLC bar: open from last bar's close, high/low/close from current price
                                # This ensures the candle accurately represents price movement during the current period
                                snapshot_high = max(snapshot_open, current_price)
                                snapshot_low = min(snapshot_open, current_price)
                                
                                current_bar_dict = {
                                    "timestamp": int(rounded_time.timestamp() * 1000),
                                    "open": snapshot_open,  # Price at start of hour (last bar's close)
                                    "high": snapshot_high,  # Highest price seen (max of open and current)
                                    "low": snapshot_low,    # Lowest price seen (min of open and current)
                                    "close": current_price, # Current price (end of hour so far)
                                    "volume": 0.0,
                                }
                                needs_current_bar = True
                                logger.warning(
                                    f"POLYGON_SERVICE: ✅ Created OHLC bar for {symbol.ticker} at timestamp {current_bar_dict['timestamp']} "
                                    f"({rounded_time}) with OHLC: O=${snapshot_open:.4f}, H=${snapshot_high:.4f}, L=${snapshot_low:.4f}, C=${current_price:.4f}"
                                )
                            else:
                                logger.warning(
                                    f"POLYGON_SERVICE: Snapshot fetch returned None for {symbol.ticker} - using stale bars"
                                )
                        except Exception as e:
                            logger.error(
                                f"POLYGON_SERVICE: Snapshot injection error for {symbol.ticker}: {e}",
                                exc_info=True,
                            )
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
                # IMPORTANT: After reversal (if fetch_newest_first), bars are ALWAYS in chronological order (oldest first)
                # So we should ALWAYS append the snapshot bar to make it the newest (last)
                # Only prepend if we didn't reverse AND sort_order is "desc"
                sort_order = params.get("sort", "asc")
                if not fetch_newest_first and sort_order == "desc":
                    # For descending sort WITHOUT reversal, prepend to make it the newest (first)
                    bars.insert(0, current_bar_dict)
                    logger.warning(f"POLYGON_SERVICE: Prepended snapshot bar for {symbol.ticker} (desc sort, no reversal)")
                else:
                    # For ascending sort OR after reversal, append to make it the newest (last)
                    bars.append(current_bar_dict)
                    logger.warning(f"POLYGON_SERVICE: Appended snapshot bar for {symbol.ticker} (asc sort or after reversal)")

                # Include appended bar timestamp in analysis if present
                if needs_current_bar and current_bar_dict:
                    appended_ts = current_bar_dict["timestamp"]
                    timestamps_ms.append(appended_ts)

            if timestamps_ms:
                # Convert timestamps to ET for analysis
                from services.time_utils import utc_timestamp_ms_to_et_datetime

                max_ts_ms = max(timestamps_ms)
                min_ts_ms = min(timestamps_ms)

                # Log raw timestamp details for debugging
                logger.debug(
                    f"POLYGON_SERVICE: Timestamp analysis for {symbol.ticker}: "
                    f"count={len(timestamps_ms)}, min={min_ts_ms}, max={max_ts_ms}"
                )

                # Log first and last few timestamps if DEBUG level
                if logger.isEnabledFor(logging.DEBUG):
                    logger.debug(
                        f"POLYGON_SERVICE: First 3 timestamps: {timestamps_ms[:3]}, "
                        f"Last 3 timestamps: {timestamps_ms[-3:]}"
                    )

                # According to Massive.com docs, the timestamp 't' represents the START of the aggregate window,
                # not the end. For delay calculation, we need to compare current time to the END of the bar window.
                last_bar_start_time = utc_timestamp_ms_to_et_datetime(max_ts_ms)

                # Calculate the END of the latest bar's window based on timespan and multiplier
                # The bar window duration depends on timespan:
                # - day: 24 hours
                # - hour: 1 hour
                # - minute: multiplier minutes
                # - week: 7 days
                # - month: ~30 days
                # - quarter: ~90 days
                # - year: ~365 days
                last_bar_start_utc = datetime.fromtimestamp(max_ts_ms / 1000, tz=pytz.UTC)
                window_duration_seconds = 0
                if timespan == "minute":
                    window_duration_seconds = multiplier * 60
                elif timespan == "hour":
                    window_duration_seconds = multiplier * 3600
                elif timespan == "day":
                    window_duration_seconds = multiplier * 86400  # 24 hours
                elif timespan == "week":
                    window_duration_seconds = multiplier * 7 * 86400
                elif timespan == "month":
                    window_duration_seconds = multiplier * 30 * 86400  # Approximate
                elif timespan == "quarter":
                    window_duration_seconds = multiplier * 90 * 86400  # Approximate
                elif timespan == "year":
                    window_duration_seconds = multiplier * 365 * 86400  # Approximate
                else:
                    # Default to 24 hours if unknown timespan
                    window_duration_seconds = 86400

                # Calculate the END of the bar window (start + duration)
                last_bar_end_utc = last_bar_start_utc + timedelta(seconds=window_duration_seconds)
                last_bar_end_time = last_bar_end_utc.astimezone(pytz.timezone("US/Eastern"))

                # Log parsed datetime details
                logger.debug(
                    f"POLYGON_SERVICE: Latest bar window for {symbol.ticker}: "
                    f"start (ET)={last_bar_start_time}, end (ET)={last_bar_end_time}, "
                    f"current_time_et={current_time_et}, timespan={timespan}, multiplier={multiplier}"
                )

                # Calculate delay from END of latest bar window to current time
                # Only flag as delayed if we're past the end of the bar window
                time_diff = current_time_et - last_bar_end_time
                delay_minutes = time_diff.total_seconds() / 60

                # Log delay calculation details
                logger.debug(
                    f"POLYGON_SERVICE: Delay calc for {symbol.ticker}: "
                    f"bar_window_end={last_bar_end_time}, current={current_time_et}, "
                    f"time_diff={time_diff}, delay_minutes={delay_minutes:.2f}"
                )

                # Only flag as delayed if we're past the end of the bar window
                # For daily bars, this means we're past midnight UTC of the next day
                if delay_minutes > 15:
                    data_status = "delayed"
                    # Log raw API response details when delay detected
                    if results:
                        latest_bar_raw = results[-1] if sort == "asc" else results[0]
                        latest_bar_dict = (
                            cast(dict[str, Any], latest_bar_raw)
                            if isinstance(latest_bar_raw, dict)
                            else {}
                        )
                        logger.warning(
                            f"POLYGON_SERVICE: Significant delay ({delay_minutes:.2f} min) for {symbol.ticker}. "
                            f"Latest bar window start (ms): {max_ts_ms}, "
                            f"Latest bar window end (ET): {last_bar_end_time}, "
                            f"Current time (ET): {current_time_et}, "
                            f"Timespan: {timespan}, Multiplier: {multiplier}, "
                            f"Raw bar data: t={latest_bar_dict.get('t')}, c={latest_bar_dict.get('c')}"
                        )
                    else:
                        logger.warning(
                            f"POLYGON_SERVICE: Significant delay ({delay_minutes:.2f} min) for {symbol.ticker}"
                        )
                else:
                    # Bar is current (within window or less than 15 min past end)
                    logger.debug(
                        f"POLYGON_SERVICE: Bar is current for {symbol.ticker}: "
                        f"delay={delay_minutes:.2f} min (within window or <15 min past end)"
                    )

                # Update metadata with refined status based on actual delay
                metadata["data_status"] = data_status

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


async def fetch_current_snapshot(
    symbol: AssetSymbol, api_key: str
) -> tuple[float | None, dict[str, Any]]:
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
        logger.debug(f"POLYGON_SERVICE: Calling massive_fetch_snapshot for ticker={ticker}, locale={locale}, markets={markets}")
        snapshots = await massive_fetch_snapshot(
            client, api_key, locale, markets, str(symbol.asset_class).lower(), [ticker], False
        )
        logger.debug(f"POLYGON_SERVICE: massive_fetch_snapshot returned {len(snapshots) if snapshots else 0} snapshots")
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


async def create_current_bar_from_snapshot(
    symbol: AssetSymbol, api_key: str
) -> tuple[list[OHLCVBar], dict[str, Any]]:
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
    snapshot_metadata["market_open"] = symbol.asset_class == AssetClass.CRYPTO
    snapshot_metadata["fallback"] = True

    logger.info(f"POLYGON_SERVICE: Created synthetic current bar for {symbol.ticker} from snapshot")
    return [current_bar], snapshot_metadata