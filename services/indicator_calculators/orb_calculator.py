import logging
from collections.abc import Sequence
from datetime import date, datetime, timedelta
from typing import Any

import pytz

from core.types_registry import AssetClass, AssetSymbol, OHLCVBar
from services.time_utils import create_market_open_time, utc_timestamp_ms_to_et_datetime

logger = logging.getLogger(__name__)


def calculate_orb(
    bars: Sequence[OHLCVBar],
    symbol: AssetSymbol,
    or_minutes: int = 5,
    avg_period: int = 14,
    now_func: Any = None,
) -> dict[str, Any]:
    """
    Calculate ORB (Opening Range Breakout) indicator including relative volume and direction.

    This implementation extracts opening range data from 5-minute bars and calculates:
    1. Relative Volume: Current opening range volume vs average of previous periods
    2. Direction: Bullish, bearish, or doji based on opening range price movement

    Args:
        bars: List of 5-minute OHLCV bars (aggregated bars from Polygon)
        symbol: Asset symbol (used to determine opening range time based on asset class)
        or_minutes: Opening range period in minutes (default: 5)
        avg_period: Period for calculating average volume (default: 14 days)
        now_func: Optional function to use instead of datetime.now for testing

    Returns:
        Dictionary with 'rel_vol' (relative volume as percentage) and 'direction' (bullish/bearish/doji)

    Reference Paper Implementation:
        The paper uses:
        - Relative Volume = (Volume in first n minutes) / (Avg of last 14 days) * 100
        - This matches our implementation

        Note: The paper also mentions ATR filtering (> $0.50 over 14 days) but that is
        a separate filter, not part of the ORB calculation itself.
    """
    current_time_utc = datetime.now(pytz.timezone("UTC"))
    current_time_et = current_time_utc.astimezone(pytz.timezone("US/Eastern"))
    
    print("=" * 80)
    print("ORB CALCULATOR: Starting calculation")
    print("=" * 80)
    logger.info("=" * 80)
    logger.info("ORB CALCULATOR: Starting calculation")
    logger.info(f"ORB CALCULATOR: Current time (UTC): {current_time_utc}")
    logger.info(f"ORB CALCULATOR: Current time (ET): {current_time_et}")
    logger.info("=" * 80)

    if not bars or len(bars) == 0:
        logger.error("ORB CALCULATOR: No bars provided")
        return {"rel_vol": None, "direction": None, "error": "No bars provided"}

    print(f"ORB CALCULATOR: Processing {len(bars)} bars for {symbol.ticker}")
    logger.info(f"ORB Calculator: Processing {len(bars)} bars for {symbol.ticker}")
    
    # Log raw bar timestamps before conversion
    if bars:
        first_bar_raw = bars[0]["timestamp"]
        last_bar_raw = bars[-1]["timestamp"]
        logger.info(f"ORB CALCULATOR: Raw timestamps - First: {first_bar_raw}, Last: {last_bar_raw}")

    # Convert timestamps to datetime objects (assuming milliseconds)
    bar_data: list[dict[str, Any]] = []
    for bar in bars:
        # Use time_utils function to properly convert UTC timestamp to ET datetime
        dt_et = utc_timestamp_ms_to_et_datetime(bar["timestamp"])
        bar_data.append(
            {
                "timestamp": dt_et,
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
        time_diff = current_time_et - last_bar_time
        delay_minutes = time_diff.total_seconds() / 60
        
        print(
            f"ORB CALCULATOR: Converted bars. First bar: {first_bar_time}, Last bar: {last_bar_time}"
        )
        logger.info(
            f"ORB Calculator: Converted bars. First bar: {first_bar_time}, Last bar: {last_bar_time}"
        )
        logger.info(f"ORB CALCULATOR: Current time (ET): {current_time_et}")
        logger.info(f"ORB CALCULATOR: Delay from last bar: {delay_minutes:.2f} minutes")
        
        if delay_minutes < 5:
            logger.info(f"ORB CALCULATOR: ✅ Bar data appears REAL-TIME (delay < 5 minutes)")
        elif delay_minutes < 15:
            logger.warning(f"ORB CALCULATOR: ⚠️ Bar data appears SLIGHTLY DELAYED (delay {delay_minutes:.2f} minutes)")
        else:
            logger.warning(f"ORB CALCULATOR: ⚠️ Bar data appears SIGNIFICANTLY DELAYED (delay {delay_minutes:.2f} minutes)")

    # Determine today's date early for logging
    if now_func is None:
        now_func = datetime.now
    today_date = now_func(pytz.timezone("US/Eastern")).date()
    logger.info(f"ORB Calculator: Today's date: {today_date}")

    # Group bars by date
    daily_groups: dict[date, list[dict[str, Any]]] = {}
    for bar_dict in bar_data:
        bar_date = bar_dict["timestamp"].date()
        if bar_date not in daily_groups:
            daily_groups[bar_date] = []
        daily_groups[bar_date].append(bar_dict)

    print(f"ORB CALCULATOR: Grouped into {len(daily_groups)} days")
    logger.info(f"ORB Calculator: Grouped into {len(daily_groups)} days")
    logger.info(f"ORB CALCULATOR: Available dates: {sorted(daily_groups.keys())}")
    logger.info(f"ORB CALCULATOR: Today's date: {today_date}")
    
    if today_date in daily_groups:
        logger.info(f"ORB CALCULATOR: ✅ Today's data ({today_date}) is AVAILABLE")
    else:
        latest_date = max(daily_groups.keys()) if daily_groups else None
        if latest_date:
            days_behind = (today_date - latest_date).days
            logger.warning(f"ORB CALCULATOR: ⚠️ Today's data ({today_date}) is NOT AVAILABLE")
            logger.warning(f"ORB CALCULATOR: ⚠️ Latest available date: {latest_date} ({days_behind} days behind)")
        else:
            logger.warning(f"ORB CALCULATOR: ⚠️ Today's data ({today_date}) is NOT AVAILABLE - No dates found")

    # Calculate opening range volumes and directions for each day
    or_volumes: dict[date, float] = {}
    or_directions: dict[date, str] = {}

    for date_key, day_bars in daily_groups.items():
        # Sort bars by timestamp to ensure chronological order
        day_bars_sorted = sorted(day_bars, key=lambda b: b["timestamp"])

        # Determine opening range time based on asset class
        if symbol.asset_class == AssetClass.CRYPTO:
            # For crypto, use UTC midnight (00:00:00) as opening range, convert to ET
            utc_midnight = pytz.timezone("UTC").localize(
                datetime.combine(date_key, datetime.strptime("00:00", "%H:%M").time())
            )
            open_time = utc_midnight.astimezone(pytz.timezone("US/Eastern"))
        else:
            # For stocks, use 9:30 AM Eastern as opening range
            open_time = create_market_open_time(date_key, hour=9, minute=30)

        # Debug: Show first few bars for this day
        print(f"ORB CALCULATOR: Bars for {date_key} (showing first 5):")
        for i, bar in enumerate(day_bars_sorted[:5]):
            print(f"  Bar {i}: timestamp={bar['timestamp']}")

        # Look for bars within the opening range (9:30 AM to 9:35 AM)
        open_range_end = open_time + timedelta(minutes=5)

        # Find bars that start within the opening range
        or_candidates = [
            bar for bar in day_bars_sorted if open_time <= bar["timestamp"] < open_range_end
        ]

        if not or_candidates:
            print(f"ORB CALCULATOR: No opening range bar found for {date_key}")
            print(f"ORB CALCULATOR: Looking for bars between {open_time} and {open_range_end}")
            logger.warning(f"ORB Calculator: No opening range bar found for {date_key}")
            logger.warning(f"ORB CALCULATOR: Expected opening range: {open_time} to {open_range_end}")
            logger.warning(f"ORB CALCULATOR: Available bars for {date_key}: {len(day_bars_sorted)}")
            if day_bars_sorted:
                logger.warning(f"ORB CALCULATOR: First bar time: {day_bars_sorted[0]['timestamp']}")
                logger.warning(f"ORB CALCULATOR: Last bar time: {day_bars_sorted[-1]['timestamp']}")
            continue

        # Pick the earliest bar in the opening range
        or_bar = or_candidates[0]

        print(
            f"ORB CALCULATOR: Found {len(or_candidates)} opening range bars for {date_key}, using: {or_bar['timestamp']}"
        )

        # Calculate opening range metrics from single 5-minute bar
        or_volume = or_bar["volume"]
        or_open = or_bar["open"]
        or_close = or_bar["close"]

        # Determine direction
        if or_close > or_open:
            direction = "bullish"
        elif or_close < or_open:
            direction = "bearish"
        else:
            direction = "doji"

        print(
            f"ORB CALCULATOR: {date_key} - OR bar: time={or_bar['timestamp']}, volume={or_volume}, direction={direction}, open={or_open}, close={or_close}"
        )
        logger.info(
            f"ORB Calculator: {date_key} - OR bar: time={or_bar['timestamp']}, volume={or_volume}, direction={direction}, open={or_open}, close={or_close}"
        )

        or_volumes[date_key] = or_volume
        or_directions[date_key] = direction

    # Calculate relative volume
    sorted_dates = sorted(or_volumes.keys())
    if len(sorted_dates) < 1:
        return {"rel_vol": None, "direction": None, "error": "Insufficient days"}

    print(f"ORB CALCULATOR: Found {len(sorted_dates)} days with opening range bars")
    print(f"ORB CALCULATOR: Date range: {sorted_dates[0]} to {sorted_dates[-1]}")
    logger.info(f"ORB Calculator: Found {len(sorted_dates)} days with opening range bars")
    logger.info(f"ORB Calculator: Date range: {sorted_dates[0]} to {sorted_dates[-1]}")
    logger.info(f"ORB CALCULATOR: Days with OR data: {sorted_dates}")
    
    # Check if today has OR data
    if today_date in sorted_dates:
        logger.info(f"ORB CALCULATOR: ✅ Today ({today_date}) has opening range data")
        today_or_volume = or_volumes.get(today_date, 0)
        today_or_direction = or_directions.get(today_date, "unknown")
        logger.info(f"ORB CALCULATOR: Today's OR - Volume: {today_or_volume}, Direction: {today_or_direction}")
    else:
        latest_or_date = sorted_dates[-1] if sorted_dates else None
        if latest_or_date:
            days_behind = (today_date - latest_or_date).days
            logger.warning(f"ORB CALCULATOR: ⚠️ Today ({today_date}) does NOT have opening range data")
            logger.warning(f"ORB CALCULATOR: ⚠️ Latest OR date: {latest_or_date} ({days_behind} days behind)")

    # Determine target date (today or last trading day)
    if symbol.asset_class == AssetClass.CRYPTO:
        # For crypto, use UTC midnight of prior day
        utc_now = datetime.now(pytz.timezone("UTC"))
        target_date = utc_now.date() - timedelta(days=1)
    else:
        # For stocks, use today if available, otherwise last trading day
        if today_date in sorted_dates:
            target_date = today_date
        else:
            target_date = sorted_dates[-1] if sorted_dates else today_date

    print(f"ORB CALCULATOR: Target date: {target_date}")
    logger.info(f"ORB Calculator: Target date: {target_date}")
    
    if target_date == today_date:
        logger.info(f"ORB CALCULATOR: ✅ Using TODAY ({target_date}) as target date")
    else:
        days_behind = (today_date - target_date).days
        logger.warning(f"ORB CALCULATOR: ⚠️ Using {target_date} as target date ({days_behind} days behind today)")

    # Calculate average volume from past periods (excluding target date)
    target_volume_date = target_date if target_date in or_volumes else sorted_dates[-1]

    if len(sorted_dates) > avg_period:
        past_volumes = [or_volumes[d] for d in sorted_dates[-avg_period - 1 : -1]]
    else:
        past_volumes = [or_volumes[d] for d in sorted_dates[:-1]]

    print(f"ORB CALCULATOR: Using {len(past_volumes)} past days for average")
    print(
        f"ORB CALCULATOR: Past dates: {sorted_dates[-avg_period - 1 : -1] if len(sorted_dates) > avg_period else sorted_dates[:-1]}"
    )
    print(f"ORB CALCULATOR: Past volumes: {past_volumes}")
    logger.info(f"ORB Calculator: Using {len(past_volumes)} past days for average")
    logger.info(
        f"ORB Calculator: Past dates: {sorted_dates[-avg_period - 1 : -1] if len(sorted_dates) > avg_period else sorted_dates[:-1]}"
    )
    logger.info(f"ORB Calculator: Past volumes: {past_volumes}")

    avg_vol = sum(past_volumes) / len(past_volumes) if past_volumes else 0.0

    current_vol = or_volumes.get(target_volume_date, 0.0)

    print(f"ORB CALCULATOR: Current day ({target_volume_date}) volume: {current_vol}")
    print(f"ORB CALCULATOR: Average volume (last {len(past_volumes)} days): {avg_vol}")
    logger.info(f"ORB Calculator: Current day ({target_volume_date}) volume: {current_vol}")
    logger.info(f"ORB Calculator: Average volume (last {len(past_volumes)} days): {avg_vol}")

    rel_vol = (
        (current_vol / avg_vol * 100) if avg_vol > 0 else (float("inf") if current_vol > 0 else 0.0)
    )

    print(
        f"ORB CALCULATOR: Relative volume calculation: {current_vol} / {avg_vol} * 100 = {rel_vol}%"
    )
    logger.info(
        f"ORB Calculator: Relative volume calculation: {current_vol} / {avg_vol} * 100 = {rel_vol}%"
    )

    # Get direction for target date
    direction = or_directions.get(target_date, "doji")

    print(f"ORB CALCULATOR: Final result - rel_vol={rel_vol}%, direction={direction}")
    logger.info(f"ORB Calculator: Final result - rel_vol={rel_vol}%, direction={direction}")
    
    # Final summary with data freshness check
    logger.info("=" * 80)
    logger.info(f"ORB CALCULATOR: Final Summary for {symbol.ticker}")
    logger.info(f"ORB CALCULATOR: Target date used: {target_date}")
    logger.info(f"ORB CALCULATOR: Relative volume: {rel_vol}%")
    logger.info(f"ORB CALCULATOR: Direction: {direction}")
    
    if target_date == today_date:
        logger.info(f"ORB CALCULATOR: ✅ Using REAL-TIME data (today)")
    else:
        days_behind = (today_date - target_date).days
        logger.warning(f"ORB CALCULATOR: ⚠️ Using DELAYED data ({days_behind} days behind)")
    
    logger.info("=" * 80)

    # Calculate opening range high and low for current target date
    target_or_bar = None
    if target_date in daily_groups:
        day_bars_sorted = sorted(daily_groups[target_date], key=lambda b: b["timestamp"])
        
        # Determine opening range time based on asset class
        if symbol.asset_class == AssetClass.CRYPTO:
            # For crypto, use UTC midnight (00:00:00) as opening range, convert to ET
            utc_midnight = pytz.timezone("UTC").localize(
                datetime.combine(target_date, datetime.strptime("00:00", "%H:%M").time())
            )
            open_time = utc_midnight.astimezone(pytz.timezone("US/Eastern"))
        else:
            # For stocks, use 9:30 AM Eastern as opening range
            open_time = create_market_open_time(target_date, hour=9, minute=30)
        
        open_range_end = open_time + timedelta(minutes=or_minutes)
        
        # Find bars that start within the opening range
        or_candidates = [
            bar for bar in day_bars_sorted if open_time <= bar["timestamp"] < open_range_end
        ]
        
        if or_candidates:
            target_or_bar = or_candidates[0]
    
    or_high = target_or_bar["high"] if target_or_bar else None
    or_low = target_or_bar["low"] if target_or_bar else None

    return {
        "rel_vol": rel_vol,
        "direction": direction,
        "or_high": or_high,
        "or_low": or_low,
    }
