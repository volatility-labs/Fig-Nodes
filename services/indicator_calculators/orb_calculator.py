from collections.abc import Sequence
from datetime import date, datetime, timedelta
from typing import Any

import pytz

from core.types_registry import AssetClass, AssetSymbol, OHLCVBar


def calculate_orb(
    bars: Sequence[OHLCVBar],
    symbol: AssetSymbol,
    or_minutes: int = 5,
    avg_period: int = 14,
) -> dict[str, Any]:
    """
    Calculate ORB (Opening Range Breakout) indicator including relative volume and direction.

    This implementation extracts opening range data from minute bars and calculates:
    1. Relative Volume: Current opening range volume vs average of previous periods
    2. Direction: Bullish, bearish, or doji based on opening range price movement

    Args:
        bars: List of 1-minute OHLCV bars
        symbol: Asset symbol (used to determine opening range time based on asset class)
        or_minutes: Opening range period in minutes (default: 5)
        avg_period: Period for calculating average volume (default: 14 days)

    Returns:
        Dictionary with 'rel_vol' (relative volume as percentage) and 'direction' (bullish/bearish/doji)

    Reference Paper Implementation:
        The paper uses:
        - Relative Volume = (Volume in first n minutes) / (Avg of last 14 days) * 100
        - This matches our implementation

        Note: The paper also mentions ATR filtering (> $0.50 over 14 days) but that is
        a separate filter, not part of the ORB calculation itself.
    """
    if not bars or len(bars) == 0:
        return {"rel_vol": None, "direction": None, "error": "No bars provided"}

    # Convert timestamps to datetime objects (assuming milliseconds)
    bar_data: list[dict[str, Any]] = []
    for bar in bars:
        dt = datetime.fromtimestamp(bar["timestamp"] / 1000, tz=pytz.UTC)
        bar_data.append(
            {
                "timestamp": dt.astimezone(pytz.timezone("US/Eastern")),
                "open": bar["open"],
                "high": bar["high"],
                "low": bar["low"],
                "close": bar["close"],
                "volume": bar["volume"],
            }
        )

    # Group bars by date
    daily_groups: dict[date, list[dict[str, Any]]] = {}
    for bar_dict in bar_data:
        bar_date = bar_dict["timestamp"].date()
        if bar_date not in daily_groups:
            daily_groups[bar_date] = []
        daily_groups[bar_date].append(bar_dict)

    # Calculate opening range volumes and directions for each day
    or_volumes: dict[date, float] = {}
    or_directions: dict[date, str] = {}
    today_date = datetime.now(pytz.timezone("US/Eastern")).date()

    for date_key, day_bars in daily_groups.items():
        # Determine opening range time based on asset class
        if symbol.asset_class == AssetClass.CRYPTO:
            # For crypto, use UTC midnight (00:00:00) as opening range
            open_time = (
                datetime.combine(date_key, datetime.strptime("00:00", "%H:%M").time())
                .replace(tzinfo=pytz.timezone("UTC"))
                .astimezone(pytz.timezone("US/Eastern"))
            )
        else:
            # For stocks, use 9:30 AM Eastern as opening range
            open_time = datetime.combine(
                date_key, datetime.strptime("09:30", "%H:%M").time()
            ).replace(tzinfo=pytz.timezone("US/Eastern"))

        close_time = open_time + timedelta(minutes=or_minutes)

        # Filter bars within opening range
        or_bars = [bar for bar in day_bars if open_time <= bar["timestamp"] < close_time]

        if not or_bars:
            continue

        # Calculate opening range metrics
        or_volume = sum(bar["volume"] for bar in or_bars)
        or_open = or_bars[0]["open"]
        or_close = or_bars[-1]["close"]

        # Determine direction
        if or_close > or_open:
            direction = "bullish"
        elif or_close < or_open:
            direction = "bearish"
        else:
            direction = "doji"

        or_volumes[date_key] = or_volume
        or_directions[date_key] = direction

    # Calculate relative volume
    sorted_dates = sorted(or_volumes.keys())
    if len(sorted_dates) < 2:
        return {"rel_vol": None, "direction": None, "error": "Insufficient days"}

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

    # Calculate average volume from past periods (excluding target date)
    target_volume_date = target_date if target_date in or_volumes else sorted_dates[-1]

    # Get past volumes for averaging
    if len(sorted_dates) > avg_period:
        past_volumes = [or_volumes[d] for d in sorted_dates[-avg_period - 1 : -1]]
    else:
        past_volumes = [or_volumes[d] for d in sorted_dates[:-1]]

    if not past_volumes:
        avg_vol = 0.0
    else:
        avg_vol = sum(past_volumes) / len(past_volumes)

    current_vol = or_volumes.get(target_volume_date, 0.0)
    rel_vol = (current_vol / avg_vol * 100) if avg_vol > 0 else 0.0

    # Get direction for target date
    direction = or_directions.get(target_date, "doji")

    return {
        "rel_vol": rel_vol,
        "direction": direction,
    }
