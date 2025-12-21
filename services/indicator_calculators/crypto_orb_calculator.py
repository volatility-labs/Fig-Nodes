"""
Crypto ORB Calculator

Calculates Opening Range Breakout (ORB) for crypto assets using:
- 00:00 UTC as the opening range start time
- 30-minute intervals (instead of 5-minute intervals)
- First 30-minute bar (00:00-00:30 UTC) for ORH/ORL calculation
"""

import logging
from collections.abc import Sequence
from datetime import date, datetime, timedelta
from typing import Any

import pytz

from core.types_registry import AssetClass, AssetSymbol, OHLCVBar

logger = logging.getLogger(__name__)


def calculate_crypto_orb(
    bars: Sequence[OHLCVBar],
    symbol: AssetSymbol,
    or_minutes: int = 30,
    avg_period: int = 14,
    now_func: Any = None,
) -> dict[str, Any]:
    """
    Calculate Crypto ORB (Opening Range Breakout) indicator using 30-minute intervals.
    
    This implementation extracts opening range data from 5-minute bars aggregated to 30-minute bars starting at 00:00 UTC:
    1. Relative Volume: Current opening range volume vs average of previous periods
    2. Direction: Bullish, bearish, or doji based on opening range price movement
    3. ORH/ORL: High and low from the first 30-minute bar (00:00-00:30 UTC)

    Args:
        bars: List of 5-minute OHLCV bars (will be aggregated to 30-minute opening range bars)
        symbol: Asset symbol (must be crypto)
        or_minutes: Opening range period in minutes (default: 30, must be 30 for crypto)
        avg_period: Period for calculating average volume (default: 14 days)
        now_func: Optional function to use instead of datetime.now for testing

    Returns:
        Dictionary with 'rel_vol' (relative volume as percentage), 'direction' (bullish/bearish/doji),
        'or_high' (opening range high), and 'or_low' (opening range low)
    """
    # Ensure symbol is crypto
    if symbol.asset_class != AssetClass.CRYPTO:
        logger.warning(
            f"Crypto ORB Calculator: Symbol {symbol.ticker} is not crypto ({symbol.asset_class})"
        )
        return {
            "rel_vol": None,
            "direction": None,
            "or_high": None,
            "or_low": None,
            "error": f"Symbol {symbol.ticker} is not crypto",
        }

    # Force or_minutes to 30 for crypto ORB
    if or_minutes != 30:
        logger.warning(
            f"Crypto ORB Calculator: or_minutes must be 30 for crypto ORB, using 30 (was {or_minutes})"
        )
        or_minutes = 30

    current_time_utc = datetime.now(pytz.timezone("UTC"))

    print("=" * 80)
    print("CRYPTO ORB CALCULATOR: Starting calculation")
    print("=" * 80)
    logger.info("=" * 80)
    logger.info("CRYPTO ORB CALCULATOR: Starting calculation")
    logger.info(f"CRYPTO ORB CALCULATOR: Current time (UTC): {current_time_utc}")
    logger.info(f"CRYPTO ORB CALCULATOR: Opening range: 00:00 UTC (30-minute bar)")
    logger.info("=" * 80)

    if not bars or len(bars) == 0:
        logger.error("CRYPTO ORB CALCULATOR: No bars provided")
        return {
            "rel_vol": None,
            "direction": None,
            "or_high": None,
            "or_low": None,
            "error": "No bars provided",
        }

    print(f"CRYPTO ORB CALCULATOR: Processing {len(bars)} bars for {symbol.ticker}")
    logger.info(f"CRYPTO ORB Calculator: Processing {len(bars)} bars for {symbol.ticker}")

    # Convert timestamps to datetime objects (assuming milliseconds)
    # For crypto, we work directly in UTC
    bar_data: list[dict[str, Any]] = []
    for bar in bars:
        # Convert UTC timestamp (ms) to UTC datetime
        timestamp_ms = bar["timestamp"]
        dt_utc = datetime.fromtimestamp(timestamp_ms / 1000.0, tz=pytz.timezone("UTC"))
        bar_data.append(
            {
                "timestamp": dt_utc,
                "open": bar["open"],
                "high": bar["high"],
                "low": bar["low"],
                "close": bar["close"],
                "volume": bar["volume"],
            }
        )

    if bar_data:
        first_bar_time = bar_data[0]["timestamp"]
        last_bar_time = bar_data[-1]["timestamp"]
        time_diff = current_time_utc - last_bar_time
        delay_minutes = time_diff.total_seconds() / 60

        print(
            f"CRYPTO ORB CALCULATOR: Converted bars. First bar: {first_bar_time}, Last bar: {last_bar_time}"
        )
        logger.info(
            f"CRYPTO ORB Calculator: Converted bars. First bar: {first_bar_time}, Last bar: {last_bar_time}"
        )
        logger.info(f"CRYPTO ORB CALCULATOR: Current time (UTC): {current_time_utc}")
        logger.info(f"CRYPTO ORB CALCULATOR: Delay from last bar: {delay_minutes:.2f} minutes")

        if delay_minutes < 30:
            logger.info("CRYPTO ORB CALCULATOR: ✅ Bar data appears REAL-TIME (delay < 30 minutes)")
        elif delay_minutes < 60:
            logger.warning(
                f"CRYPTO ORB CALCULATOR: ⚠️ Bar data appears SLIGHTLY DELAYED (delay {delay_minutes:.2f} minutes)"
            )
        else:
            logger.warning(
                f"CRYPTO ORB CALCULATOR: ⚠️ Bar data appears SIGNIFICANTLY DELAYED (delay {delay_minutes:.2f} minutes)"
            )

    # Determine today's date in UTC
    if now_func is None:
        now_func = datetime.now
    today_date_utc = now_func(pytz.timezone("UTC")).date()
    logger.info(f"CRYPTO ORB Calculator: Today's date (UTC): {today_date_utc}")

    # Group bars by UTC date
    daily_groups: dict[date, list[dict[str, Any]]] = {}
    for bar_dict in bar_data:
        bar_date = bar_dict["timestamp"].date()  # UTC date
        if bar_date not in daily_groups:
            daily_groups[bar_date] = []
        daily_groups[bar_date].append(bar_dict)

    print(f"CRYPTO ORB CALCULATOR: Grouped into {len(daily_groups)} days")
    logger.info(f"CRYPTO ORB Calculator: Grouped into {len(daily_groups)} days")
    logger.info(f"CRYPTO ORB CALCULATOR: Available dates: {sorted(daily_groups.keys())}")
    logger.info(f"CRYPTO ORB CALCULATOR: Today's date (UTC): {today_date_utc}")

    if today_date_utc in daily_groups:
        logger.info(f"CRYPTO ORB CALCULATOR: ✅ Today's data ({today_date_utc}) is AVAILABLE")
    else:
        latest_date = max(daily_groups.keys()) if daily_groups else None
        if latest_date:
            days_behind = (today_date_utc - latest_date).days
            logger.warning(f"CRYPTO ORB CALCULATOR: ⚠️ Today's data ({today_date_utc}) is NOT AVAILABLE")
            logger.warning(
                f"CRYPTO ORB CALCULATOR: ⚠️ Latest available date: {latest_date} ({days_behind} days behind)"
            )
        else:
            logger.warning(
                f"CRYPTO ORB CALCULATOR: ⚠️ Today's data ({today_date_utc}) is NOT AVAILABLE - No dates found"
            )

    # Calculate opening range volumes, directions, highs, and lows for each day
    or_volumes: dict[date, float] = {}
    or_directions: dict[date, str] = {}
    or_highs: dict[date, float] = {}
    or_lows: dict[date, float] = {}

    for date_key, day_bars in daily_groups.items():
        # Sort bars by timestamp to ensure chronological order
        day_bars_sorted = sorted(day_bars, key=lambda b: b["timestamp"])

        # For crypto, opening range is 00:00 UTC (first 30-minute bar)
        # We aggregate 5-minute bars from 00:00-00:30 UTC to create the opening range bar
        utc_midnight = pytz.timezone("UTC").localize(
            datetime.combine(date_key, datetime.strptime("00:00", "%H:%M").time())
        )
        open_time = utc_midnight
        open_range_end = open_time + timedelta(minutes=or_minutes)  # 00:00-00:30 UTC

        # Debug: Show first few bars for this day
        print(f"CRYPTO ORB CALCULATOR: Bars for {date_key} (showing first 5):")
        for i, bar in enumerate(day_bars_sorted[:5]):
            print(f"  Bar {i}: timestamp={bar['timestamp']}")

        # Aggregate 5-minute bars that fall within the opening range (00:00-00:30 UTC)
        # Polygon bars: timestamp represents the START of the bar period
        # For 5-min bars, we want bars that start at or after 00:00 and before 00:30
        # A bar starting at 00:25 covers 00:25-00:30, which is within the opening range
        or_candidates = [
            bar for bar in day_bars_sorted 
            if open_time <= bar["timestamp"] < open_range_end
        ]

        if not or_candidates:
            print(f"CRYPTO ORB CALCULATOR: No opening range bars found for {date_key}")
            print(f"CRYPTO ORB CALCULATOR: Looking for bars between {open_time} and {open_range_end}")
            logger.warning(f"CRYPTO ORB Calculator: No opening range bars found for {date_key}")
            logger.warning(
                f"CRYPTO ORB CALCULATOR: Expected opening range: {open_time} to {open_range_end} (00:00-00:30 UTC)"
            )
            logger.warning(f"CRYPTO ORB CALCULATOR: Available bars for {date_key}: {len(day_bars_sorted)}")
            if day_bars_sorted:
                first_bar = day_bars_sorted[0]['timestamp']
                last_bar = day_bars_sorted[-1]['timestamp']
                logger.warning(f"CRYPTO ORB CALCULATOR: First bar time: {first_bar} (UTC)")
                logger.warning(f"CRYPTO ORB CALCULATOR: Last bar time: {last_bar} (UTC)")
            continue

        # Aggregate 5-minute bars into a single 30-minute opening range bar
        # Open = first bar's open, Close = last bar's close
        # High = max of all highs, Low = min of all lows
        # Volume = sum of all volumes
        or_open = or_candidates[0]["open"]
        or_close = or_candidates[-1]["close"]
        or_high = max(bar["high"] for bar in or_candidates)
        or_low = min(bar["low"] for bar in or_candidates)
        or_volume = sum(bar["volume"] for bar in or_candidates)

        print(
            f"CRYPTO ORB CALCULATOR: Aggregated {len(or_candidates)} bars for opening range {date_key} "
            f"(from {or_candidates[0]['timestamp']} to {or_candidates[-1]['timestamp']})"
        )

        # Determine direction
        if or_close > or_open:
            direction = "bullish"
        elif or_close < or_open:
            direction = "bearish"
        else:
            direction = "doji"

        # Use first bar's timestamp for logging
        first_bar_timestamp = or_candidates[0]['timestamp'] if or_candidates else None
        print(
            f"CRYPTO ORB CALCULATOR: {date_key} - OR aggregated from {len(or_candidates)} bars "
            f"(first bar: {first_bar_timestamp}), volume={or_volume}, direction={direction}, "
            f"open={or_open}, close={or_close}, high={or_high}, low={or_low}"
        )
        logger.info(
            f"CRYPTO ORB Calculator: {date_key} - OR aggregated from {len(or_candidates)} bars "
            f"(first bar: {first_bar_timestamp}), volume={or_volume}, direction={direction}, "
            f"open={or_open}, close={or_close}, high={or_high}, low={or_low}"
        )

        or_volumes[date_key] = or_volume
        or_directions[date_key] = direction
        or_highs[date_key] = or_high
        or_lows[date_key] = or_low

    # Calculate relative volume
    sorted_dates = sorted(or_volumes.keys())
    if len(sorted_dates) < 1:
        return {
            "rel_vol": None,
            "direction": None,
            "or_high": None,
            "or_low": None,
            "error": "Insufficient days",
        }

    print(f"CRYPTO ORB CALCULATOR: Found {len(sorted_dates)} days with opening range bars")
    print(f"CRYPTO ORB CALCULATOR: Date range: {sorted_dates[0]} to {sorted_dates[-1]}")
    logger.info(f"CRYPTO ORB Calculator: Found {len(sorted_dates)} days with opening range bars")
    logger.info(f"CRYPTO ORB Calculator: Date range: {sorted_dates[0]} to {sorted_dates[-1]}")
    logger.info(f"CRYPTO ORB CALCULATOR: Days with OR data: {sorted_dates}")

    # Check if today has OR data
    if today_date_utc in sorted_dates:
        logger.info(f"CRYPTO ORB CALCULATOR: ✅ Today ({today_date_utc}) has opening range data")
        today_or_volume = or_volumes.get(today_date_utc, 0)
        today_or_direction = or_directions.get(today_date_utc, "unknown")
        logger.info(
            f"CRYPTO ORB CALCULATOR: Today's OR - Volume: {today_or_volume}, Direction: {today_or_direction}"
        )
    else:
        latest_or_date = sorted_dates[-1] if sorted_dates else None
        if latest_or_date:
            days_behind = (today_date_utc - latest_or_date).days
            logger.warning(
                f"CRYPTO ORB CALCULATOR: ⚠️ Today ({today_date_utc}) does NOT have opening range data"
            )
            logger.warning(
                f"CRYPTO ORB CALCULATOR: ⚠️ Latest OR date: {latest_or_date} ({days_behind} days behind)"
            )

    # Determine target date - use TODAY's opening range if available (for filtering current price vs today's ORH)
    # This ensures we're comparing current price to TODAY's opening range high, not yesterday's
    utc_now = datetime.now(pytz.timezone("UTC"))
    current_hour = utc_now.hour
    current_minute = utc_now.minute
    
    # Prefer today's opening range if it exists (we're filtering based on today's new day)
    # Only use yesterday if today's data isn't available yet
    if today_date_utc in or_directions:
        target_date = today_date_utc
        logger.info(f"CRYPTO ORB CALCULATOR: ✅ Using TODAY ({target_date}) as target date - comparing current price to today's ORH")
    elif current_hour > 0 or (current_hour == 0 and current_minute >= 30):
        # We're past 00:30 UTC but today's data isn't available - this shouldn't happen normally
        target_date = today_date_utc - timedelta(days=1)
        logger.warning(
            f"CRYPTO ORB CALCULATOR: ⚠️ Past 00:30 UTC but today's OR data not available, "
            f"using YESTERDAY ({target_date}) as fallback"
        )
    else:
        # Before 00:30 UTC, use yesterday
        target_date = today_date_utc - timedelta(days=1)
        logger.info(f"CRYPTO ORB CALCULATOR: Using YESTERDAY ({target_date}) as target date (before 00:30 UTC)")

    print(f"CRYPTO ORB CALCULATOR: Target date: {target_date}")
    logger.info(f"CRYPTO ORB Calculator: Target date: {target_date}")
    
    # Final validation: if target date doesn't have OR data, use the most recent date that does
    if target_date not in or_directions:
        if sorted_dates:
            latest_date = sorted_dates[-1]
            logger.warning(
                f"CRYPTO ORB CALCULATOR: ⚠️ Target date {target_date} doesn't have OR data, "
                f"using latest available date ({latest_date}) instead"
            )
            target_date = latest_date
        else:
            logger.error(f"CRYPTO ORB CALCULATOR: ❌ No opening range data available for any date!")

    # Calculate average volume from past periods (excluding target date)
    target_volume_date = target_date if target_date in or_volumes else sorted_dates[-1]

    if len(sorted_dates) > avg_period:
        past_volumes = [or_volumes[d] for d in sorted_dates[-avg_period - 1 : -1]]
    else:
        past_volumes = [or_volumes[d] for d in sorted_dates[:-1]]

    print(f"CRYPTO ORB CALCULATOR: Using {len(past_volumes)} past days for average")
    print(
        f"CRYPTO ORB CALCULATOR: Past dates: {sorted_dates[-avg_period - 1 : -1] if len(sorted_dates) > avg_period else sorted_dates[:-1]}"
    )
    print(f"CRYPTO ORB CALCULATOR: Past volumes: {past_volumes}")
    logger.info(f"CRYPTO ORB Calculator: Using {len(past_volumes)} past days for average")
    logger.info(
        f"CRYPTO ORB Calculator: Past dates: {sorted_dates[-avg_period - 1 : -1] if len(sorted_dates) > avg_period else sorted_dates[:-1]}"
    )
    logger.info(f"CRYPTO ORB Calculator: Past volumes: {past_volumes}")

    avg_vol = sum(past_volumes) / len(past_volumes) if past_volumes else 0.0

    current_vol = or_volumes.get(target_volume_date, 0.0)

    print(f"CRYPTO ORB CALCULATOR: Current day ({target_volume_date}) volume: {current_vol}")
    print(f"CRYPTO ORB CALCULATOR: Average volume (last {len(past_volumes)} days): {avg_vol}")
    logger.info(f"CRYPTO ORB Calculator: Current day ({target_volume_date}) volume: {current_vol}")
    logger.info(f"CRYPTO ORB Calculator: Average volume (last {len(past_volumes)} days): {avg_vol}")

    rel_vol = (
        (current_vol / avg_vol * 100) if avg_vol > 0 else (float("inf") if current_vol > 0 else 0.0)
    )

    print(
        f"CRYPTO ORB CALCULATOR: Relative volume calculation: {current_vol} / {avg_vol} * 100 = {rel_vol}%"
    )
    logger.info(
        f"CRYPTO ORB Calculator: Relative volume calculation: {current_vol} / {avg_vol} * 100 = {rel_vol}%"
    )

    # Get direction, high, and low for target date
    # If target date doesn't have OR data, return error (don't use "doji" as default)
    if target_date not in or_directions:
        logger.warning(
            f"CRYPTO ORB CALCULATOR: ⚠️ Target date {target_date} does NOT have opening range data"
        )
        return {
            "rel_vol": None,
            "direction": None,
            "or_high": None,
            "or_low": None,
            "error": f"No opening range data for target date {target_date}",
        }
    
    direction = or_directions.get(target_date, "doji")
    or_high = or_highs.get(target_date)
    or_low = or_lows.get(target_date)
    
    # Validate that we have valid OR data
    if or_high is None or or_low is None:
        logger.warning(
            f"CRYPTO ORB CALCULATOR: ⚠️ Target date {target_date} has incomplete OR data (or_high={or_high}, or_low={or_low})"
        )
        return {
            "rel_vol": None,
            "direction": None,
            "or_high": None,
            "or_low": None,
            "error": f"Incomplete opening range data for target date {target_date}",
        }

    print(
        f"CRYPTO ORB CALCULATOR: Final result - rel_vol={rel_vol}%, direction={direction}, or_high={or_high}, or_low={or_low}"
    )
    logger.info(
        f"CRYPTO ORB Calculator: Final result - rel_vol={rel_vol}%, direction={direction}, or_high={or_high}, or_low={or_low}"
    )

    # Final summary with data freshness check
    logger.info("=" * 80)
    logger.info(f"CRYPTO ORB CALCULATOR: Final Summary for {symbol.ticker}")
    logger.info(f"CRYPTO ORB CALCULATOR: Target date used: {target_date}")
    logger.info(f"CRYPTO ORB CALCULATOR: Relative volume: {rel_vol}%")
    logger.info(f"CRYPTO ORB CALCULATOR: Direction: {direction}")
    logger.info(f"CRYPTO ORB CALCULATOR: Opening Range High: {or_high}")
    logger.info(f"CRYPTO ORB CALCULATOR: Opening Range Low: {or_low}")

    if target_date == today_date_utc:
        logger.info("CRYPTO ORB CALCULATOR: ✅ Using TODAY's opening range data")
    elif target_date == today_date_utc - timedelta(days=1):
        logger.info("CRYPTO ORB CALCULATOR: ⚠️ Using YESTERDAY's opening range data (today's OR not yet available)")
    else:
        days_behind = (today_date_utc - target_date).days
        logger.warning(f"CRYPTO ORB CALCULATOR: ⚠️ Using DELAYED data ({days_behind} days behind)")

    logger.info("=" * 80)

    return {
        "rel_vol": rel_vol,
        "direction": direction,
        "or_high": or_high,
        "or_low": or_low,
    }

