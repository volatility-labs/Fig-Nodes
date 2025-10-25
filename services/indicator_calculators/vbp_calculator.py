from collections.abc import Sequence
from typing import Any

from core.types_registry import OHLCVBar


def calculate_vbp(bars: Sequence[OHLCVBar], number_of_bins: int) -> dict[str, Any]:
    """
    Calculate VBP (Volume Profile) histogram data.

    Args:
        bars: List of OHLCV bars (can contain None values in volume field)
        number_of_bins: The number of price bins to create for the histogram

    Returns:
        Dictionary with 'histogram', 'pointOfControl', 'valueAreaHigh', 'valueAreaLow'
        Each contains lists matching the TypeScript implementation.
    """
    if not bars or len(bars) == 0 or number_of_bins <= 0:
        return {
            "histogram": [],
            "pointOfControl": None,
            "valueAreaHigh": None,
            "valueAreaLow": None,
        }

    # Find min and max prices
    min_price = float("inf")
    max_price = float("-inf")
    total_volume = 0.0

    for bar in bars:
        if bar["high"] > max_price:
            max_price = bar["high"]
        if bar["low"] < min_price:
            min_price = bar["low"]
        total_volume += bar.get("volume", 0.0) or 0.0

    if total_volume == 0 or min_price == max_price:
        return {
            "histogram": [],
            "pointOfControl": None,
            "valueAreaHigh": None,
            "valueAreaLow": None,
        }

    # Create histogram bins
    bin_size = (max_price - min_price) / number_of_bins
    histogram: list[dict[str, Any]] = []

    for i in range(number_of_bins):
        price_low = min_price + i * bin_size
        histogram.append(
            {
                "priceLow": price_low,
                "priceHigh": price_low + bin_size,
                "priceLevel": price_low + bin_size / 2,
                "volume": 0.0,
            }
        )

    # Distribute volume into bins using typical price
    for bar in bars:
        volume = bar.get("volume", 0.0) or 0.0
        if volume > 0:
            typical_price = (bar["high"] + bar["low"] + bar["close"]) / 3
            bin_index = int((typical_price - min_price) / bin_size)
            if bin_index >= number_of_bins:
                bin_index = number_of_bins - 1
            if bin_index < 0:
                bin_index = 0

            if 0 <= bin_index < len(histogram):
                histogram[bin_index]["volume"] += volume

    if len(histogram) == 0:
        return {
            "histogram": [],
            "pointOfControl": None,
            "valueAreaHigh": None,
            "valueAreaLow": None,
        }

    # Find Point of Control (POC) - bin with highest volume
    poc_index = 0
    max_volume = histogram[0]["volume"]
    for i in range(1, len(histogram)):
        if histogram[i]["volume"] > max_volume:
            max_volume = histogram[i]["volume"]
            poc_index = i

    point_of_control = histogram[poc_index]["priceLevel"]

    # Calculate Value Area (70% of total volume)
    target_volume = total_volume * 0.70
    current_volume = histogram[poc_index]["volume"]
    high_index = poc_index
    low_index = poc_index

    while current_volume < target_volume and (low_index > 0 or high_index < number_of_bins - 1):
        next_high_volume = (
            histogram[high_index + 1]["volume"] if high_index + 1 < number_of_bins else -1.0
        )
        next_low_volume = histogram[low_index - 1]["volume"] if low_index - 1 >= 0 else -1.0

        if next_high_volume > next_low_volume:
            high_index += 1
            current_volume += next_high_volume
        else:
            low_index -= 1
            current_volume += next_low_volume

    value_area_high = histogram[high_index]["priceHigh"]
    value_area_low = histogram[low_index]["priceLow"]

    return {
        "histogram": histogram,
        "pointOfControl": point_of_control,
        "valueAreaHigh": value_area_high,
        "valueAreaLow": value_area_low,
    }
