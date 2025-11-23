"""
MESA Stochastic Multi Length Calculator

Converts Pine Script MESA Stochastic indicator to Python.

Based on MESA Stochastic code published by @blackcat1402 under Mozilla Public License 2.0.
"""

import math
from collections.abc import Sequence
from typing import Any


def calculate_mesa_stochastic(
    prices: Sequence[float | None],
    length: int = 50,
) -> dict[str, Any]:
    """
    Calculate MESA Stochastic indicator for a given price series.

    Args:
        prices: List of price values (typically HL2 = (high + low) / 2)
            Can contain None values
        length: Lookback period for stochastic calculation

    Returns:
        Dictionary with 'mesa_stochastic' as a list of calculated values for each row,
        matching the TypeScript implementation that returns full time series.
        Each list contains the calculated values for corresponding rows in the input data.
        Returns None for positions where calculation isn't possible.
    """
    data_length = len(prices)

    if length <= 0 or data_length == 0:
        return {"mesa_stochastic": [None] * data_length}

    if data_length < length + 10:  # Need enough data for HP filter
        return {"mesa_stochastic": [None] * data_length}

    pi = 2 * math.asin(1)

    # Initialize arrays with None
    hp: list[float | None] = [None] * data_length
    filt: list[float | None] = [None] * data_length
    stoc: list[float | None] = [None] * data_length
    mesa_stochastic: list[float | None] = [None] * data_length

    # Calculate alpha1 for HP filter
    alpha1 = (math.cos(0.707 * 2 * pi / 48) + math.sin(0.707 * 2 * pi / 48) - 1) / math.cos(
        0.707 * 2 * pi / 48
    )

    # Calculate a1, b1, c1, c2, c3 for SuperSmoother filter
    a1 = math.exp(-1.414 * math.pi / 10)
    b1 = 2 * a1 * math.cos(1.414 * pi / 10)
    c2 = b1
    c3 = -a1 * a1
    c1 = 1 - c2 - c3

    # Process each bar
    for i in range(2, data_length):
        current_price = prices[i]
        prev_price = prices[i - 1] if i > 0 else None
        prev2_price = prices[i - 2] if i > 1 else None

        # Skip if we don't have enough valid prices
        if current_price is None or prev_price is None or prev2_price is None:
            continue

        # High-Pass Filter (HP)
        prev_hp_raw = hp[i - 1]
        prev2_hp_raw = hp[i - 2]
        prev_hp_val = prev_hp_raw if prev_hp_raw is not None else 0.0
        prev2_hp_val = prev2_hp_raw if prev2_hp_raw is not None else 0.0
        hp[i] = (
            (1 - alpha1 / 2) * (1 - alpha1 / 2) * (current_price - 2 * prev_price + prev2_price)
            + 2 * (1 - alpha1) * prev_hp_val
            - (1 - alpha1) * (1 - alpha1) * prev2_hp_val
        )

        # SuperSmoother Filter
        hp_val = hp[i]
        if hp_val is not None:
            prev_hp = hp[i - 1] if hp[i - 1] is not None else hp_val
            prev_filt = filt[i - 1] if filt[i - 1] is not None else hp_val
            prev2_filt = filt[i - 2] if filt[i - 2] is not None else hp_val

            if prev_hp is not None and prev_filt is not None and prev2_filt is not None:
                filt[i] = c1 * (hp_val + prev_hp) / 2 + c2 * prev_filt + c3 * prev2_filt
            else:
                filt[i] = hp_val
        else:
            filt[i] = None

        # Stochastic calculation over lookback period
        if i >= length and filt[i] is not None:
            # Find highest and lowest in lookback window
            highest_c: float | None = None
            lowest_c: float | None = None

            for count in range(max(0, i - length + 1), i + 1):
                filt_val = filt[count]
                if filt_val is not None:
                    if highest_c is None or filt_val > highest_c:
                        highest_c = filt_val
                    if lowest_c is None or filt_val < lowest_c:
                        lowest_c = filt_val

            # Calculate stochastic
            filt_val = filt[i]
            if (
                filt_val is not None
                and highest_c is not None
                and lowest_c is not None
                and highest_c != lowest_c
            ):
                stoc[i] = (filt_val - lowest_c) / (highest_c - lowest_c)
            else:
                stoc[i] = 0.5  # Default to middle if no range

            # Apply SuperSmoother to stochastic
            stoc_val = stoc[i]
            if stoc_val is not None:
                prev_stoc = stoc[i - 1] if stoc[i - 1] is not None else stoc_val
                prev_mesa = (
                    mesa_stochastic[i - 1] if mesa_stochastic[i - 1] is not None else stoc_val
                )
                prev2_mesa = (
                    mesa_stochastic[i - 2] if mesa_stochastic[i - 2] is not None else stoc_val
                )

                if prev_stoc is not None and prev_mesa is not None and prev2_mesa is not None:
                    mesa_stochastic[i] = (
                        c1 * (stoc_val + prev_stoc) / 2 + c2 * prev_mesa + c3 * prev2_mesa
                    )
                else:
                    mesa_stochastic[i] = stoc_val
            else:
                mesa_stochastic[i] = None
        elif i < length:
            stoc[i] = None
            mesa_stochastic[i] = None

    return {"mesa_stochastic": mesa_stochastic}


def calculate_mesa_stochastic_multi_length(
    prices: Sequence[float | None],
    length1: int = 50,
    length2: int = 21,
    length3: int = 14,
    length4: int = 9,
) -> dict[str, Any]:
    """
    Calculate MESA Stochastic for multiple lengths.

    Args:
        prices: List of price values (typically HL2 = (high + low) / 2)
            Can contain None values
        length1: First length (default 50)
        length2: Second length (default 21)
        length3: Third length (default 14)
        length4: Fourth length (default 9)

    Returns:
        Dictionary with keys "mesa1", "mesa2", "mesa3", "mesa4" and their respective values.
        Each value is a list matching the input length, with None for positions where
        calculation isn't possible.
    """
    mesa1_result = calculate_mesa_stochastic(prices, length1)
    mesa2_result = calculate_mesa_stochastic(prices, length2)
    mesa3_result = calculate_mesa_stochastic(prices, length3)
    mesa4_result = calculate_mesa_stochastic(prices, length4)

    return {
        "mesa1": mesa1_result.get("mesa_stochastic", [None] * len(prices)),
        "mesa2": mesa2_result.get("mesa_stochastic", [None] * len(prices)),
        "mesa3": mesa3_result.get("mesa_stochastic", [None] * len(prices)),
        "mesa4": mesa4_result.get("mesa_stochastic", [None] * len(prices)),
    }
