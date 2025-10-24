from collections.abc import Sequence
from typing import Any


def calculate_ema(values: Sequence[float | None], period: int) -> dict[str, Any]:
    """
    Calculate EMA (Exponential Moving Average) indicator.

    Args:
        values: List of values to calculate EMA on (can contain None values)
        period: Period for EMA calculation

    Returns:
        Dictionary with 'ema' as a list of calculated values for each row,
        matching the TypeScript implementation that returns full time series.
        Each list contains the calculated values for corresponding rows in the input data.
    """
    if period <= 0:
        return {"ema": [None] * len(values)}

    results: list[float | None] = [None] * len(values)
    k = 2 / (period + 1)
    ema: float | None = None

    for i in range(len(values)):
        value = values[i]

        if value is None:
            ema = None
            continue

        if ema is None:
            # Try to find a valid window to initialize EMA
            window_start = max(0, i - period + 1)
            window = values[window_start : i + 1]
            valid_values = [v for v in window if v is not None]

            if len(valid_values) == period:
                ema = sum(valid_values) / period
        else:
            ema = value * k + ema * (1 - k)

        if i >= period - 1:
            results[i] = ema

    return {"ema": results}
