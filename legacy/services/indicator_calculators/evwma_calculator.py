from collections.abc import Sequence
from typing import Any

from core.types_registry import OHLCVBar


def calculate_evwma(
    bars: Sequence[OHLCVBar],
    length: int,
    use_cum_volume: bool = False,
    roll_window: int | None = None,
) -> dict[str, Any]:
    """
    Calculate EVWMA (Exponential Volume Weighted Moving Average).

    EVWMA combines volume-weighted price with exponential smoothing:
    1. Calculate typical price (HLC/3)
    2. Calculate volume-weighted price (typical_price * volume)
    3. Use either cumulative volume or rolling window volume
    4. Calculate VWMA = volume_weighted_price_sum / volume_sum
    5. Apply exponential smoothing with alpha = 2 / (length + 1)

    Args:
        bars: List of OHLCV bars
        length: Period for exponential smoothing
        use_cum_volume: If True, use cumulative volume; if False, use rolling window
        roll_window: Window size for rolling volume (required if use_cum_volume=False)

    Returns:
        Dictionary with 'evwma' as a list of calculated values for each bar.
        Returns None for bars before sufficient data is available.
    """
    if length <= 0:
        return {"evwma": [None] * len(bars)}

    if not use_cum_volume and roll_window is None:
        raise ValueError("roll_window must be provided when use_cum_volume=False")

    if roll_window is None:
        roll_window = length

    if not bars or len(bars) == 0:
        return {"evwma": []}

    results: list[float | None] = [None] * len(bars)

    # Calculate typical price and volume-weighted price for each bar
    typical_prices: list[float] = []
    vwp_values: list[float] = []  # volume-weighted price
    volumes: list[float] = []

    for bar in bars:
        typical_price = (bar["high"] + bar["low"] + bar["close"]) / 3.0
        volume = bar.get("volume", 0.0) or 0.0
        typical_prices.append(typical_price)
        vwp_values.append(typical_price * volume)
        volumes.append(volume)

    # Calculate VWMA (volume-weighted moving average) for each bar
    vwma_values: list[float | None] = []

    if use_cum_volume:
        # Use cumulative volume
        cum_vwp = 0.0
        cum_volume = 0.0

        for i in range(len(bars)):
            cum_vwp += vwp_values[i]
            cum_volume += volumes[i]

            if cum_volume > 0:
                vwma_values.append(cum_vwp / cum_volume)
            else:
                vwma_values.append(None)
    else:
        # Use rolling window volume
        for i in range(len(bars)):
            window_start = max(0, i - roll_window + 1)
            window_vwp = sum(vwp_values[window_start : i + 1])
            window_volume = sum(volumes[window_start : i + 1])

            if window_volume > 0:
                vwma_values.append(window_vwp / window_volume)
            else:
                vwma_values.append(None)

    # Apply exponential smoothing to VWMA values
    alpha = 2.0 / (length + 1)
    evwma: float | None = None

    for i in range(len(bars)):
        vwma = vwma_values[i]

        if vwma is None:
            evwma = None
            continue

        if evwma is None:
            # Try to find a valid window to initialize EVWMA
            window_start = max(0, i - length + 1)
            window = vwma_values[window_start : i + 1]
            valid_values = [v for v in window if v is not None]

            if len(valid_values) >= length:
                # Initialize with simple average of first length values
                evwma = sum(valid_values[:length]) / length
            else:
                continue

        # Apply exponential smoothing
        evwma = vwma * alpha + evwma * (1 - alpha)

        # Only set result if we have enough data
        if i >= length - 1:
            results[i] = evwma

    return {"evwma": results}


def calculate_rolling_correlation(
    x: list[float | None], y: list[float | None], window: int
) -> list[float | None]:
    """
    Calculate rolling correlation between two series.

    Args:
        x: First series (can contain None values)
        y: Second series (can contain None values)
        window: Window size for rolling correlation

    Returns:
        List of correlation values, with None for insufficient data
    """
    if len(x) != len(y):
        raise ValueError("Series x and y must have the same length")

    if window <= 0:
        return [None] * len(x)

    results: list[float | None] = [None] * len(x)

    for i in range(window - 1, len(x)):
        window_x = x[i - window + 1 : i + 1]
        window_y = y[i - window + 1 : i + 1]

        # Filter out None values
        valid_pairs = [(a, b) for a, b in zip(window_x, window_y) if a is not None and b is not None]

        if len(valid_pairs) < 2:
            results[i] = None
            continue

        valid_x = [pair[0] for pair in valid_pairs]
        valid_y = [pair[1] for pair in valid_pairs]

        # Calculate mean
        mean_x = sum(valid_x) / len(valid_x)
        mean_y = sum(valid_y) / len(valid_y)

        # Calculate covariance and variances
        covariance = sum((valid_x[j] - mean_x) * (valid_y[j] - mean_y) for j in range(len(valid_x)))
        variance_x = sum((val - mean_x) ** 2 for val in valid_x)
        variance_y = sum((val - mean_y) ** 2 for val in valid_y)

        # Calculate correlation
        denominator = (variance_x * variance_y) ** 0.5
        if denominator == 0:
            results[i] = None
        else:
            correlation = covariance / denominator
            results[i] = correlation

    return results



