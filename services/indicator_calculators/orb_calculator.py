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
        # Match external script logic: Convert 9:30 AM ET to UTC for each date (handles DST automatically)
        et_tz = pytz.timezone("America/New_York")
        if symbol.asset_class == AssetClass.CRYPTO:
            # For crypto, use UTC midnight (00:00:00) as opening range
            utc_midnight = pytz.timezone("UTC").localize(
                datetime.combine(date_key, datetime.strptime("00:00", "%H:%M").time())
            )
            market_open_et = utc_midnight.astimezone(et_tz)
            market_open_utc = utc_midnight  # Already UTC
        else:
            # For stocks, use 9:30 AM Eastern as opening range
            # Convert this specific date's 9:30 AM ET to UTC (handles DST for that date)
            # This matches external script: et_tz.localize(datetime.combine(date, datetime.min.time().replace(hour=9, minute=30)))
            market_open_et = et_tz.localize(
                datetime.combine(date_key, datetime.min.time().replace(hour=9, minute=30))
            )
            market_open_utc = market_open_et.astimezone(pytz.timezone("UTC"))
        
        # Convert opening range end time to UTC as well
        market_close_et = market_open_et + timedelta(minutes=or_minutes)
        market_close_utc = market_close_et.astimezone(pytz.timezone("UTC"))

        # Debug: Show first few bars for this day
        print(f"ORB CALCULATOR: Bars for {date_key} (showing first 5):")
        for i, bar in enumerate(day_bars_sorted[:5]):
            print(f"  Bar {i}: timestamp={bar['timestamp']}")

        # Match external script logic: Select the FIRST 5-minute candle that starts at or after 9:30 AM ET
        # External script: df[(df.index.time >= market_start) & (df.index.time <= market_end)].iloc[:1]
        # This gets the FIRST bar that starts at or after 9:30 AM ET and is within 9:30-9:35 AM ET window
        # Polygon bars are timestamped at the START of the 5-minute window, so:
        # - Bar at 9:30 AM ET = 9:30-9:35 AM ET window ✓ (what we want)
        # - Bar at 9:33 AM ET = 9:33-9:38 AM ET window ✗ (not what we want)
        market_start_time = market_open_et.time()  # 9:30 AM ET time component
        market_end_time = market_close_et.time()   # 9:35 AM ET time component
        
        # Find the bar that starts at exactly 9:30 AM ET (covers 9:30-9:35 AM ET)
        # If that doesn't exist, take the first bar that starts at or after 9:30 AM ET (but before 9:35 AM ET)
        # This matches the standalone script's logic: first bar >= 9:30 AM ET
        or_bar = None
        exact_match = None  # Bar that starts exactly at 9:30 AM ET
        for bar in day_bars_sorted:
            bar_time = bar["timestamp"].time()  # ET time component
            # First, try to find exact match at 9:30 AM ET
            if bar_time == market_start_time:
                exact_match = bar
                break  # Found exact match, use it
            # Also check for bars in the opening range window
            elif market_start_time <= bar_time < market_end_time:
                if or_bar is None:  # Take the first matching bar
                    or_bar = bar
        
        # Prefer exact match, otherwise use first candidate
        if exact_match:
            or_bar = exact_match
        
        # Debug: Log what we found (only log if we found a bar to reduce noise)
        if or_bar:
            print(f"ORB CALCULATOR: Looking for first bar starting at or after {market_start_time} (ET time)")
            print(f"ORB CALCULATOR: Found opening range bar: timestamp={or_bar['timestamp']} (ET), time={or_bar['timestamp'].time()}, volume={or_bar['volume']}")
        
        or_candidates = [or_bar] if or_bar else []

        if not or_bar:
            # Fallback: Use first available candle after market open if exact time not found
            # External script fallback: first_candle = daily_data.iloc[0] if exact time not found
            # But we want the first bar that starts at or after market open
            for bar in day_bars_sorted:
                bar_time = bar["timestamp"].time()
                if bar_time >= market_start_time:
                    or_bar = bar
                    logger.info(f"ORB CALCULATOR: Using fallback - first bar after market open for {date_key}")
                    break
            
            if not or_bar:
                # Last resort: use first available bar
                if day_bars_sorted:
                    or_bar = day_bars_sorted[0]
                    logger.info(f"ORB CALCULATOR: Using last resort fallback - first available candle for {date_key}")
                else:
                    print(f"ORB CALCULATOR: No opening range bar found for {date_key}")
                    print(f"ORB CALCULATOR: Looking for bars starting at or after {market_start_time} (ET time)")
                    logger.warning(f"ORB Calculator: No opening range bar found for {date_key}")
                    logger.warning(f"ORB CALCULATOR: Expected opening range start: {market_start_time} (ET)")
                    logger.warning(f"ORB CALCULATOR: Available bars for {date_key}: {len(day_bars_sorted)}")
                    if day_bars_sorted:
                        logger.warning(f"ORB CALCULATOR: First bar time: {day_bars_sorted[0]['timestamp']}")
                        logger.warning(f"ORB CALCULATOR: Last bar time: {day_bars_sorted[-1]['timestamp']}")
                    continue

        print(
            f"ORB CALCULATOR: Found opening range bar for {date_key}, using: {or_bar['timestamp']}"
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
    # Match standalone script: explicitly exclude target_date from average calculation
    target_volume_date = target_date if target_date in or_volumes else sorted_dates[-1]
    
    # Get all dates excluding target_date (matches standalone script's "if date == current_time.date(): continue")
    dates_excluding_target = [d for d in sorted_dates if d != target_date]
    
    # Take last avg_period days from dates excluding target
    if len(dates_excluding_target) >= avg_period:
        past_volumes = [or_volumes[d] for d in dates_excluding_target[-avg_period:]]
    else:
        past_volumes = [or_volumes[d] for d in dates_excluding_target]

    past_dates = dates_excluding_target[-avg_period:] if len(dates_excluding_target) >= avg_period else dates_excluding_target
    print(f"ORB CALCULATOR: Using {len(past_volumes)} past days for average (excluding target date {target_date})")
    print(f"ORB CALCULATOR: Past dates: {past_dates}")
    print(f"ORB CALCULATOR: Past volumes: {past_volumes}")
    logger.info(f"ORB Calculator: Using {len(past_volumes)} past days for average (excluding target date {target_date})")
    logger.info(f"ORB Calculator: Past dates: {past_dates}")
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
    # NOTE: OR High/Low should be FIXED once the opening range period (9:30-9:35 AM ET) is complete
    # If these values are changing, it means either:
    # 1. The opening range bar is still being formed (before 9:35 AM ET) - this is EXPECTED
    # 2. The opening range bar selection is inconsistent - this is a BUG
    # 3. The bars list is being updated with new data that affects the opening range bar - this is EXPECTED if before 9:35 AM ET
    target_or_bar = None
    opening_range_complete = False
    or_high = None
    or_low = None
    
    # Check if we're past the opening range period (after 9:35 AM ET for today)
    if target_date == today_date:
        opening_range_end_time = create_market_open_time(target_date, hour=9, minute=30) + timedelta(minutes=or_minutes)
        opening_range_complete = current_time_et > opening_range_end_time
        if opening_range_complete:
            logger.info(f"ORB CALCULATOR: Opening range period COMPLETE (current time {current_time_et} > {opening_range_end_time}) - OR High/Low should be FIXED")
        else:
            logger.info(f"ORB CALCULATOR: Opening range period IN PROGRESS (current time {current_time_et} < {opening_range_end_time}) - OR High/Low may change")
    
    if target_date in daily_groups:
        day_bars_sorted = sorted(daily_groups[target_date], key=lambda b: b["timestamp"])
        
        # Determine opening range time based on asset class
        # Match external script logic: Convert 9:30 AM ET to UTC for target date (handles DST automatically)
        et_tz = pytz.timezone("America/New_York")
        if symbol.asset_class == AssetClass.CRYPTO:
            # For crypto, use UTC midnight (00:00:00) as opening range
            utc_midnight = pytz.timezone("UTC").localize(
                datetime.combine(target_date, datetime.strptime("00:00", "%H:%M").time())
            )
            market_open_et = utc_midnight.astimezone(et_tz)
            market_open_utc = utc_midnight  # Already UTC
        else:
            # For stocks, use 9:30 AM Eastern as opening range
            # Convert this specific date's 9:30 AM ET to UTC (handles DST for that date)
            # This matches external script: et_tz.localize(datetime.combine(date, datetime.min.time().replace(hour=9, minute=30)))
            market_open_et = et_tz.localize(
                datetime.combine(target_date, datetime.min.time().replace(hour=9, minute=30))
            )
            market_open_utc = market_open_et.astimezone(pytz.timezone("UTC"))
        
        # Convert opening range end time to UTC as well
        market_close_et = market_open_et + timedelta(minutes=or_minutes)
        market_close_utc = market_close_et.astimezone(pytz.timezone("UTC"))
        
        # Match external script logic: For current day, use TIME COMPONENT filtering
        # External script uses: df[(df.index.time >= market_start) & (df.index.time <= market_end)]
        # where market_start and market_end are UTC time components
        # Since our bars are in ET timezone, we use ET time components directly
        market_start_time = market_open_et.time()  # 9:30 AM ET time component
        market_end_time = market_close_et.time()   # 9:35 AM ET time component
        
        print(f"ORB CALCULATOR: Looking for opening range bars between {market_start_time} and {market_end_time} (ET time)")
        print(f"ORB CALCULATOR: Market open ET: {market_open_et}, Market close ET: {market_close_et}")
        print(f"ORB CALCULATOR: Total bars for {target_date}: {len(day_bars_sorted)}")
        
        # Debug: Show bars around market open (9:25-9:40 AM) to see what's available
        print(f"ORB CALCULATOR: Bars around market open (9:25-9:40 AM ET) for {target_date}:")
        market_debug_start = datetime.min.time().replace(hour=9, minute=25)
        market_debug_end = datetime.min.time().replace(hour=9, minute=40)
        bars_around_open = [
            bar for bar in day_bars_sorted
            if market_debug_start <= bar["timestamp"].time() <= market_debug_end
        ]
        for i, bar in enumerate(bars_around_open[:10]):
            bar_time = bar["timestamp"].time()
            print(f"  Bar {i}: timestamp={bar['timestamp']}, time={bar_time}, high={bar['high']}, low={bar['low']}, volume={bar['volume']}")
        
        # Initialize variables before loop
        or_candidates = []
        first_or_bar = None
        
        # Filter by time component (09:30:00 <= start < 09:35:00)
        for bar in day_bars_sorted:
            bar_time = bar["timestamp"].time()  # ET time component
            # Collect ALL bars that START within the true opening-range window
            # We want bars beginning at 09:30, 09:31, 09:32, 09:33 or 09:34.
            # A bar stamped 09:35 covers 09:35-09:40 and is *outside* the 5-minute OR window,
            # so we use a strict < 09:35 comparison.
            if market_start_time <= bar_time < market_end_time:
                or_candidates.append(bar)
                if first_or_bar is None:
                    first_or_bar = bar  # First bar for volume calculation
                print(f"ORB CALCULATOR: Found opening range bar: timestamp={bar['timestamp']} (ET), time={bar_time}, high={bar['high']}, low={bar['low']}")
        
        # Use first bar for volume calculation (matches standalone script)
        if first_or_bar:
            or_candidates = [first_or_bar]  # Keep first bar for volume
        
        if not or_candidates:
            # Fallback: Use first available candle after market open if exact time not found
            # Standalone script fallback: market_hours_df = df[df.index.time >= market_start]
            # Then: opening_range_df = market_hours_df.iloc[:1]  # First 5-min candle
            market_hours_bars = [bar for bar in day_bars_sorted if bar["timestamp"].time() >= market_start_time]
            if market_hours_bars:
                print(f"ORB CALCULATOR: No bars found in exact opening range window, using first bar after market open")
                print(f"ORB CALCULATOR: First bar after market open: timestamp={market_hours_bars[0]['timestamp']}, high={market_hours_bars[0]['high']}, low={market_hours_bars[0]['low']}")
                or_candidates = [market_hours_bars[0]]  # First 5-min candle after market open (matches standalone script)
                logger.info(f"ORB CALCULATOR: Using fallback - first 5-min candle after market open for {target_date}")
            elif day_bars_sorted:
                print(f"ORB CALCULATOR: No bars found after market open, using first available bar")
                print(f"ORB CALCULATOR: First available bar: timestamp={day_bars_sorted[0]['timestamp']}, high={day_bars_sorted[0]['high']}, low={day_bars_sorted[0]['low']}")
                or_candidates = [day_bars_sorted[0]]  # Last resort fallback
                logger.info(f"ORB CALCULATOR: Using last resort fallback - first available candle for {target_date}")
        
        if or_candidates:
            # Use first bar for volume calculation (matches standalone script: opening_range_candles.iloc[:1])
            target_or_bar = or_candidates[0]
            
            # Match standalone script exactly: Use ONLY the first 5-minute bar (9:30 AM)
            # Standalone script: opening_range_df = opening_range_candles.iloc[:1]
            # This means OR High/Low comes from the FIRST bar only, not all bars
            or_high = target_or_bar["high"]
            or_low = target_or_bar["low"]
            print(f"ORB CALCULATOR: ✅ SELECTED Opening range bar for {target_date}: timestamp={target_or_bar['timestamp']} (ET)")
            print(f"ORB CALCULATOR: Using FIRST bar only for OR High/Low (matches standalone script)")
            print(f"ORB CALCULATOR: OR High=${or_high:.2f} (from first bar), OR Low=${or_low:.2f} (from first bar)")
            print(f"ORB CALCULATOR: Expected: OR High=$113.26, OR Low=$112.06 (from standalone script)")
            logger.info(f"ORB CALCULATOR: Opening range bar for {target_date}: timestamp={target_or_bar['timestamp']}, volume={target_or_bar['volume']}")
            logger.info(f"ORB CALCULATOR: OR High={or_high}, OR Low={or_low} (from first bar only)")
        else:
            logger.warning(f"ORB CALCULATOR: No opening range bar found for {target_date}")
            print(f"ORB CALCULATOR: No opening range bar found for {target_date}")
            or_high = None
            or_low = None
    
    # Log final OR High/Low values with status
    if target_date == today_date:
        status_note = "✅ FIXED" if opening_range_complete else "⚠️ MAY CHANGE (opening range still forming)"
        logger.info(f"ORB CALCULATOR: Final OR High: {or_high}, OR Low: {or_low} - {status_note}")
        print(f"ORB CALCULATOR: Final OR High: {or_high}, OR Low: {or_low} - {status_note}")
    else:
        logger.info(f"ORB CALCULATOR: Final OR High: {or_high}, OR Low: {or_low} (historical date - should be fixed)")
        print(f"ORB CALCULATOR: Final OR High: {or_high}, OR Low: {or_low} (historical date - should be fixed)")

    return {
        "rel_vol": rel_vol,
        "direction": direction,
        "or_high": or_high,
        "or_low": or_low,
    }
