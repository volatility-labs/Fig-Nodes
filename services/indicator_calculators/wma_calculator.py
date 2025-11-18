from collections.abc import Sequence
from typing import Any


def calculate_wma(values: Sequence[float | None], period: int) -> dict[str, Any]:
    """
    Calculate WMA (Weighted Moving Average) indicator.

    Args:
        values: List of values to calculate WMA on (can contain None values)
        period: Period for WMA calculation

    Returns:
        Dictionary with 'wma' as a list of calculated values for each row,
        matching the TypeScript implementation that returns full time series.
        Each list contains the calculated values for corresponding rows in the input data.
    """
    if period <= 0:
        raise ValueError("WMA period must be greater than 0.")

    results: list[float | None] = []
    divisor = (period * (period + 1)) / 2

    for i in range(len(values)):
        if i < period - 1:
            results.append(None)
            continue

        window = values[i - period + 1 : i + 1]

        # Check if any value in window is None
        if any(v is None for v in window):
            results.append(None)
            continue

        # Calculate weighted sum (all values are guaranteed to be float at this point)
        # Type narrowing: after the None check, window contains only floats
        window_floats: list[float] = [v for v in window if v is not None]
        weighted_sum = sum(val * (idx + 1) for idx, val in enumerate(window_floats))
        results.append(weighted_sum / divisor)

    return {"wma": results}
