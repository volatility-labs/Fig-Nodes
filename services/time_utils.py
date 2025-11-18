"""Time utility functions for handling timezone conversions and timestamp calculations."""

from datetime import datetime
from typing import Any

import pytz


def is_us_market_open() -> bool:
    """
    Check if US stock market is currently open (9:30 AM ET - 4:00 PM ET, Mon-Fri).

    Returns:
        True if market is open, False otherwise.
    """
    et_tz = pytz.timezone("US/Eastern")
    now_et = datetime.now(et_tz)

    # Check if it's a weekday (Monday=0, Sunday=6)
    if now_et.weekday() >= 5:  # Saturday or Sunday
        return False

    # Check if within market hours (9:30 AM - 4:00 PM ET)
    market_open = now_et.replace(hour=9, minute=30, second=0, microsecond=0)
    market_close = now_et.replace(hour=16, minute=0, second=0, microsecond=0)

    return market_open <= now_et <= market_close


def et_time_to_utc_timestamp_ms(year: int, month: int, day: int, hour: int, minute: int) -> int:
    """
    Convert Eastern Time to UTC timestamp in milliseconds.

    Args:
        year: Year (e.g., 2025)
        month: Month (1-12)
        day: Day of month
        hour: Hour (0-23)
        minute: Minute (0-59)

    Returns:
        UTC timestamp in milliseconds

    Example:
        >>> et_time_to_utc_timestamp_ms(2025, 10, 26, 9, 30)
        1729954200000  # UTC timestamp for Oct 26, 2025 9:30 AM ET
    """
    et_tz = pytz.timezone("US/Eastern")
    dt = et_tz.localize(datetime(year, month, day, hour, minute))
    return int(dt.astimezone(pytz.UTC).timestamp() * 1000)


def utc_timestamp_ms_to_et_datetime(timestamp_ms: int) -> datetime:
    """
    Convert UTC timestamp in milliseconds to Eastern Time datetime.

    Args:
        timestamp_ms: UTC timestamp in milliseconds

    Returns:
        Datetime object in Eastern Time timezone

    Example:
        >>> utc_timestamp_ms_to_et_datetime(1729954200000)
        datetime.datetime(2025, 10, 26, 9, 30, tzinfo=<DstTzInfo 'US/Eastern' EDT-1 day, 20:00:00 DST>)
    """
    dt = datetime.fromtimestamp(timestamp_ms / 1000, tz=pytz.UTC)
    return dt.astimezone(pytz.timezone("US/Eastern"))


def create_market_open_time(date_key: Any, hour: int = 9, minute: int = 30) -> datetime:
    """
    Create a market open time datetime in Eastern Timezone.

    Args:
        date_key: Date object or anything with year, month, day attributes
        hour: Hour of the day (default: 9 for 9 AM)
        minute: Minute of the hour (default: 30 for 9:30 AM)

    Returns:
        Datetime object in Eastern Time timezone

    Example:
        >>> from datetime import date
        >>> create_market_open_time(date(2025, 10, 26))
        datetime.datetime(2025, 10, 26, 9, 30, tzinfo=<DstTzInfo 'US/Eastern' EDT-1 day, 20:00:00 DST>)
    """
    et_tz = pytz.timezone("US/Eastern")
    return et_tz.localize(datetime(date_key.year, date_key.month, date_key.day, hour, minute))


def utc_timestamp_flex_to_et_datetime(ts: int) -> datetime | None:
    """
    Convert UTC timestamp (int) to Eastern Time datetime, auto-detecting unit: seconds (s), milliseconds (ms), or nanoseconds (ns).

    Detection logic:
    - Based on digit count of ts (str(ts)):
      - <11 digits: Assume s (e.g., 1730000000).
      - 11-14 digits: Assume ms (e.g., 1730000000000).
      - 15-19 digits: Assume ns (e.g., 1730000000000000000).
      - Else: Default to ms.
    - Tries in order: ns → ms → s. First valid (year 1970-2100) wins.
    - Handles ts=0/negative as invalid (returns None).

    Args:
        ts: UTC timestamp integer (s, ms, or ns).

    Returns:
        ET-aware datetime if valid; None if unparseable (logs warning).

    Example:
        >>> utc_timestamp_flex_to_et_datetime(1730000000000000000)  # ns
        datetime.datetime(2024, 10, 20, 12, 0, tzinfo=...)  # Approx, in ET
        >>> utc_timestamp_flex_to_et_datetime(1730000000000)    # ms
        Same as above.
        >>> utc_timestamp_flex_to_et_datetime(1730000000)      # s
        Same as above.
    """
    if ts <= 0:
        import logging

        logging.getLogger(__name__).warning(f"Invalid timestamp {ts} (<=0); returning None")
        return None

    ts_str = str(ts)
    digit_count = len(ts_str)

    # Initial guess based on digits
    if digit_count < 11:
        candidates = [("s", 1)]
    elif 11 <= digit_count <= 14:
        candidates = [("ms", 1000)]
    elif 15 <= digit_count <= 19:
        candidates = [("ns", 1_000_000_000)]
    else:
        candidates = [("ms", 1000)]  # Default for unknown

    # For robustness, try all in order: ns → ms → s (override digit guess if needed)
    full_candidates = [
        ("ns", 1_000_000_000),
        ("ms", 1000),
        ("s", 1),
    ]

    for unit, divisor in full_candidates:
        try:
            ts_seconds = ts / divisor
            dt_utc = datetime.fromtimestamp(ts_seconds, tz=pytz.UTC)
            # Validate: Unix epoch range (1970-2100)
            if 1970 <= dt_utc.year <= 2100:
                et_dt = dt_utc.astimezone(pytz.timezone("US/Eastern"))
                import logging

                logging.getLogger(__name__).debug(f"Parsed {ts} as {unit} -> {et_dt}")
                return et_dt
        except (ValueError, OSError, OverflowError):
            continue  # Try next unit

    import logging

    logging.getLogger(__name__).warning(
        f"Could not parse timestamp {ts} (digits: {digit_count}); all units invalid"
    )
    return None


def get_timezone_for_asset_class(asset_class: Any) -> pytz.BaseTzInfo:
    """
    Get the appropriate timezone for an asset class.
    
    Args:
        asset_class: AssetClass enum (CRYPTO or STOCKS)
    
    Returns:
        pytz timezone object:
        - UTC for crypto (bars are at UTC midnight)
        - US/Eastern for stocks (bars are at market open/close ET)
    
    Example:
        >>> from core.types_registry import AssetClass
        >>> get_timezone_for_asset_class(AssetClass.CRYPTO)
        <DstTzInfo 'UTC' ...>
        >>> get_timezone_for_asset_class(AssetClass.STOCKS)
        <DstTzInfo 'US/Eastern' ...>
    """
    import logging
    from core.types_registry import AssetClass
    
    logger = logging.getLogger(__name__)
    
    if asset_class == AssetClass.CRYPTO:
        tz = pytz.timezone("UTC")
        logger.debug(f"Using UTC timezone for CRYPTO asset class")
        return tz
    elif asset_class == AssetClass.STOCKS:
        tz = pytz.timezone("US/Eastern")
        logger.debug(f"Using US/Eastern timezone for STOCKS asset class")
        return tz
    else:
        # Default to UTC for unknown asset classes
        logger.warning(f"Unknown asset_class {asset_class}, defaulting to UTC")
        return pytz.timezone("UTC")


def utc_timestamp_ms_to_datetime(
    timestamp_ms: int, 
    target_tz: pytz.BaseTzInfo | None = None
) -> datetime:
    """
    Convert UTC timestamp in milliseconds to datetime in target timezone.
    
    Args:
        timestamp_ms: UTC timestamp in milliseconds
        target_tz: Target timezone (defaults to UTC if None)
    
    Returns:
        Datetime object in target timezone
    
    Example:
        >>> tz = pytz.timezone("US/Eastern")
        >>> utc_timestamp_ms_to_datetime(1729954200000, tz)
        datetime.datetime(2025, 10, 26, 5, 30, tzinfo=...)
    """
    dt_utc = datetime.fromtimestamp(timestamp_ms / 1000, tz=pytz.UTC)
    if target_tz is None:
        return dt_utc
    return dt_utc.astimezone(target_tz)


def convert_timestamps_to_datetimes(
    timestamps_ms: list[int],
    asset_class: Any,
) -> list[datetime]:
    """
    Convert list of UTC timestamps (ms) to datetimes in appropriate timezone.
    
    Args:
        timestamps_ms: List of UTC timestamps in milliseconds
        asset_class: AssetClass enum (CRYPTO or STOCKS)
    
    Returns:
        List of datetime objects in appropriate timezone
    
    Example:
        >>> from core.types_registry import AssetClass
        >>> timestamps = [1729954200000, 1730040600000]
        >>> convert_timestamps_to_datetimes(timestamps, AssetClass.CRYPTO)
        [datetime.datetime(2025, 10, 26, 0, 0, tzinfo=<UTC>), ...]
    """
    import logging
    logger = logging.getLogger(__name__)
    
    target_tz = get_timezone_for_asset_class(asset_class)
    logger.debug(f"Converting {len(timestamps_ms)} timestamps to {target_tz} timezone")
    
    result = [
        utc_timestamp_ms_to_datetime(ts, target_tz) for ts in timestamps_ms
    ]
    
    if result:
        logger.debug(
            f"First timestamp: {timestamps_ms[0]} -> {result[0]}, "
            f"Last timestamp: {timestamps_ms[-1]} -> {result[-1]}"
        )
    
    return result
