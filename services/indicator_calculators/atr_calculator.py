from collections.abc import Sequence
from typing import Any

from .ema_calculator import calculate_ema
from .sma_calculator import calculate_sma
from .utils import calculate_wilder_ma


def calculate_tr(high: float | None, low: float | None, prev_close: float | None) -> float | None:
    """
    Calculate True Range for a single point.

    Args:
        high: Current high price
        low: Current low price
        prev_close: Previous close price (None for first point or if previous close is null)

    Returns:
        True Range value or None
    """
    # If no previous point, or current values are null, or previous close is null
    if high is None or low is None or prev_close is None:
        # For the very first point, TR is just High - Low
        if high is not None and low is not None:
            return high - low
        return None

    high_low = high - low
    high_close = abs(high - prev_close)
    low_close = abs(low - prev_close)

    return max(high_low, high_close, low_close)


def calculate_atr(
    highs: Sequence[float | None],
    lows: Sequence[float | None],
    closes: Sequence[float | None],
    length: int,
    smoothing: str = "RMA",
) -> dict[str, Any]:
    """
    Calculate ATR (Average True Range) indicator.

    Args:
        highs: List of high prices (can contain None values)
        lows: List of low prices (can contain None values)
        closes: List of close prices (can contain None values)
        length: Period for ATR calculation
        smoothing: Smoothing method - "RMA" (default), "SMA", or "EMA"

    Returns:
        Dictionary with 'atr' as a list of calculated values for each row,
        matching the TypeScript implementation that returns full time series.
        Each list contains the calculated values for corresponding rows in the input data.
    """
    data_length = len(highs)

    if length <= 0 or data_length == 0:
        return {"atr": [None] * data_length}

    if len(lows) != data_length or len(closes) != data_length:
        return {"atr": [None] * data_length}

    # Calculate True Range values
    tr_values: list[float | None] = []

    for i in range(data_length):
        current_high: float | None = highs[i]
        current_low: float | None = lows[i]
        prev_close: float | None = closes[i - 1] if i > 0 else None
        tr_val = calculate_tr(current_high, current_low, prev_close)
        tr_values.append(tr_val)

    # Calculate ATR using selected smoothing method
    if smoothing == "SMA":
        sma_result = calculate_sma(tr_values, period=length)
        atr_values = sma_result.get("sma", [])
    elif smoothing == "EMA":
        ema_result = calculate_ema(tr_values, period=length)
        atr_values = ema_result.get("ema", [])
    else:  # Default to RMA
        atr_values = calculate_wilder_ma(tr_values, length)

    # Return full time series matching TypeScript implementation
    return {"atr": atr_values}
