"""
Stochastic Heat Map Calculator

Implements the Stochastic Heat Map indicator that plots multiple stochastic oscillators
stacked vertically, each colored based on its value.

Based on TradingView Pine Script by Violent (https://www.tradingview.com/v/7PRbCBjk/)
"""

from collections.abc import Sequence
from typing import Any

from .ema_calculator import calculate_ema
from .sma_calculator import calculate_sma
from .wma_calculator import calculate_wma


def calculate_stochastic(
    source: Sequence[float | None],
    highs: Sequence[float | None],
    lows: Sequence[float | None],
    length: int,
) -> list[float | None]:
    """
    Calculate stochastic oscillator %K (matching TradingView's stoch() function).
    
    Formula: (source - lowest low) / (highest high - lowest low) * 100
    
    Args:
        source: Source price series (typically close)
        highs: High prices
        lows: Low prices
        length: Lookback period
    
    Returns:
        List of stochastic values (0-100)
    """
    if not source or len(source) == 0:
        return []
    
    if len(highs) != len(source) or len(lows) != len(source):
        raise ValueError("highs, lows, and source must have the same length")
    
    stoch_values: list[float | None] = [None] * len(source)
    
    for i in range(len(source)):
        if i < length - 1:
            stoch_values[i] = None
            continue
        
        # Find highest high and lowest low in the lookback period
        window_start = max(0, i - length + 1)
        window_highs: list[float] = []
        window_lows: list[float] = []
        
        for j in range(window_start, i + 1):
            if highs[j] is not None:
                window_highs.append(highs[j])
            if lows[j] is not None:
                window_lows.append(lows[j])
        
        if not window_highs or not window_lows:
            stoch_values[i] = None
            continue
        
        highest = max(window_highs)
        lowest = min(window_lows)
        
        if source[i] is None:
            stoch_values[i] = None
        elif highest == lowest:
            stoch_values[i] = 50.0
        else:
            stoch_values[i] = 100.0 * (source[i] - lowest) / (highest - lowest)
    
    return stoch_values


def calculate_stochastic_heatmap(
    closes: Sequence[float | None],
    highs: Sequence[float | None],
    lows: Sequence[float | None],
    ma_type: str = "EMA",
    increment: int = 10,
    smooth_fast: int = 2,
    smooth_slow: int = 21,
    plot_number: int = 28,
    waves: bool = False,
) -> dict[str, Any]:
    """
    Calculate Stochastic Heat Map indicator.
    
    Args:
        closes: Close prices
        highs: High prices
        lows: Low prices
        ma_type: Moving average type ("SMA", "EMA", or "WMA")
        increment: Base increment for stochastic lengths (default: 10)
        smooth_fast: Smoothing period for fast line (default: 2)
        smooth_slow: Smoothing period for slow line (default: 21)
        plot_number: Number of stochastics to calculate (1-28, default: 28)
        waves: If True, use weighted increments; if False, use linear increments
    
    Returns:
        Dictionary with:
        - stochastics: dict mapping index (1-28) to list of stochastic values
        - colors: dict mapping index (1-28) to list of color hex codes
        - fast_line: list of fast oscillator values
        - slow_line: list of slow oscillator values
        - average_stoch: list of average stochastic values
    """
    if not closes or len(closes) == 0:
        return {
            "stochastics": {},
            "colors": {},
            "fast_line": [],
            "slow_line": [],
            "average_stoch": [],
        }
    
    # Define stochastic lengths and smoothing periods based on waves option
    # Pine Script logic:
    # - When Waves=false: getStoch(i, 0) where i=1..28, so c=i*inc, s=smooth+0
    # - When Waves=true: getStoch(i, i) where i=1..10, then getStoch(15,11), getStoch(20,12), etc.
    stoch_lengths: list[int] = []
    smooth_lengths: list[int] = []
    
    if waves:
        # Waves mode: i values are [1,2,3,4,5,6,7,8,9,10,15,20,25,30,35,40,45,50,55,60,70,80,90,100,110,120,140,160]
        # c = i * inc, s = smooth + i (where i is the second parameter)
        wave_i_values = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 15, 20, 25, 30, 35, 40, 45, 50, 55, 60, 70, 80, 90, 100, 110, 120, 140, 160]
        wave_incr_values = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28]
        for i_val, incr_val in zip(wave_i_values, wave_incr_values):
            stoch_lengths.append(i_val * increment)  # c = i * inc
            smooth_lengths.append(smooth_fast + incr_val)  # s = smooth + incr
    else:
        # Non-waves mode: i values are [1,2,3,...,28], incr=0
        # c = i * inc, s = smooth + 0
        for i in range(1, 29):  # i from 1 to 28
            stoch_lengths.append(i * increment)  # c = i * inc
            smooth_lengths.append(smooth_fast)  # s = smooth + 0
    
    # Calculate all stochastics
    stochastics: dict[int, list[float | None]] = {}
    smoothed_stochastics: dict[int, list[float | None]] = {}
    
    for i in range(min(plot_number, 28)):
        idx = i + 1
        stoch_length = stoch_lengths[i]
        smooth_length = smooth_lengths[i]
        
        # Calculate raw stochastic
        raw_stoch = calculate_stochastic(closes, highs, lows, stoch_length)
        
        # Apply smoothing
        if ma_type == "SMA":
            smoothed = calculate_sma(raw_stoch, smooth_length)
            smoothed_stoch = smoothed.get("sma", [None] * len(closes))
        elif ma_type == "EMA":
            smoothed = calculate_ema(raw_stoch, smooth_length)
            smoothed_stoch = smoothed.get("ema", [None] * len(closes))
        elif ma_type == "WMA":
            smoothed = calculate_wma(raw_stoch, smooth_length)
            smoothed_stoch = smoothed.get("wma", [None] * len(closes))
        else:
            smoothed_stoch = raw_stoch
        
        stochastics[idx] = raw_stoch
        smoothed_stochastics[idx] = smoothed_stoch
    
    # Calculate average of all smoothed stochastics
    # Pine Script: getAverage = (stoch1 + stoch2 + ... + stoch28) / plotNumber
    # Note: Pine Script divides by plotNumber, not by count of valid values
    average_stoch: list[float | None] = []
    for i in range(len(closes)):
        sum_values = 0.0
        count_valid = 0
        for idx in range(1, min(plot_number, 28) + 1):
            if idx in smoothed_stochastics:
                val = smoothed_stochastics[idx][i]
                if val is not None:
                    sum_values += val
                    count_valid += 1
        
        # Match Pine Script: divide by plotNumber, but only if we have at least some valid values
        # If all are None, result is None
        if count_valid > 0:
            # Pine Script divides by plotNumber regardless of how many are valid
            # This matches: getAverage = (stoch1 + stoch2 + ... + stoch28) / plotNumber
            average_stoch.append(sum_values / plot_number)
        else:
            average_stoch.append(None)
    
    # Calculate fast and slow lines
    fast_line: list[float | None] = []
    for avg_val in average_stoch:
        if avg_val is not None:
            fast_line.append((avg_val / 100.0) * plot_number)
        else:
            fast_line.append(None)
    
    # Smooth the fast line to get slow line
    if ma_type == "SMA":
        slow_result = calculate_sma(fast_line, smooth_slow)
        slow_line = slow_result.get("sma", [None] * len(closes))
    elif ma_type == "EMA":
        slow_result = calculate_ema(fast_line, smooth_slow)
        slow_line = slow_result.get("ema", [None] * len(closes))
    elif ma_type == "WMA":
        slow_result = calculate_wma(fast_line, smooth_slow)
        slow_line = slow_result.get("wma", [None] * len(closes))
    else:
        slow_line = fast_line
    
    # Calculate colors for each stochastic (Theme 3 colors)
    colors: dict[int, list[str]] = {}
    for idx in range(1, min(plot_number, 28) + 1):
        if idx in smoothed_stochastics:
            stoch_vals = smoothed_stochastics[idx]
            color_list: list[str] = []
            for val in stoch_vals:
                if val is None:
                    color_list.append("#ffffff")
                else:
                    color_list.append(_get_color_theme3(val))
            colors[idx] = color_list
    
    return {
        "stochastics": smoothed_stochastics,
        "colors": colors,
        "fast_line": fast_line,
        "slow_line": slow_line,
        "average_stoch": average_stoch,
    }


def _get_color_theme3(value: float) -> str:
    """
    Get color for Theme 3 based on stochastic value.
    Enhanced colors for better visibility on dark background.
    
    Theme 3 colors (brighter, more vibrant):
    - >= 90: #ff0000 (bright red)
    - >= 85: #ff4000 (red-orange)
    - >= 80: #ff8000 (bright orange-red)
    - >= 75: #ffa000 (orange)
    - >= 70: #ffc000 (yellow-orange)
    - >= 65: #ffe000 (yellow)
    - >= 60: #ffff00 (bright yellow)
    - >= 55: #c0ff00 (yellow-green)
    - >= 50: #80ff00 (bright green)
    - >= 45: #40ff00 (green)
    - >= 40: #00ff80 (cyan-green)
    - >= 35: #00ffc0 (cyan)
    - >= 30: #00ffff (bright cyan)
    - >= 25: #00c0ff (light blue)
    - >= 20: #0080ff (blue)
    - >= 15: #0040ff (bright blue)
    - >= 10: #0000ff (deep blue)
    - >= 5: #4000ff (purple-blue)
    - >= 0: #8000ff (purple)
    """
    if value >= 90:
        return "#ff0000"  # Bright red
    elif value >= 85:
        return "#ff4000"  # Red-orange
    elif value >= 80:
        return "#ff8000"  # Bright orange-red
    elif value >= 75:
        return "#ffa000"  # Orange
    elif value >= 70:
        return "#ffc000"  # Yellow-orange
    elif value >= 65:
        return "#ffe000"  # Yellow
    elif value >= 60:
        return "#ffff00"  # Bright yellow
    elif value >= 55:
        return "#c0ff00"  # Yellow-green
    elif value >= 50:
        return "#80ff00"  # Bright green
    elif value >= 45:
        return "#40ff00"  # Green
    elif value >= 40:
        return "#00ff80"  # Cyan-green
    elif value >= 35:
        return "#00ffc0"  # Cyan
    elif value >= 30:
        return "#00ffff"  # Bright cyan
    elif value >= 25:
        return "#00c0ff"  # Light blue
    elif value >= 20:
        return "#0080ff"  # Blue
    elif value >= 15:
        return "#0040ff"  # Bright blue
    elif value >= 10:
        return "#0000ff"  # Deep blue
    elif value >= 5:
        return "#4000ff"  # Purple-blue
    else:
        return "#8000ff"  # Purple

