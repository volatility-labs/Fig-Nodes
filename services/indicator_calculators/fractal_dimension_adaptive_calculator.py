"""
Fractal Dimension Adaptive Calculator

Implements DSS of Advanced Kaufman AMA with Fractal Dimension Adaptive efficiency ratio.
Based on TradingView PineScript indicator "DSS of Advanced Kaufman AMA [Loxx]" by loxx.
"""

import math
from collections.abc import Sequence
from typing import Any

from .ema_calculator import calculate_ema
from .rsi_calculator import calculate_rsi


def _jfract(
    highs: Sequence[float | None],
    lows: Sequence[float | None],
    count: int,
    index: int,
) -> float:
    """
    Calculate fractal dimension at a specific index.

    Args:
        highs: List of high prices
        lows: List of low prices
        count: Window size for fractal calculation
        index: Current index

    Returns:
        Fractal dimension value (clamped between 1 and 2)
    """
    if count <= 0 or index < count:
        return 1.0
    
    window = math.ceil(count / 2)
    
    # Calculate _hl1: (highest(high[window], window) - lowest(low[window], window)) / window
    window_start = max(0, index - window)
    window_highs = [h for h in highs[window_start:index] if h is not None]
    window_lows = [l for l in lows[window_start:index] if l is not None]
    
    if not window_highs or not window_lows:
        return 1.0
    
    hl1 = (max(window_highs) - min(window_lows)) / window if window > 0 else 0.0
    
    # Calculate _hl2: (highest(high, window) - lowest(low, window)) / window
    window_start2 = max(0, index - window + 1)
    window_highs2 = [h for h in highs[window_start2:index + 1] if h is not None]
    window_lows2 = [l for l in lows[window_start2:index + 1] if l is not None]
    
    if not window_highs2 or not window_lows2:
        return 1.0
    
    hl2 = (max(window_highs2) - min(window_lows2)) / window if window > 0 else 0.0
    
    # Calculate _hl: (highest(high, count) - lowest(low, count)) / count
    count_start = max(0, index - count + 1)
    count_highs = [h for h in highs[count_start:index + 1] if h is not None]
    count_lows = [l for l in lows[count_start:index + 1] if l is not None]
    
    if not count_highs or not count_lows:
        return 1.0
    
    hl = (max(count_highs) - min(count_lows)) / count if count > 0 else 0.0
    
    # Calculate fractal dimension
    # Ensure all values are positive before taking log
    if hl <= 0 or hl1 + hl2 <= 0:
        return 1.0
    
    try:
        d = (math.log(hl1 + hl2) - math.log(hl)) / math.log(2)
    except (ValueError, OverflowError):
        # Handle math domain errors gracefully
        return 1.0
    
    # Clamp between 1 and 2
    dim = max(1.0, min(2.0, d))
    
    return dim


def _kama(
    src: Sequence[float | None],
    len_period: int,
    fast: float,
    slow: float,
    jcount: int,
    power: int,
    efratiocalc: str,
    highs: Sequence[float | None] | None = None,
    lows: Sequence[float | None] | None = None,
) -> list[float | None]:
    """
    Calculate Kaufman Adaptive Moving Average.

    Args:
        src: Source price series
        len_period: Period for momentum calculation
        fast: Fast-end period
        slow: Slow-end period
        jcount: Fractal dimension count
        power: Smoothing power
        efratiocalc: Efficiency ratio type ("Regular" or "Fractal Dimension Adaptive")
        highs: High prices (needed for fractal dimension)
        lows: Low prices (needed for fractal dimension)

    Returns:
        List of KAMA values
    """
    data_length = len(src)
    if data_length == 0:
        return []
    
    fastend = 2.0 / (fast + 1)
    slowend = 2.0 / (slow + 1)
    
    kama_values: list[float | None] = [None] * data_length
    
    for i in range(data_length):
        if i < len_period:
            kama_values[i] = None
            continue
        
        # Calculate momentum
        if src[i] is None or src[i - len_period] is None:
            kama_values[i] = None
            continue
        
        mom = abs(src[i] - src[i - len_period])
        
        # Calculate volatility
        vola = 0.0
        for j in range(i - len_period + 1, i + 1):
            if j > 0 and src[j] is not None and src[j - 1] is not None:
                vola += abs(src[j] - src[j - 1])
        
        # Calculate efficiency ratio
        if efratiocalc == "Regular":
            efratio = mom / vola if vola != 0 else 0.0
        else:  # Fractal Dimension Adaptive
            if highs is not None and lows is not None:
                fract_dim = _jfract(highs, lows, jcount, i)
                efratio = min(2.0 - fract_dim, 1.0)
            else:
                efratio = 0.0
        
        # Calculate alpha
        alpha = math.pow(efratio * (fastend - slowend) + slowend, power)
        
        # Calculate KAMA
        if kama_values[i - 1] is None:
            kama_values[i] = src[i] if src[i] is not None else None
        else:
            if src[i] is not None:
                kama_values[i] = alpha * src[i] + (1 - alpha) * kama_values[i - 1]
            else:
                kama_values[i] = None
    
    return kama_values


def calculate_stoch(
    src: Sequence[float | None],
    length: int,
) -> list[float | None]:
    """
    Calculate Stochastic oscillator.

    Args:
        src: Source series
        length: Period length

    Returns:
        List of stochastic values (0-100)
    """
    data_length = len(src)
    if data_length == 0:
        return []
    
    stoch_values: list[float | None] = [None] * data_length
    
    for i in range(data_length):
        if i < length - 1:
            stoch_values[i] = None
            continue
        
        window_start = max(0, i - length + 1)
        window = src[window_start:i + 1]
        valid_values = [v for v in window if v is not None]
        
        if not valid_values:
            stoch_values[i] = None
            continue
        
        highest = max(valid_values)
        lowest = min(valid_values)
        
        if highest == lowest:
            stoch_values[i] = 50.0
        elif src[i] is not None:
            stoch_values[i] = 100.0 * (src[i] - lowest) / (highest - lowest)
        else:
            stoch_values[i] = None
    
    return stoch_values


def calculate_fractal_dimension_adaptive(
    closes: Sequence[float | None],
    highs: Sequence[float | None] | None = None,
    lows: Sequence[float | None] | None = None,
    period: int = 10,
    kama_fastend: float = 2.0,
    kama_slowend: float = 30.0,
    efratiocalc: str = "Fractal Dimension Adaptive",
    jcount: int = 2,
    smooth_power: int = 2,
    stoch_len: int = 30,
    sm_ema: int = 9,
    sig_ema: int = 5,
) -> dict[str, Any]:
    """
    Calculate Fractal Dimension Adaptive (DSSAKAMA) indicator.

    Args:
        closes: Close prices
        highs: High prices (optional, needed for fractal dimension)
        lows: Low prices (optional, needed for fractal dimension)
        period: KAMA period (default: 10)
        kama_fastend: KAMA fast-end period (default: 2.0)
        kama_slowend: KAMA slow-end period (default: 30.0)
        efratiocalc: Efficiency ratio type (default: "Fractal Dimension Adaptive")
        jcount: Fractal dimension count (default: 2)
        smooth_power: Smoothing power (default: 2)
        stoch_len: Stochastic length (default: 30)
        sm_ema: Intermediate smooth period (default: 9)
        sig_ema: Signal smooth period (default: 5)

    Returns:
        Dictionary with:
        - 'kama': List of KAMA values
        - 'signal': List of signal line values
        - 'outer': List of outer line values
        - 'stoch': List of stochastic values
    """
    data_length = len(closes)
    
    if data_length == 0:
        return {
            "kama": [],
            "signal": [],
            "outer": [],
            "stoch": [],
        }
    
    # Calculate KAMA
    kama_values = _kama(
        closes,
        period,
        kama_fastend,
        kama_slowend,
        jcount,
        smooth_power,
        efratiocalc,
        highs,
        lows,
    )
    
    # Calculate stochastic on KAMA
    kama_hi: list[float | None] = [None] * data_length
    kama_lo: list[float | None] = [None] * data_length
    
    for i in range(data_length):
        if i < stoch_len - 1:
            continue
        
        window_start = max(0, i - stoch_len + 1)
        window = kama_values[window_start:i + 1]
        valid_values = [v for v in window if v is not None]
        
        if valid_values:
            kama_hi[i] = max(valid_values)
            kama_lo[i] = min(valid_values)
    
    st1: list[float | None] = [None] * data_length
    for i in range(data_length):
        if kama_hi[i] is not None and kama_lo[i] is not None and kama_values[i] is not None:
            if kama_hi[i] == kama_lo[i]:
                st1[i] = 50.0
            else:
                st1[i] = 100.0 * (kama_values[i] - kama_lo[i]) / (kama_hi[i] - kama_lo[i])
    
    # Calculate EMA on st1
    ema_result = calculate_ema(st1, sm_ema)
    emaout = ema_result.get("ema", [None] * data_length)
    
    # Calculate stochastic on emaout
    firsthi: list[float | None] = [None] * data_length
    firstlo: list[float | None] = [None] * data_length
    
    for i in range(data_length):
        if i < stoch_len - 1:
            continue
        
        window_start = max(0, i - stoch_len + 1)
        window = emaout[window_start:i + 1]
        valid_values = [v for v in window if v is not None]
        
        if valid_values:
            firsthi[i] = max(valid_values)
            firstlo[i] = min(valid_values)
    
    out: list[float | None] = [None] * data_length
    for i in range(data_length):
        if firsthi[i] is not None and firstlo[i] is not None and emaout[i] is not None:
            if firsthi[i] == firstlo[i]:
                out[i] = 50.0
            else:
                out[i] = 100.0 * (emaout[i] - firstlo[i]) / (firsthi[i] - firstlo[i])
    
    # Calculate outer (EMA on out)
    outer_result = calculate_ema(out, sm_ema)
    outer = outer_result.get("ema", [None] * data_length)
    
    # Calculate signal (EMA on outer)
    signal_result = calculate_ema(outer, sig_ema)
    signal = signal_result.get("ema", [None] * data_length)
    
    return {
        "kama": kama_values,
        "signal": signal,
        "outer": outer,
        "stoch": st1,
    }

