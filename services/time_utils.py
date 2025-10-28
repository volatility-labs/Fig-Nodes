"""Time utility functions for handling timezone conversions and timestamp calculations."""

from datetime import datetime
from typing import Any

import pytz


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
