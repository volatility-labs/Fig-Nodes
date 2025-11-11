from collections.abc import Sequence
from typing import Any

from .utils import calculate_wilder_ma


def calculate_rma(values: Sequence[float | None], period: int) -> dict[str, Any]:
    """
    Calculate RMA (Relative Moving Average / Wilder's Moving Average) indicator.

    Args:
        values: List of values to calculate RMA on (can contain None values)
        period: Period for RMA calculation

    Returns:
        Dictionary with 'rma' as a list of calculated values for each row,
        matching the TypeScript implementation that returns full time series.
        Each list contains the calculated values for corresponding rows in the input data.

    Reference:
        https://www.tradingcode.net/tradingview/relative-moving-average/
    """
    if period <= 0:
        return {"rma": [None] * len(values)}

    # Convert Sequence to list for calculate_wilder_ma
    values_list = list(values)
    # Use Wilder's MA from utils
    rma_values = calculate_wilder_ma(values_list, period)

    return {"rma": rma_values}
