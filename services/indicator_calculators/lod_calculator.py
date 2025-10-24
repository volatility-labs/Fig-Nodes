from collections.abc import Sequence

from .atr_calculator import calculate_atr


def calculate_lod(
    highs: Sequence[float | None],
    lows: Sequence[float | None],
    closes: Sequence[float | None],
    atr_window: int = 14,
) -> dict[str, list[float | None]]:
    """
    Calculate LoD (Low of Day Distance) indicator.

    LoD Distance measures the distance of current price from the low of the day
    as a percentage of ATR (Average True Range).

    Formula: LoD Distance % = ((current_price - low_of_day) / ATR) * 100

    Args:
        highs: List of high prices (can contain None values)
        lows: List of low prices (can contain None values)
        closes: List of close prices (can contain None values)
        atr_window: Period for ATR calculation (default: 14)

    Returns:
        Dictionary with 'lod_distance_pct', 'current_price', 'low_of_day', and 'atr'
        as lists of calculated values for each row, matching the TypeScript implementation
        that returns full time series.

    Reference:
        https://www.tradingview.com/script/uloAa2EI-Swing-Data-ADR-RVol-PVol-Float-Avg-Vol/

    Example:
        Current price (A) = $24.49
        Low Price (B) = $22.16
        Difference (A) - (B) = $2.33
        ATR = $2.25
        LoD dist = $2.33 / $2.25 = 103.55% (round up to nearest whole number = 104%)
    """
    data_length = len(highs)

    if atr_window <= 0 or data_length == 0:
        return {
            "lod_distance_pct": [None] * data_length,
            "current_price": [None] * data_length,
            "low_of_day": [None] * data_length,
            "atr": [None] * data_length,
        }

    if len(lows) != data_length or len(closes) != data_length:
        return {
            "lod_distance_pct": [None] * data_length,
            "current_price": [None] * data_length,
            "low_of_day": [None] * data_length,
            "atr": [None] * data_length,
        }

    # Calculate ATR using Wilder's smoothing (RMA)
    atr_result = calculate_atr(highs, lows, closes, atr_window)
    atr_values = atr_result.get("atr", [])

    if not atr_values or len(atr_values) != data_length:
        return {
            "lod_distance_pct": [None] * data_length,
            "current_price": [None] * data_length,
            "low_of_day": [None] * data_length,
            "atr": [None] * data_length,
        }

    # Calculate LoD Distance for each point
    lod_distance_pct: list[float | None] = []
    current_prices: list[float | None] = []
    low_of_days: list[float | None] = []

    for i in range(data_length):
        current_price = closes[i]
        low_of_day = lows[i]
        atr = atr_values[i]

        current_prices.append(current_price)
        low_of_days.append(low_of_day)

        # Check for invalid values
        if current_price is None or low_of_day is None or atr is None or atr <= 0:
            lod_distance_pct.append(None)
            continue

        # Calculate LoD Distance as percentage of ATR
        # LoD Distance % = ((current_price - low_of_day) / ATR) * 100
        lod_distance = ((current_price - low_of_day) / atr) * 100

        # Ensure non-negative distance
        lod_distance_pct.append(max(0.0, lod_distance))

    return {
        "lod_distance_pct": lod_distance_pct,
        "current_price": current_prices,
        "low_of_day": low_of_days,
        "atr": atr_values,
    }
