"""
THMA (Triangular Hull Moving Average) Calculator

Based on TradingView Pine Script by BigBeluga:
https://www.tradingview.com/script/0.448/

THMA combines triangular smoothing with Hull Moving Average concepts.
"""

from collections.abc import Sequence
from math import sqrt
from typing import Any

from services.indicator_calculators.wma_calculator import calculate_wma


def calculate_hma(values: Sequence[float | None], period: int) -> list[float | None]:
    """
    Calculate HMA (Hull Moving Average).
    
    HMA = WMA(2*WMA(n/2) - WMA(n), sqrt(n))
    
    Args:
        values: List of values to calculate HMA on (can contain None values)
        period: Period for HMA calculation
        
    Returns:
        List of HMA values (same length as input, with None for insufficient data)
    """
    if period <= 0:
        return [None] * len(values)
    
    # Calculate half period (rounded)
    half_period = max(1, int(period / 2))
    sqrt_period = max(1, int(sqrt(period)))
    
    # Calculate WMA(n/2)
    wma_half_result = calculate_wma(values, half_period)
    wma_half = wma_half_result.get("wma", [])
    
    # Calculate WMA(n)
    wma_full_result = calculate_wma(values, period)
    wma_full = wma_full_result.get("wma", [])
    
    # Calculate 2*WMA(n/2) - WMA(n)
    diff_values: list[float | None] = []
    for i in range(len(values)):
        wma_half_val = wma_half[i] if i < len(wma_half) else None
        wma_full_val = wma_full[i] if i < len(wma_full) else None
        
        if wma_half_val is not None and wma_full_val is not None:
            diff_values.append(2 * wma_half_val - wma_full_val)
        else:
            diff_values.append(None)
    
    # Calculate final WMA on the difference
    hma_result = calculate_wma(diff_values, sqrt_period)
    return hma_result.get("wma", [])


def calculate_thma(values: Sequence[float | None], length: int) -> list[float | None]:
    """
    Calculate THMA (Triangular Hull Moving Average).
    
    THMA formula from TradingView script:
    ta.wma(ta.wma(_src, _length / 3) * 3 - ta.wma(_src, _length / 2) - ta.wma(_src, _length), _length)
    
    Args:
        values: List of values to calculate THMA on (can contain None values)
        length: Period for THMA calculation
        
    Returns:
        List of THMA values (same length as input, with None for insufficient data)
    """
    if length <= 0:
        return [None] * len(values)
    
    # Calculate periods
    period_third = max(1, int(length / 3))
    period_half = max(1, int(length / 2))
    
    # Calculate WMA(_length / 3)
    wma_third_result = calculate_wma(values, period_third)
    wma_third = wma_third_result.get("wma", [])
    
    # Calculate WMA(_length / 2)
    wma_half_result = calculate_wma(values, period_half)
    wma_half = wma_half_result.get("wma", [])
    
    # Calculate WMA(_length)
    wma_full_result = calculate_wma(values, length)
    wma_full = wma_full_result.get("wma", [])
    
    # Calculate: WMA(_length / 3) * 3 - WMA(_length / 2) - WMA(_length)
    combined_values: list[float | None] = []
    for i in range(len(values)):
        wma_third_val = wma_third[i] if i < len(wma_third) else None
        wma_half_val = wma_half[i] if i < len(wma_half) else None
        wma_full_val = wma_full[i] if i < len(wma_full) else None
        
        if wma_third_val is not None and wma_half_val is not None and wma_full_val is not None:
            combined_values.append(wma_third_val * 3 - wma_half_val - wma_full_val)
        else:
            combined_values.append(None)
    
    # Final WMA on the combined values
    thma_result = calculate_wma(combined_values, length)
    return thma_result.get("wma", [])


def calculate_thma_with_volatility(
    closes: Sequence[float | None],
    highs: Sequence[float | None],
    lows: Sequence[float | None],
    thma_length: int = 40,
    volatility_length: int = 15,
) -> dict[str, Any]:
    """
    Calculate THMA with volatility overlay.
    
    Based on TradingView script by BigBeluga.
    
    Args:
        closes: List of close prices
        highs: List of high prices
        lows: List of low prices
        thma_length: Period for THMA calculation (default: 40)
        volatility_length: Period for volatility HMA calculation (default: 15)
        
    Returns:
        Dictionary with:
        - 'thma': List of THMA values
        - 'volatility': List of volatility values (HMA of high-low)
        - 'thma_shifted': List of THMA values shifted by 2 bars (thma[2])
        - 'signal_up': List of boolean values indicating upward crossover signals
        - 'signal_dn': List of boolean values indicating downward crossunder signals
        - 'trend': List of trend direction ('bullish' or 'bearish')
    """
    if not closes or len(closes) == 0:
        return {
            "thma": [],
            "volatility": [],
            "thma_shifted": [],
            "signal_up": [],
            "signal_dn": [],
            "trend": [],
        }
    
    data_length = len(closes)
    
    # Calculate THMA
    thma_values = calculate_thma(closes, thma_length)
    
    # Calculate high-low range for volatility
    high_low_range: list[float | None] = []
    for i in range(data_length):
        high_val = highs[i] if i < len(highs) else None
        low_val = lows[i] if i < len(lows) else None
        
        if high_val is not None and low_val is not None:
            high_low_range.append(high_val - low_val)
        else:
            high_low_range.append(None)
    
    # Calculate volatility using HMA
    volatility_values = calculate_hma(high_low_range, volatility_length)
    
    # Calculate THMA shifted by 2 bars (thma[2])
    thma_shifted: list[float | None] = [None, None]  # First 2 bars are None
    for i in range(2, len(thma_values)):
        thma_shifted.append(thma_values[i - 2])
    
    # Detect crossover/crossunder signals
    # Need at least 3 bars to compare thma[i] with thma[i-2]
    # Need at least 4 bars to detect crossover (need previous values too)
    signal_up: list[bool] = []
    signal_dn: list[bool] = []
    trend: list[str] = []
    
    for i in range(data_length):
        thma_current = thma_values[i] if i < len(thma_values) else None
        thma_prev_shifted = thma_shifted[i] if i < len(thma_shifted) else None
        
        # Need at least 3 bars to determine trend (compare current with shifted)
        if thma_current is not None and thma_prev_shifted is not None:
            # Determine trend: bullish if thma > thma[2], bearish otherwise
            if thma_current > thma_prev_shifted:
                trend.append("bullish")
            else:
                trend.append("bearish")
            
            # Need at least 4 bars to detect crossover (need previous bar and its shifted value)
            if i >= 3:
                thma_prev = thma_values[i - 1]
                thma_prev_shifted_prev = thma_shifted[i - 1]
                
                if thma_prev is not None and thma_prev_shifted_prev is not None:
                    # Crossover: current > shifted AND previous <= previous_shifted
                    crossover_up = (
                        thma_current > thma_prev_shifted and thma_prev <= thma_prev_shifted_prev
                    )
                    # Crossunder: current < shifted AND previous >= previous_shifted
                    crossunder_dn = (
                        thma_current < thma_prev_shifted and thma_prev >= thma_prev_shifted_prev
                    )
                    
                    signal_up.append(crossover_up)
                    signal_dn.append(crossunder_dn)
                else:
                    signal_up.append(False)
                    signal_dn.append(False)
            else:
                # Not enough bars for crossover detection
                signal_up.append(False)
                signal_dn.append(False)
        else:
            # Not enough data
            signal_up.append(False)
            signal_dn.append(False)
            trend.append("neutral")
    
    return {
        "thma": thma_values,
        "volatility": volatility_values,
        "thma_shifted": thma_shifted,
        "signal_up": signal_up,
        "signal_dn": signal_dn,
        "trend": trend,
    }

