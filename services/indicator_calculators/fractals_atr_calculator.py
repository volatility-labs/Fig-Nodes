"""
Fractals ATR Block Calculator

Implements fractals detection with ATR breaks and ROC (Rate of Change) calculations.
Based on TradingView PineScript indicator "[JL] Fractals ATR Block" by Jesse.Lau.

Default ATR period: 325 (as specified by user)
"""

import math
from collections.abc import Sequence
from typing import Any, Optional


def calculate_fractals_atr(
    highs: Sequence[float | None],
    lows: Sequence[float | None],
    opens: Sequence[float | None],
    closes: Sequence[float | None],
    atr_period: int = 325,
    fractals_periods: int = 1,
    roc_break_level: float = 2.0,
    atr_break_level: float = 1.5,
) -> dict[str, Any]:
    """
    Calculate Fractals ATR Block indicator.

    Args:
        highs: List of high prices
        lows: List of low prices
        opens: List of open prices
        closes: List of close prices
        atr_period: ATR period (default: 325)
        fractals_periods: Fractals periods (default: 1)
        roc_break_level: ROC break level (default: 2.0)
        atr_break_level: ATR break level (default: 1.5)

    Returns:
        Dictionary with:
        - 'up_fractals': List of bool indicating up fractals
        - 'down_fractals': List of bool indicating down fractals
        - 'atr_up_breaks': List of float | None for ATR up breaks (value if break, None otherwise)
        - 'atr_down_breaks': List of float | None for ATR down breaks (value if break, None otherwise)
        - 'fractal_roc_up': List of float | None for fractal ROC up values
        - 'fractal_roc_down': List of float | None for fractal ROC down values
        - 'atr': List of ATR values
    """
    data_length = len(closes)
    
    if data_length == 0:
        return {
            "up_fractals": [],
            "down_fractals": [],
            "atr_up_breaks": [],
            "atr_down_breaks": [],
            "fractal_roc_up": [],
            "fractal_roc_down": [],
            "atr": [],
        }
    
    # Calculate ATR
    from .atr_calculator import calculate_atr
    
    atr_result = calculate_atr(highs, lows, closes, atr_period, smoothing="RMA")
    atr_values = atr_result.get("atr", [None] * data_length)
    
    n = fractals_periods
    
    # Initialize results
    up_fractals: list[bool] = [False] * data_length
    down_fractals: list[bool] = [False] * data_length
    atr_up_breaks: list[float | None] = [None] * data_length
    atr_down_breaks: list[float | None] = [None] * data_length
    fractal_roc_up: list[float | None] = [None] * data_length
    fractal_roc_down: list[float | None] = [None] * data_length
    
    # Calculate ROC values
    rocup: list[float | None] = [None] * data_length
    rocdn: list[float | None] = [None] * data_length
    
    # Calculate ATR break values
    atrup: list[float | None] = [None] * data_length
    atrdn: list[float | None] = [None] * data_length
    
    # Need at least 2*n+1 bars for fractals calculation
    min_bars_needed = 2 * n + 1
    
    for i in range(data_length):
        # Calculate ROC
        if i >= 2 * n and closes[i] is not None and opens[i - 2 * n] is not None:
            # Find lowest in n+1 bars ending at i
            window_lows = []
            for j in range(max(0, i - n), i + 1):
                if lows[j] is not None:
                    window_lows.append(lows[j])
            
            if window_lows:
                lowest_n1 = min(window_lows)
                if opens[i - 2 * n] is not None and lowest_n1 is not None:
                    denom = opens[i - 2 * n] - lowest_n1
                    if denom != 0 and closes[i] is not None:
                        rocup[i] = (closes[i] - lowest_n1) / denom
            
            # Find highest in n+1 bars ending at i
            window_highs = []
            for j in range(max(0, i - n), i + 1):
                if highs[j] is not None:
                    window_highs.append(highs[j])
            
            if window_highs:
                highest_n1 = max(window_highs)
                if opens[i - 2 * n] is not None and highest_n1 is not None:
                    denom = highest_n1 - opens[i - 2 * n]
                    if denom != 0 and closes[i] is not None:
                        rocdn[i] = (highest_n1 - closes[i]) / denom
        
        # Calculate ATR breaks
        if i > 0 and closes[i] is not None and lows[i] is not None and atr_values[i - 1] is not None:
            if atr_values[i - 1] > 0:
                atrup[i] = (closes[i] - lows[i]) / atr_values[i - 1]
                if atrup[i] is not None and atrup[i] > atr_break_level:
                    atr_up_breaks[i] = atrup[i]
        
        if i > 0 and closes[i] is not None and highs[i] is not None and atr_values[i - 1] is not None:
            if atr_values[i - 1] > 0:
                atrdn[i] = (highs[i] - closes[i]) / atr_values[i - 1]
                if atrdn[i] is not None and atrdn[i] > atr_break_level:
                    atr_down_breaks[i] = atrdn[i]
    
    # Calculate fractals
    for i in range(min_bars_needed, data_length):
        if highs[i] is None or lows[i] is None:
            continue
        
        # Up Fractal detection
        upflag_down_frontier = True
        upflag_up_frontier0 = True
        upflag_up_frontier1 = True
        upflag_up_frontier2 = True
        upflag_up_frontier3 = True
        upflag_up_frontier4 = True
        
        for j in range(1, n + 1):
            if i - j < 0 or i + j >= data_length:
                upflag_down_frontier = False
                break
            if highs[i - j] is None or highs[i] is None:
                upflag_down_frontier = False
                break
            if highs[i - j] >= highs[i]:
                upflag_down_frontier = False
                break
        
        if upflag_down_frontier:
            # Check various frontier conditions
            for j in range(1, n + 1):
                if i + j >= data_length or highs[i + j] is None or highs[i] is None:
                    upflag_up_frontier0 = False
                    break
                if highs[i + j] >= highs[i]:
                    upflag_up_frontier0 = False
                    break
            
            # Check other frontier conditions
            if i + 1 < data_length and highs[i + 1] is not None and highs[i] is not None:
                if highs[i + 1] <= highs[i]:
                    for j in range(1, n + 1):
                        if i + j + 1 >= data_length or highs[i + j + 1] is None or highs[i] is None:
                            upflag_up_frontier1 = False
                            break
                        if highs[i + j + 1] >= highs[i]:
                            upflag_up_frontier1 = False
                            break
                else:
                    upflag_up_frontier1 = False
            else:
                upflag_up_frontier1 = False
            
            # Similar checks for frontier2, frontier3, frontier4
            # Simplified: check if n+1 is <= high[n] and n+i+2 < high[n]
            if i + 2 < data_length and highs[i + 1] is not None and highs[i + 2] is not None and highs[i] is not None:
                if highs[i + 1] <= highs[i] and highs[i + 2] <= highs[i]:
                    for j in range(1, n + 1):
                        if i + j + 2 >= data_length or highs[i + j + 2] is None or highs[i] is None:
                            upflag_up_frontier2 = False
                            break
                        if highs[i + j + 2] >= highs[i]:
                            upflag_up_frontier2 = False
                            break
                else:
                    upflag_up_frontier2 = False
            else:
                upflag_up_frontier2 = False
            
            flag_up_frontier = (
                upflag_up_frontier0
                or upflag_up_frontier1
                or upflag_up_frontier2
                or upflag_up_frontier3
                or upflag_up_frontier4
            )
            
            if flag_up_frontier:
                up_fractals[i - n] = True  # Fractal is at bar i-n
                # According to PineScript: upFractal and rocdn > roclevel is BEARISH signal
                # Store ROC value from the current bar (matching PineScript behavior)
                if rocdn[i] is not None and rocdn[i] > roc_break_level:
                    fractal_roc_down[i - n] = rocdn[i]
        
        # Down Fractal detection
        downflag_down_frontier = True
        downflag_up_frontier0 = True
        downflag_up_frontier1 = True
        downflag_up_frontier2 = True
        downflag_up_frontier3 = True
        downflag_up_frontier4 = True
        
        for j in range(1, n + 1):
            if i - j < 0 or i + j >= data_length:
                downflag_down_frontier = False
                break
            if lows[i - j] is None or lows[i] is None:
                downflag_down_frontier = False
                break
            if lows[i - j] <= lows[i]:
                downflag_down_frontier = False
                break
        
        if downflag_down_frontier:
            # Check various frontier conditions
            for j in range(1, n + 1):
                if i + j >= data_length or lows[i + j] is None or lows[i] is None:
                    downflag_up_frontier0 = False
                    break
                if lows[i + j] <= lows[i]:
                    downflag_up_frontier0 = False
                    break
            
            # Check other frontier conditions
            if i + 1 < data_length and lows[i + 1] is not None and lows[i] is not None:
                if lows[i + 1] >= lows[i]:
                    for j in range(1, n + 1):
                        if i + j + 1 >= data_length or lows[i + j + 1] is None or lows[i] is None:
                            downflag_up_frontier1 = False
                            break
                        if lows[i + j + 1] <= lows[i]:
                            downflag_up_frontier1 = False
                            break
                else:
                    downflag_up_frontier1 = False
            else:
                downflag_up_frontier1 = False
            
            # Similar checks for frontier2
            if i + 2 < data_length and lows[i + 1] is not None and lows[i + 2] is not None and lows[i] is not None:
                if lows[i + 1] >= lows[i] and lows[i + 2] >= lows[i]:
                    for j in range(1, n + 1):
                        if i + j + 2 >= data_length or lows[i + j + 2] is None or lows[i] is None:
                            downflag_up_frontier2 = False
                            break
                        if lows[i + j + 2] <= lows[i]:
                            downflag_up_frontier2 = False
                            break
                else:
                    downflag_up_frontier2 = False
            else:
                downflag_up_frontier2 = False
            
            flag_down_frontier = (
                downflag_up_frontier0
                or downflag_up_frontier1
                or downflag_up_frontier2
                or downflag_up_frontier3
                or downflag_up_frontier4
            )
            
            if flag_down_frontier:
                down_fractals[i - n] = True  # Fractal is at bar i-n
                # According to PineScript: downFractal and rocup > roclevel is BULLISH signal
                # Store ROC value from the current bar (matching PineScript behavior)
                if rocup[i] is not None and rocup[i] > roc_break_level:
                    fractal_roc_up[i - n] = rocup[i]
    
    # Determine the most recent signal (bullish/bearish) for downstream consumers
    last_signal_index: Optional[int] = None
    last_signal_type: Optional[str] = None  # "bullish", "bearish", or "both"
    
    for idx in range(data_length - 1, -1, -1):
        has_bullish = False
        has_bearish = False
        
        if atr_up_breaks[idx] is not None and atr_up_breaks[idx] > 0:
            has_bullish = True
        if down_fractals[idx] and fractal_roc_up[idx] is not None and fractal_roc_up[idx] > 0:
            has_bullish = True
        
        if atr_down_breaks[idx] is not None and atr_down_breaks[idx] > 0:
            has_bearish = True
        if up_fractals[idx] and fractal_roc_down[idx] is not None and fractal_roc_down[idx] > 0:
            has_bearish = True
        
        if has_bullish or has_bearish:
            last_signal_index = idx
            if has_bullish and has_bearish:
                last_signal_type = "both"
            elif has_bullish:
                last_signal_type = "bullish"
            else:
                last_signal_type = "bearish"
            break
    
    return {
        "up_fractals": up_fractals,
        "down_fractals": down_fractals,
        "atr_up_breaks": atr_up_breaks,
        "atr_down_breaks": atr_down_breaks,
        "fractal_roc_up": fractal_roc_up,
        "fractal_roc_down": fractal_roc_down,
        "atr": atr_values,
        "last_signal_index": last_signal_index,
        "last_signal_type": last_signal_type,
    }

