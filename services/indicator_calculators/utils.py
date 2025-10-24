from collections.abc import Callable


def rolling_calculation(
    data: list[float | None], period: int, callback: Callable[[list[float | None]], float | None]
) -> list[float | None]:
    """
    Helper for generic rolling window calculations.
    Applies a callback function to each window of a specified period.
    Handles initial null padding.
    """
    if period <= 0 or len(data) == 0:
        return [None] * len(data)

    results: list[float | None] = [None] * len(data)

    for i in range(period - 1, len(data)):
        window_data = data[i - period + 1 : i + 1]
        if len(window_data) == period:
            results[i] = callback(window_data)

    return results


def rolling_max(data: list[float | None], period: int) -> list[float | None]:
    """
    Calculates the rolling maximum over a given period, ignoring nulls.
    """
    return rolling_calculation(
        data,
        period,
        lambda window: max([v for v in window if v is not None])
        if any(v is not None for v in window)
        else None,
    )


def rolling_min(data: list[float | None], period: int) -> list[float | None]:
    """
    Calculates the rolling minimum over a given period, ignoring nulls.
    """
    return rolling_calculation(
        data,
        period,
        lambda window: min([v for v in window if v is not None])
        if any(v is not None for v in window)
        else None,
    )


def calculate_rolling_mean(data: list[float | None], period: int) -> list[float | None]:
    """
    Calculates the rolling mean (Simple Moving Average - SMA), ignoring null values.

    Args:
        data: The input array of numbers (can contain None).
        period: The lookback period for the moving average.

    Returns:
        An array containing the SMA values, with initial nulls.
    """
    return rolling_calculation(
        data,
        period,
        lambda window: (
            sum([v for v in window if v is not None]) / len([v for v in window if v is not None])
            if any(v is not None for v in window)
            else None
        ),
    )


def calculate_rolling_sum_strict(data: list[float | None], period: int) -> list[float | None]:
    """
    Calculates the rolling sum, returning None if any value in the window is None.

    Args:
        data: The input array of numbers (can contain None).
        period: The lookback period for the rolling sum.

    Returns:
        An array containing the rolling sum values, with initial nulls and nulls for windows containing None.
    """
    return rolling_calculation(
        data,
        period,
        lambda window: None if any(v is None for v in window) else sum(window),  # type: ignore
    )


def calculate_rolling_std_dev(data: list[float | None], period: int) -> list[float | None]:
    """
    Calculates the rolling population standard deviation.
    Ignores nulls in the window. Returns None if fewer than 2 points.

    Args:
        data: The input array of numbers (can contain None).
        period: The lookback period for the standard deviation.

    Returns:
        An array containing the rolling standard deviation values.
    """

    def _calculate_std_dev(window: list[float | None]) -> float | None:
        valid_values = [v for v in window if v is not None]
        if len(valid_values) < 2:
            return None

        mean = sum(valid_values) / len(valid_values)
        variance = sum((val - mean) ** 2 for val in valid_values) / len(valid_values)
        return variance**0.5 if variance >= 0 else 0.0

    return rolling_calculation(data, period, _calculate_std_dev)


def calculate_wilder_ma(data: list[float | None], period: int) -> list[float | None]:
    """
    Calculates Wilder's Smoothing Average (RMA).
    This is similar to EMA but uses alpha = 1 / period.
    Correctly handles None values by carrying forward the previous valid MA.

    Args:
        data: The input array of numbers (can contain None).
        period: The smoothing period.

    Returns:
        An array containing the Wilder's smoothed values, with initial nulls.
    """
    if period <= 0 or len(data) < period:
        return [None] * len(data)

    results: list[float | None] = [None] * len(data)

    first_valid_index = -1
    for i in range(period - 1, len(data)):
        window = data[i - period + 1 : i + 1]
        valid_values = [v for v in window if v is not None]
        if len(valid_values) == period:
            first_valid_index = i
            break

    if first_valid_index == -1:
        return results

    seed_window = data[first_valid_index - period + 1 : first_valid_index + 1]
    results[first_valid_index] = sum(seed_window) / period  # type: ignore

    for i in range(first_valid_index + 1, len(data)):
        prev_ma = results[i - 1]
        current_value = data[i]

        if current_value is not None:
            if prev_ma is not None:
                results[i] = (prev_ma * (period - 1) + current_value) / period
            else:
                window = data[i - period + 1 : i + 1]
                valid_values = [v for v in window if v is not None]
                if len(valid_values) == period:
                    results[i] = sum(valid_values) / period
                else:
                    results[i] = None
        else:
            results[i] = prev_ma if prev_ma is not None else None

    return results
