from collections.abc import Sequence
from typing import Any


def calculate_rsi(values: Sequence[float | None], length: int = 14) -> dict[str, Any]:
    """
    Calculate RSI (Relative Strength Index) indicator.

    Args:
        values: List of values to calculate RSI on (can contain None values)
        length: Period for RSI calculation (default: 14)

    Returns:
        Dictionary with 'rsi' as a list of calculated values for each row,
        matching the TypeScript implementation that returns full time series.
        Each list contains the calculated values for corresponding rows in the input data.
    """
    if length <= 0:
        return {"rsi": [None] * len(values)}

    results: list[float | None] = []
    avg_gain = 0.0
    avg_loss = 0.0
    consecutive_valid = 0
    init_calculated = False

    for i in range(len(values)):
        if i == 0:
            results.append(None)
            current_val = values[i]
            consecutive_valid = 1 if current_val is not None else 0
            continue

        current = values[i]
        prev = values[i - 1]

        if current is None or prev is None:
            results.append(None)
            avg_gain = 0.0
            avg_loss = 0.0
            init_calculated = False
            consecutive_valid = 1 if current is not None else 0
            continue

        consecutive_valid += 1

        change = current - prev
        gain = change if change > 0 else 0.0
        loss = -change if change < 0 else 0.0

        if init_calculated:
            avg_gain = (avg_gain * (length - 1) + gain) / length
            avg_loss = (avg_loss * (length - 1) + loss) / length
            if avg_loss == 0:
                results.append(100.0)
            else:
                rs = avg_gain / avg_loss
                rsi = 100 - (100 / (1 + rs))
                results.append(rsi)
        else:
            avg_gain += gain
            avg_loss += loss
            if consecutive_valid == length + 1:
                avg_gain /= length
                avg_loss /= length
                init_calculated = True
                if avg_loss == 0:
                    results.append(100.0)
                else:
                    rs = avg_gain / avg_loss
                    rsi = 100 - (100 / (1 + rs))
                    results.append(rsi)
            else:
                results.append(None)

    return {"rsi": results}
