"""
MESA Stochastic Multi Length Calculator

Converts Pine Script MESA Stochastic indicator to Python.
Based on MESA Stochastic code published by @blackcat1402 under Mozilla Public License 2.0.
"""

import math
from typing import Any

import numpy as np


def calculate_mesa_stochastic(
    prices: list[float],
    length: int = 50,
) -> list[float]:
    """
    Calculate MESA Stochastic indicator for a given price series.
    
    Args:
        prices: List of price values (typically HL2 = (high + low) / 2)
        length: Lookback period for stochastic calculation
        
    Returns:
        List of MESA Stochastic values (same length as input prices)
    """
    if len(prices) < length + 10:  # Need enough data for HP filter
        return [0.0] * len(prices)
    
    pi = 2 * math.asin(1)
    
    # Initialize arrays
    n = len(prices)
    hp = [0.0] * n
    filt = [0.0] * n
    stoc = [0.0] * n
    mesa_stochastic = [0.0] * n
    
    # Calculate alpha1 for HP filter
    alpha1 = (math.cos(0.707 * 2 * pi / 48) + math.sin(0.707 * 2 * pi / 48) - 1) / math.cos(0.707 * 2 * pi / 48)
    
    # Calculate a1, b1, c1, c2, c3 for SuperSmoother filter
    a1 = math.exp(-1.414 * math.pi / 10)
    b1 = 2 * a1 * math.cos(1.414 * pi / 10)
    c2 = b1
    c3 = -a1 * a1
    c1 = 1 - c2 - c3
    
    # Process each bar
    for i in range(2, n):
        # High-Pass Filter (HP)
        if i >= 2:
            hp[i] = (
                (1 - alpha1 / 2) * (1 - alpha1 / 2) * (prices[i] - 2 * prices[i - 1] + prices[i - 2])
                + 2 * (1 - alpha1) * hp[i - 1]
                - (1 - alpha1) * (1 - alpha1) * hp[i - 2]
            )
        else:
            hp[i] = 0.0
        
        # SuperSmoother Filter
        if i >= 2:
            filt[i] = (
                c1 * (hp[i] + hp[i - 1]) / 2
                + c2 * filt[i - 1]
                + c3 * filt[i - 2]
            )
        else:
            filt[i] = hp[i]
        
        # Stochastic calculation over lookback period
        if i >= length:
            # Find highest and lowest in lookback window
            highest_c = filt[i]
            lowest_c = filt[i]
            
            for count in range(max(0, i - length + 1), i + 1):
                if filt[count] > highest_c:
                    highest_c = filt[count]
                if filt[count] < lowest_c:
                    lowest_c = filt[count]
            
            # Calculate stochastic
            if highest_c != lowest_c:
                stoc[i] = (filt[i] - lowest_c) / (highest_c - lowest_c)
            else:
                stoc[i] = 0.5  # Default to middle if no range
            
            # Apply SuperSmoother to stochastic
            if i >= 2:
                mesa_stochastic[i] = (
                    c1 * (stoc[i] + stoc[i - 1]) / 2
                    + c2 * mesa_stochastic[i - 1]
                    + c3 * mesa_stochastic[i - 2]
                )
            else:
                mesa_stochastic[i] = stoc[i]
        else:
            stoc[i] = 0.5
            mesa_stochastic[i] = 0.5
    
    return mesa_stochastic


def calculate_mesa_stochastic_multi_length(
    prices: list[float],
    length1: int = 50,
    length2: int = 21,
    length3: int = 14,
    length4: int = 9,
) -> dict[str, list[float]]:
    """
    Calculate MESA Stochastic for multiple lengths.
    
    Args:
        prices: List of price values (typically HL2 = (high + low) / 2)
        length1: First length (default 50)
        length2: Second length (default 21)
        length3: Third length (default 14)
        length4: Fourth length (default 9)
        
    Returns:
        Dictionary with keys "mesa1", "mesa2", "mesa3", "mesa4" and their respective values
    """
    return {
        "mesa1": calculate_mesa_stochastic(prices, length1),
        "mesa2": calculate_mesa_stochastic(prices, length2),
        "mesa3": calculate_mesa_stochastic(prices, length3),
        "mesa4": calculate_mesa_stochastic(prices, length4),
    }

