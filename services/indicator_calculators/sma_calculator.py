from collections.abc import Sequence
from typing import Any


def calculate_sma(values: Sequence[float | None], period: int) -> dict[str, Any]:
    """
    Calculate SMA (Simple Moving Average) indicator.

    Args:
        values: List of values to calculate SMA on (can contain None values)
        period: Period for SMA calculation

    Returns:
        Dictionary with 'sma' as a list of calculated values for each row,
        matching the TypeScript implementation that returns full time series.
        Each list contains the calculated values for corresponding rows in the input data.
    """
    if period <= 0:
        return {"sma": [None] * len(values)}

    results: list[float | None] = []
    sum_val = 0.0
    period_values: list[float] = []

    for i in range(len(values)):
        value = values[i]
        if value is not None:
            period_values.append(value)
            sum_val += value

        if i >= period:
            exiting_value = period_values.pop(0)
            sum_val -= exiting_value

        if i >= period - 1:
            valid_count = len(period_values)
            if valid_count > 0:
                results.append(sum_val / valid_count)
            else:
                results.append(None)
        else:
            results.append(None)

    return {"sma": results}
