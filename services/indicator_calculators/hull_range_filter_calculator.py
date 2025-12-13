"""
Hull Range Filter Calculator

Based on TradingView Pine Script "Hull-rangefilter" by RafaelZioni.
Combines XAvi range filter with Hull Moving Average and Fibonacci ATR bands.
"""

from collections.abc import Sequence
from math import sqrt
from typing import Any

from services.indicator_calculators.ema_calculator import calculate_ema
from services.indicator_calculators.wma_calculator import calculate_wma
from services.indicator_calculators.atr_calculator import calculate_atr
from services.indicator_calculators.sma_calculator import calculate_sma


def calculate_smooth_range(
    values: Sequence[float | None],
    period: int,
    multiplier: float,
) -> list[float | None]:
    """
    Calculate smooth average range using EMA.
    
    Formula: EMA(EMA(abs(x - x[1]), period), (period*2 - 1)) * multiplier
    
    Args:
        values: List of source values (e.g., close prices)
        period: Sampling period
        multiplier: Range multiplier
        
    Returns:
        List of smooth range values
    """
    if period <= 0 or len(values) < 2:
        return [None] * len(values)
    
    # Calculate abs(x - x[1])
    abs_diff: list[float | None] = []
    for i in range(len(values)):
        if i == 0:
            abs_diff.append(None)
        else:
            curr = values[i]
            prev = values[i - 1]
            if curr is not None and prev is not None:
                abs_diff.append(abs(curr - prev))
            else:
                abs_diff.append(None)
    
    # First EMA: EMA(abs(x - x[1]), period)
    ema1_result = calculate_ema(abs_diff, period)
    ema1_values = ema1_result.get("ema", [])
    
    # Second EMA period: (period * 2) - 1
    wper = (period * 2) - 1
    
    # Second EMA: EMA(ema1, wper)
    ema2_result = calculate_ema(ema1_values, wper)
    ema2_values = ema2_result.get("ema", [])
    
    # Multiply by multiplier
    smooth_range: list[float | None] = []
    for val in ema2_values:
        if val is not None:
            smooth_range.append(val * multiplier)
        else:
            smooth_range.append(None)
    
    return smooth_range


def calculate_range_filter(
    values: Sequence[float | None],
    smooth_range: Sequence[float | None],
) -> list[float | None]:
    """
    Calculate range filter.
    
    Formula (Pine Script):
    rngfilt := x > nz(rngfilt[1]) ? 
        ((x - r) < nz(rngfilt[1]) ? nz(rngfilt[1]) : (x - r)) : 
        ((x + r) > nz(rngfilt[1]) ? nz(rngfilt[1]) : (x + r))
    
    Where nz() returns 0 if value is None/null.
    
    Args:
        values: Source values
        smooth_range: Smooth range values (r)
        
    Returns:
        List of range filter values
    """
    if len(values) != len(smooth_range):
        return [None] * len(values)
    
    filt: list[float | None] = []
    
    for i in range(len(values)):
        x = values[i]
        r = smooth_range[i] if i < len(smooth_range) else None
        
        if x is None or r is None:
            filt.append(None)
            continue
        
        if i == 0:
            # First value: use x as initial value
            filt.append(x)
        else:
            # nz() returns 0 if None, otherwise returns the value
            prev_filt = filt[i - 1] if filt[i - 1] is not None else 0.0
            
            # Range filter logic
            if x > prev_filt:
                candidate = x - r
                filt_val = prev_filt if candidate < prev_filt else candidate
            else:
                candidate = x + r
                filt_val = prev_filt if candidate > prev_filt else candidate
            filt.append(filt_val)
    
    return filt


def calculate_hull_range_filter(
    closes: Sequence[float | None],
    highs: Sequence[float | None],
    lows: Sequence[float | None],
    sampling_period: int = 14,
    range_multiplier: float = 5.0,
    hull_period: int = 16,
    fib_atr_length: int = 20,
    fib_ratio1: float = 1.618,
    fib_ratio2: float = 2.618,
    fib_ratio3: float = 4.236,
) -> dict[str, Any]:
    """
    Calculate complete Hull Range Filter indicator.
    
    Args:
        closes: Close prices
        highs: High prices
        lows: Low prices
        sampling_period: Sampling period for smooth range (default: 14)
        range_multiplier: Range multiplier (default: 5.0)
        hull_period: Period for Hull Moving Average (default: 16)
        fib_atr_length: Length for ATR calculation (default: 20)
        fib_ratio1: Fibonacci ratio 1 (default: 1.618)
        fib_ratio2: Fibonacci ratio 2 (default: 2.618)
        fib_ratio3: Fibonacci ratio 3 (default: 4.236)
        
    Returns:
        Dictionary with:
        - 'range_filter': Range filter values
        - 'smooth_range': Smooth range values
        - 'upward': Upward direction count
        - 'downward': Downward direction count
        - 'hull_ma': Hull Moving Average values
        - 'hull_ma_prev': Previous period Hull MA
        - 'fib_atr': ATR values
        - 'fib_top1', 'fib_top2', 'fib_top3': Fibonacci upper bands
        - 'fib_bott1', 'fib_bott2', 'fib_bott3': Fibonacci lower bands
        - 'sma': Simple Moving Average
        - 'signal_buy': Buy signals
        - 'signal_sell': Sell signals
        - 'long_condition': Long entry condition
        - 'short_condition': Short entry condition
    """
    if len(closes) < max(sampling_period * 2, hull_period, fib_atr_length) + 10:
        return {
            "range_filter": [None] * len(closes),
            "smooth_range": [None] * len(closes),
            "upward": [0] * len(closes),
            "downward": [0] * len(closes),
            "hull_ma": [None] * len(closes),
            "hull_ma_prev": [None] * len(closes),
            "fib_atr": [None] * len(closes),
            "fib_top1": [None] * len(closes),
            "fib_top2": [None] * len(closes),
            "fib_top3": [None] * len(closes),
            "fib_bott1": [None] * len(closes),
            "fib_bott2": [None] * len(closes),
            "fib_bott3": [None] * len(closes),
            "sma": [None] * len(closes),
            "signal_buy": [False] * len(closes),
            "signal_sell": [False] * len(closes),
            "long_condition": [False] * len(closes),
            "short_condition": [False] * len(closes),
        }
    
    # Calculate smooth range
    smooth_range = calculate_smooth_range(closes, sampling_period, range_multiplier)
    
    # Calculate range filter
    range_filter = calculate_range_filter(closes, smooth_range)
    
    # Calculate filter direction (upward/downward)
    upward: list[int] = []
    downward: list[int] = []
    
    for i in range(len(range_filter)):
        if i == 0:
            upward.append(0)
            downward.append(0)
        else:
            filt_curr = range_filter[i]
            filt_prev = range_filter[i - 1]
            
            if filt_curr is None or filt_prev is None:
                upward.append(upward[i - 1] if i > 0 else 0)
                downward.append(downward[i - 1] if i > 0 else 0)
            elif filt_curr > filt_prev:
                upward.append((upward[i - 1] if i > 0 else 0) + 1)
                downward.append(0)
            elif filt_curr < filt_prev:
                upward.append(0)
                downward.append((downward[i - 1] if i > 0 else 0) + 1)
            else:
                upward.append(upward[i - 1] if i > 0 else 0)
                downward.append(downward[i - 1] if i > 0 else 0)
    
    # Calculate Hull Moving Average
    half_period = max(1, int(hull_period / 2))
    sqrt_period = max(1, int(sqrt(hull_period)))
    
    wma_half_result = calculate_wma(closes, half_period)
    wma_half = wma_half_result.get("wma", [])
    
    wma_full_result = calculate_wma(closes, hull_period)
    wma_full = wma_full_result.get("wma", [])
    
    # Calculate 2*WMA(n/2) - WMA(n)
    diff_values: list[float | None] = []
    for i in range(len(closes)):
        wma_half_val = wma_half[i] if i < len(wma_half) else None
        wma_full_val = wma_full[i] if i < len(wma_full) else None
        
        if wma_half_val is not None and wma_full_val is not None:
            diff_values.append(2 * wma_half_val - wma_full_val)
        else:
            diff_values.append(None)
    
    # Calculate WMA of diff with sqrt period
    wma_diff_result = calculate_wma(diff_values, sqrt_period)
    hull_ma = wma_diff_result.get("wma", [])
    
    # Previous period Hull MA (shifted by 1)
    hull_ma_prev: list[float | None] = [None]
    for i in range(1, len(hull_ma)):
        hull_ma_prev.append(hull_ma[i - 1])
    
    # Calculate ATR and Fibonacci bands
    atr_result = calculate_atr(highs, lows, closes, fib_atr_length)
    fib_atr = atr_result.get("atr", [])
    
    sma_result = calculate_sma(closes, fib_atr_length)
    sma_values = sma_result.get("sma", [])
    
    # Calculate Fibonacci bands
    fib_top1: list[float | None] = []
    fib_top2: list[float | None] = []
    fib_top3: list[float | None] = []
    fib_bott1: list[float | None] = []
    fib_bott2: list[float | None] = []
    fib_bott3: list[float | None] = []
    
    for i in range(len(closes)):
        sma_val = sma_values[i] if i < len(sma_values) else None
        atr_val = fib_atr[i] if i < len(fib_atr) else None
        
        if sma_val is not None and atr_val is not None:
            fib_top1.append(sma_val + atr_val * fib_ratio1)
            fib_top2.append(sma_val + atr_val * fib_ratio2)
            fib_top3.append(sma_val + atr_val * fib_ratio3)
            fib_bott1.append(sma_val - atr_val * fib_ratio1)
            fib_bott2.append(sma_val - atr_val * fib_ratio2)
            fib_bott3.append(sma_val - atr_val * fib_ratio3)
        else:
            fib_top1.append(None)
            fib_top2.append(None)
            fib_top3.append(None)
            fib_bott1.append(None)
            fib_bott2.append(None)
            fib_bott3.append(None)
    
    # Calculate buy/sell signals
    signal_buy: list[bool] = []
    signal_sell: list[bool] = []
    long_condition: list[bool] = []
    short_condition: list[bool] = []
    
    cond_ini: list[int] = [0]  # Initial condition state
    
    for i in range(len(closes)):
        if i == 0:
            signal_buy.append(False)
            signal_sell.append(False)
            long_condition.append(False)
            short_condition.append(False)
            continue
        
        close_curr = closes[i]
        close_prev = closes[i - 1]
        filt_curr = range_filter[i]
        filt_prev = range_filter[i - 1] if i > 0 else None
        upward_curr = upward[i]
        downward_curr = downward[i]
        hull_curr = hull_ma[i] if i < len(hull_ma) else None
        hull_prev = hull_ma_prev[i] if i < len(hull_ma_prev) else None
        fib_bott2_curr = fib_bott2[i] if i < len(fib_bott2) else None
        fib_top2_curr = fib_top2[i] if i < len(fib_top2) else None
        
        if (
            close_curr is None
            or close_prev is None
            or filt_curr is None
            or filt_prev is None
            or hull_curr is None
            or hull_prev is None
            or fib_bott2_curr is None
            or fib_top2_curr is None
        ):
            signal_buy.append(False)
            signal_sell.append(False)
            long_condition.append(False)
            short_condition.append(False)
            cond_ini.append(cond_ini[i - 1] if i > 0 else 0)
            continue
        
        # Long condition: (src > filt) and (src > src[1]) and (upward > 0)
        # OR (src > filt) and (src < src[1]) and (upward > 0)
        long_cond = (
            (close_curr > filt_curr and close_curr > close_prev and upward_curr > 0)
            or (close_curr > filt_curr and close_curr < close_prev and upward_curr > 0)
        )
        
        # Short condition: (src < filt) and (src < src[1]) and (downward > 0)
        # OR (src < filt) and (src > src[1]) and (downward > 0)
        short_cond = (
            (close_curr < filt_curr and close_curr < close_prev and downward_curr > 0)
            or (close_curr < filt_curr and close_curr > close_prev and downward_curr > 0)
        )
        
        long_condition.append(long_cond)
        short_condition.append(short_cond)
        
        # Update condition state
        if long_cond:
            cond_ini.append(1)
        elif short_cond:
            cond_ini.append(-1)
        else:
            cond_ini.append(cond_ini[i - 1] if i > 0 else 0)
        
        # Buy signal: long condition AND previous state was short (-1)
        buy_signal = long_cond and (cond_ini[i - 1] if i > 0 else 0) == -1
        
        # Sell signal: short condition AND previous state was long (1)
        sell_signal = short_cond and (cond_ini[i - 1] if i > 0 else 0) == 1
        
        # Additional buy/sell from Hull MA crossover with Fibonacci bands
        hull_buy = hull_curr > hull_prev and hull_curr > fib_bott2_curr and hull_prev <= fib_bott2_curr
        hull_sell = hull_curr < hull_prev and hull_curr < fib_top2_curr and hull_prev >= fib_top2_curr
        
        signal_buy.append(buy_signal or hull_buy)
        signal_sell.append(sell_signal or hull_sell)
    
    return {
        "range_filter": range_filter,
        "smooth_range": smooth_range,
        "upward": upward,
        "downward": downward,
        "hull_ma": hull_ma,
        "hull_ma_prev": hull_ma_prev,
        "fib_atr": fib_atr,
        "fib_top1": fib_top1,
        "fib_top2": fib_top2,
        "fib_top3": fib_top3,
        "fib_bott1": fib_bott1,
        "fib_bott2": fib_bott2,
        "fib_bott3": fib_bott3,
        "sma": sma_values,
        "signal_buy": signal_buy,
        "signal_sell": signal_sell,
        "long_condition": long_condition,
        "short_condition": short_condition,
    }

