"""
Deviation Magnet Calculator

Based on TradingView Pine Script "Deviation Magnet - JD" by Joris Duyck (JD).
Shows price in relation to standard deviations in a normalized way.

The indicator highlights "MAGNET MOVES" where price sticks to deviation levels
rather than bouncing off them.
"""

from collections.abc import Sequence
from typing import Any

from services.indicator_calculators.ema_calculator import calculate_ema
from services.indicator_calculators.sma_calculator import calculate_sma
from services.indicator_calculators.utils import (
    calculate_rolling_std_dev,
    rolling_max,
    rolling_min,
)


def calculate_deviation_magnet(
    opens: Sequence[float | None],
    highs: Sequence[float | None],
    lows: Sequence[float | None],
    closes: Sequence[float | None],
    anchor: int = 1,  # 1 = SMA, 2 = EMA
    bblength: int = 50,
    mult: float = 2.0,
    timeframe_multiplier: int = 1,
    coloring_sensitivity: int = 2,  # 0-3, matches Pine Script sens parameter
) -> dict[str, Any]:
    """
    Calculate Deviation Magnet indicator.
    
    Args:
        opens: Open prices
        highs: High prices
        lows: Low prices
        closes: Close prices
        anchor: Anchor type (1 = SMA, 2 = EMA)
        bblength: Bollinger Band length period
        mult: Bollinger Band multiplier
        timeframe_multiplier: Timeframe multiplier for multi-timeframe analysis
        
    Returns:
        Dictionary with:
        - 'basis': Moving average basis (SMA or EMA)
        - 'dev': Standard deviation values
        - 'upper': Upper Bollinger Band (basis + dev)
        - 'lower': Lower Bollinger Band (basis - dev)
        - 'upper1': Upper half deviation (basis + dev/2)
        - 'lower1': Lower half deviation (basis - dev/2)
        - 'upper3': Upper 1.5x deviation (basis + dev*1.5)
        - 'lower3': Lower 1.5x deviation (basis - dev*1.5)
        - 'price': Normalized price value
        - 'sq': Squeeze indicator
        - 'top': Expansion indicator
        - 'up_break': Upper band break signals
        - 'low_break': Lower band break signals
        - 'up_break1': Upper half deviation break signals
        - 'low_break1': Lower half deviation break signals
        - 'up_break3': Upper 1.5x deviation break signals
        - 'low_break3': Lower 1.5x deviation break signals
        - 'magnet_up': Magnet up signals
        - 'magnet_down': Magnet down signals
        - 'bounce_up': Bounce up signals
        - 'bounce_down': Bounce down signals
        - 'explode_up': Explosion up signals
        - 'explode_down': Explosion down signals
    """
    if bblength <= 0 or mult <= 0:
        return {
            "basis": [None] * len(closes),
            "dev": [None] * len(closes),
            "upper": [None] * len(closes),
            "lower": [None] * len(closes),
            "upper1": [None] * len(closes),
            "lower1": [None] * len(closes),
            "upper3": [None] * len(closes),
            "lower3": [None] * len(closes),
            "price": [None] * len(closes),
            "sq": [None] * len(closes),
            "top": [None] * len(closes),
            "up_break": [False] * len(closes),
            "low_break": [False] * len(closes),
            "up_break1": [False] * len(closes),
            "low_break1": [False] * len(closes),
            "up_break3": [False] * len(closes),
            "low_break3": [False] * len(closes),
            "magnet_up": [False] * len(closes),
            "magnet_down": [False] * len(closes),
            "bounce_up": [False] * len(closes),
            "bounce_down": [False] * len(closes),
            "explode_up": [False] * len(closes),
            "explode_down": [False] * len(closes),
        }
    
    # Calculate OHLC4 (typical price)
    ohlc4: list[float | None] = []
    for i in range(len(closes)):
        o = opens[i] if i < len(opens) else None
        h = highs[i] if i < len(highs) else None
        l = lows[i] if i < len(lows) else None
        c = closes[i]
        
        if o is not None and h is not None and l is not None and c is not None:
            ohlc4.append((o + h + l + c) / 4.0)
        else:
            ohlc4.append(None)
    
    # Calculate basis (SMA or EMA) with timeframe multiplier
    effective_length = bblength * timeframe_multiplier
    
    if anchor == 1:
        # SMA
        sma_result = calculate_sma(ohlc4, effective_length)
        basis = sma_result.get("sma", [])
    else:
        # EMA
        ema_result = calculate_ema(ohlc4, effective_length)
        basis = ema_result.get("ema", [])
    
    # Calculate standard deviation
    dev_raw = calculate_rolling_std_dev(ohlc4, effective_length)
    dev: list[float | None] = []
    for d in dev_raw:
        if d is not None:
            dev.append(d * mult)
        else:
            dev.append(None)
    
    # Calculate Bollinger Bands
    upper: list[float | None] = []
    lower: list[float | None] = []
    upper1: list[float | None] = []
    lower1: list[float | None] = []
    upper3: list[float | None] = []
    lower3: list[float | None] = []
    
    for i in range(len(basis)):
        b = basis[i]
        d = dev[i] if i < len(dev) else None
        
        if b is not None and d is not None:
            upper.append(b + d)
            lower.append(b - d)
            upper1.append(b + d / 2.0)
            lower1.append(b - d / 2.0)
            upper3.append(b + d * 1.5)
            lower3.append(b - d * 1.5)
        else:
            upper.append(None)
            lower.append(None)
            upper1.append(None)
            lower1.append(None)
            upper3.append(None)
            lower3.append(None)
    
    # Calculate normalized price
    price: list[float | None] = []
    for i in range(len(ohlc4)):
        ohlc4_val = ohlc4[i]
        b = basis[i] if i < len(basis) else None
        d = dev[i] if i < len(dev) else None
        h = highs[i] if i < len(highs) else None
        l = lows[i] if i < len(lows) else None
        
        if ohlc4_val is not None and b is not None and d is not None and d > 0:
            if ohlc4_val > b:
                if h is not None:
                    price_val = (h - b) * 2.0 / d
                else:
                    price_val = (ohlc4_val - b) * 2.0 / d
            else:
                if l is not None:
                    price_val = (l - b) * 2.0 / d
                else:
                    price_val = (ohlc4_val - b) * 2.0 / d
            price.append(price_val)
        else:
            price.append(None)
    
    # Calculate squeeze/expansion indicators
    sq: list[float | None] = []
    top: list[float | None] = []
    
    # Calculate highest and lowest dev over 50 period window
    dev_highest = rolling_max(dev, 50)
    dev_lowest = rolling_min(dev, 50)
    
    for i in range(len(dev)):
        d = dev[i]
        d_highest = dev_highest[i] if i < len(dev_highest) else None
        d_lowest = dev_lowest[i] if i < len(dev_lowest) else None
        
        if d is not None and d_highest is not None and d_highest > 0:
            sq_val = -15 - (d / d_highest) * 5.0
            sq.append(sq_val)
        else:
            sq.append(None)
        
        if d is not None and d_lowest is not None and d_lowest > 0:
            top_val = (d / d_lowest) - 21.0
            top.append(top_val)
        else:
            top.append(None)
    
    # Calculate break signals
    up_break: list[bool] = []
    low_break: list[bool] = []
    up_break1: list[bool] = []
    low_break1: list[bool] = []
    up_break3: list[bool] = []
    low_break3: list[bool] = []
    
    for i in range(len(highs)):
        h = highs[i] if i < len(highs) else None
        l = lows[i] if i < len(lows) else None
        u = upper[i] if i < len(upper) else None
        lo = lower[i] if i < len(lower) else None
        u1 = upper1[i] if i < len(upper1) else None
        lo1 = lower1[i] if i < len(lower1) else None
        u3 = upper3[i] if i < len(upper3) else None
        lo3 = lower3[i] if i < len(lower3) else None
        
        up_break.append(h is not None and u is not None and (h - u) >= 0)
        low_break.append(l is not None and lo is not None and (l - lo) <= 0)
        up_break1.append(h is not None and u1 is not None and (h - u1) >= 0)
        low_break1.append(l is not None and lo1 is not None and (l - lo1) <= 0)
        up_break3.append(h is not None and u3 is not None and (h - u3) >= 0)
        low_break3.append(l is not None and lo3 is not None and (l - lo3) <= 0)
    
    # Calculate magnet signals
    magnet_up: list[bool] = []
    magnet_down: list[bool] = []
    
    for i in range(len(up_break1)):
        magnet_up.append(up_break1[i])
        magnet_down.append(low_break1[i])
    
    # Calculate bounce/explosion signals
    bounce_up: list[bool] = []
    bounce_down: list[bool] = []
    explode_up: list[bool] = []
    explode_down: list[bool] = []
    
    # Helper to check if squeeze is rising/falling
    # Note: Works correctly with negative values (e.g., -19 > -20 means rising)
    # For expansion line (top): typically negative values around -18 to -21
    # Rising = becoming less negative (volatility increasing)
    # Falling = becoming more negative (volatility decreasing)
    def is_rising(values: list[float | None], idx: int) -> bool:
        if idx < 1 or idx >= len(values):
            return False
        curr = values[idx]
        prev = values[idx - 1]
        # For negative values: -19 > -20 is True (rising), -20 > -19 is False (falling)
        return curr is not None and prev is not None and curr > prev
    
    def is_falling(values: list[float | None], idx: int) -> bool:
        if idx < 1 or idx >= len(values):
            return False
        curr = values[idx]
        prev = values[idx - 1]
        # For negative values: -20 < -19 is True (falling), -19 < -20 is False (rising)
        return curr is not None and prev is not None and curr < prev
    
    # Calculate bounce conditions
    for i in range(len(sq)):
        sq_rising = is_rising(sq, i)
        top_falling = is_falling(top, i)
        sq_curr = sq[i]
        top_curr = top[i]
        
        # Bounce conditions (simplified from Pine Script logic)
        bounce1 = (
            sq_curr is not None
            and top_curr is not None
            and sq_rising
            and top_curr < sq_curr
        )
        bounce2 = (
            sq_curr is not None
            and top_curr is not None
            and sq_rising
            and top_curr >= sq_curr
        )
        
        # Check if upper/lower are rising/falling
        upper_rising = is_rising(upper, i) if i < len(upper) else False
        lower_rising = is_rising(lower, i) if i < len(lower) else False
        
        # Bounce signals
        if i < len(low_break1) and low_break1[i] and (bounce1 or bounce2):
            if lower_rising:
                bounce_up.append(True)
            else:
                bounce_up.append(False)
        else:
            bounce_up.append(False)
        
        if i < len(up_break1) and up_break1[i] and (bounce1 or bounce2):
            if not upper_rising:
                bounce_down.append(True)
            else:
                bounce_down.append(False)
        else:
            bounce_down.append(False)
        
        # Explosion signals
        if i > 0:
            prev_bounce1 = (
                i - 1 < len(sq)
                and sq[i - 1] is not None
                and top[i - 1] is not None
                and is_rising(sq, i - 1)
                and top[i - 1] < sq[i - 1]
            )
            prev_bounce2 = (
                i - 1 < len(sq)
                and sq[i - 1] is not None
                and top[i - 1] is not None
                and is_rising(sq, i - 1)
                and top[i - 1] >= sq[i - 1]
            )
            curr_bounce1 = bounce1
            curr_bounce2 = bounce2
            
            if i < len(low_break) and low_break[i] and (prev_bounce1 or prev_bounce2) and not (curr_bounce1 or curr_bounce2):
                explode_down.append(True)
            else:
                explode_down.append(False)
            
            if i < len(up_break) and up_break[i] and (prev_bounce1 or prev_bounce2) and not (curr_bounce1 or curr_bounce2):
                explode_up.append(True)
            else:
                explode_up.append(False)
        else:
            explode_up.append(False)
            explode_down.append(False)
    
    # Calculate squeeze/expansion signals
    squeeze_release: list[bool] = []
    squeeze_contract: list[bool] = []
    squeeze_active: list[bool] = []
    expansion_bullish: list[bool] = []
    expansion_bullish_rising: list[bool] = []
    expansion_bullish_rising_any: list[bool] = []  # Green line rising (any green, dim or bright)
    expansion_bearish: list[bool] = []
    expansion_bearish_rising: list[bool] = []
    
    for i in range(len(sq)):
        if i < 1:
            squeeze_release.append(False)
            squeeze_contract.append(False)
            squeeze_active.append(False)
            expansion_bullish.append(False)
            expansion_bullish_rising.append(False)
            expansion_bullish_rising_any.append(False)
            expansion_bearish.append(False)
            expansion_bearish_rising.append(False)
            continue
        
        sq_curr = sq[i]
        sq_prev = sq[i - 1] if i > 0 else None
        top_curr = top[i] if i < len(top) else None
        top_prev = top[i - 1] if i > 0 and i - 1 < len(top) else None
        p = price[i] if i < len(price) else None
        
        # Release: top[1] < sq[1] and top >= sq (expansion crosses above squeeze)
        release = (
            top_prev is not None
            and sq_prev is not None
            and top_curr is not None
            and sq_curr is not None
            and top_prev < sq_prev
            and top_curr >= sq_curr
        )
        squeeze_release.append(release)
        
        # Contract: top[1] > sq[1] and top <= sq (expansion crosses below squeeze)
        contract = (
            top_prev is not None
            and sq_prev is not None
            and top_curr is not None
            and sq_curr is not None
            and top_prev > sq_prev
            and top_curr <= sq_curr
        )
        squeeze_contract.append(contract)
        
        # Squeeze active: squeeze is rising (volatility compression)
        sq_rising = is_rising(sq, i)
        squeeze_active.append(sq_rising)
        
        # Expansion bullish: matches Pine Script top_color green logic
        # Green appears when:
        #   1. rising(top,1) AND top>sq AND price>=0 → bright green (green,0) - STRONG bullish
        #   2. falling(sq,1) AND price>=0 → dim green (green,25) - WEAK bullish (squeeze falling but expansion flat/not rising)
        top_rising = is_rising(top, i)
        sq_falling = is_falling(sq, i)
        
        # Case 1: Strong bullish - expansion rising + top > sq + price >= 0 (bright green)
        expansion_bull_strong = (
            top_rising
            and top_curr is not None
            and sq_curr is not None
            and top_curr > sq_curr
            and p is not None
            and p >= 0
        )
        
        # Case 2: Weak bullish - squeeze falling + price >= 0 (dim green, even if expansion flat)
        expansion_bull_weak = (
            sq_falling
            and p is not None
            and p >= 0
        )
        
        # Any green (strong OR weak)
        expansion_bull = expansion_bull_strong or expansion_bull_weak
        expansion_bullish.append(expansion_bull)
        expansion_bullish_rising.append(expansion_bull_strong)  # Only strong (rising) case
        
        # Green line rising (any green + top rising) - catches dim green rising like TRUMP
        expansion_bullish_rising_any_val = expansion_bull and top_rising
        expansion_bullish_rising_any.append(expansion_bullish_rising_any_val)
        
        # Expansion bearish: matches Pine Script top_color red logic
        # Red appears when:
        #   1. rising(top,1) AND top>sq AND price<0 → bright red (red,0) - STRONG bearish
        #   2. falling(sq,1) AND price<0 → dim red (red,25) - WEAK bearish (squeeze falling but expansion flat/not rising)
        
        # Case 1: Strong bearish - expansion rising + top > sq + price < 0 (bright red)
        expansion_bear_strong = (
            top_rising
            and top_curr is not None
            and sq_curr is not None
            and top_curr > sq_curr
            and p is not None
            and p < 0
        )
        
        # Case 2: Weak bearish - squeeze falling + price < 0 (dim red, even if expansion flat)
        expansion_bear_weak = (
            sq_falling
            and p is not None
            and p < 0
        )
        
        # Any red (strong OR weak)
        expansion_bear = expansion_bear_strong or expansion_bear_weak
        expansion_bearish.append(expansion_bear)
        expansion_bearish_rising.append(expansion_bear_strong)  # Only strong (rising) case
        
        sq_curr = sq[i]
        sq_prev = sq[i - 1] if i > 0 else None
        top_curr = top[i] if i < len(top) else None
        top_prev = top[i - 1] if i > 0 and i - 1 < len(top) else None
        p = price[i] if i < len(price) else None
        
        # Release: top[1] < sq[1] and top >= sq (expansion crosses above squeeze)
        release = (
            top_prev is not None
            and sq_prev is not None
            and top_curr is not None
            and sq_curr is not None
            and top_prev < sq_prev
            and top_curr >= sq_curr
        )
        squeeze_release.append(release)
        
        # Contract: top[1] > sq[1] and top <= sq (expansion crosses below squeeze)
        contract = (
            top_prev is not None
            and sq_prev is not None
            and top_curr is not None
            and sq_curr is not None
            and top_prev > sq_prev
            and top_curr <= sq_curr
        )
        squeeze_contract.append(contract)
        
        # Squeeze active: squeeze is rising (volatility compression)
        sq_rising = is_rising(sq, i)
        squeeze_active.append(sq_rising)
        
        # Expansion bullish: matches Pine Script top_color green logic
        # Green appears when:
        #   1. rising(top,1) AND top>sq AND price>=0 → bright green (green,0) - STRONG bullish
        #   2. falling(sq,1) AND price>=0 → dim green (green,25) - WEAK bullish (squeeze falling but expansion flat/not rising)
        top_rising = is_rising(top, i)
        sq_falling = is_falling(sq, i)
        
        # Case 1: Strong bullish - expansion rising + top > sq + price >= 0 (bright green)
        expansion_bull_strong = (
            top_rising
            and top_curr is not None
            and sq_curr is not None
            and top_curr > sq_curr
            and p is not None
            and p >= 0
        )
        
        # Case 2: Weak bullish - squeeze falling + price >= 0 (dim green, even if expansion flat)
        expansion_bull_weak = (
            sq_falling
            and p is not None
            and p >= 0
        )
        
        # Any green (strong OR weak)
        expansion_bull = expansion_bull_strong or expansion_bull_weak
        expansion_bullish.append(expansion_bull)
        
        # Expansion bearish: matches Pine Script top_color red logic
        # Red appears when:
        #   1. rising(top,1) AND top>sq AND price<0 → bright red (red,0) - STRONG bearish
        #   2. falling(sq,1) AND price<0 → dim red (red,25) - WEAK bearish (squeeze falling but expansion flat/not rising)
        
        # Case 1: Strong bearish - expansion rising + top > sq + price < 0 (bright red)
        expansion_bear_strong = (
            top_rising
            and top_curr is not None
            and sq_curr is not None
            and top_curr > sq_curr
            and p is not None
            and p < 0
        )
        
        # Case 2: Weak bearish - squeeze falling + price < 0 (dim red, even if expansion flat)
        expansion_bear_weak = (
            sq_falling
            and p is not None
            and p < 0
        )
        
        # Any red (strong OR weak)
        expansion_bear = expansion_bear_strong or expansion_bear_weak
        expansion_bearish.append(expansion_bear)
    
    # Calculate boost conditions and bar coloring signals (matching Pine Script b_col logic)
    # boost1 = top_color==color(green,25) or top_color==color(red,25) or not(rising(sq,1) and falling(top,1))
    # boost2 = top_color==color(green,0) or top_color==color(red,0)
    # Bar coloring logic matches Pine Script b_col calculation
    
    bar_coloring_bullish: list[bool] = []
    bar_coloring_bearish: list[bool] = []
    
    for i in range(len(price)):
        p = price[i] if i < len(price) else None
        sq_rising = is_rising(sq, i)
        top_falling = is_falling(top, i)
        u_break = up_break[i] if i < len(up_break) else False
        l_break = low_break[i] if i < len(low_break) else False
        u_break1 = up_break1[i] if i < len(up_break1) else False
        l_break1 = low_break1[i] if i < len(low_break1) else False
        u_break3 = up_break3[i] if i < len(up_break3) else False
        l_break3 = low_break3[i] if i < len(low_break3) else False
        
        # Calculate top_color conditions (simplified from Pine Script)
        # top_color logic: rising(top,1) ? (top>sq ? (price>=0?green:red) : (falling(sq,1)?green/red:orange)) : orange
        top_rising = is_rising(top, i)
        sq_falling = is_falling(sq, i)
        top_val = top[i] if i < len(top) else None
        sq_val = sq[i] if i < len(sq) else None
        
        # Calculate boost conditions matching Pine Script logic
        # top_color logic from Pine Script:
        #   rising(top,1) ? (top>sq ? (price>=0?green(0):red(0)) : (falling(sq,1)?(price>=0?green(25):red(25)):orange)) : orange
        # boost1 = top_color==color(green,25) or top_color==color(red,25) or not(rising(sq,1) and falling(top,1))
        # boost2 = top_color==color(green,0) or top_color==color(red,0)
        
        # Calculate top_color conditions
        top_color_green_0 = False  # top_color == color(green,0)
        top_color_red_0 = False     # top_color == color(red,0)
        top_color_green_25 = False  # top_color == color(green,25)
        top_color_red_25 = False    # top_color == color(red,25)
        
        if top_rising:
            if top_val is not None and sq_val is not None and top_val > sq_val:
                # top > sq: price>=0 ? green(0) : red(0)
                if p is not None and p >= 0:
                    top_color_green_0 = True
                elif p is not None and p < 0:
                    top_color_red_0 = True
            elif sq_falling:
                # falling(sq,1): price>=0 ? green(25) : red(25)
                if p is not None and p >= 0:
                    top_color_green_25 = True
                elif p is not None and p < 0:
                    top_color_red_25 = True
        
        # Calculate boost conditions
        boost1 = top_color_green_25 or top_color_red_25 or not (sq_rising and top_falling)
        boost2 = top_color_green_0 or top_color_red_0
        
        # Bar coloring logic matching Pine Script b_col
        bullish_signal = False
        bearish_signal = False
        
        if boost1 or boost2:
            # Check sensitivity-based breaks
            if coloring_sensitivity <= 3 and u_break3:
                bullish_signal = True
            elif coloring_sensitivity <= 2 and u_break:
                bullish_signal = True
            elif coloring_sensitivity == 1 and u_break1:
                bullish_signal = True
            elif coloring_sensitivity == 0 and p is not None and p >= 0:
                bullish_signal = True
            
            if coloring_sensitivity <= 3 and l_break3:
                bearish_signal = True
            elif coloring_sensitivity <= 2 and l_break:
                bearish_signal = True
            elif coloring_sensitivity == 1 and l_break1:
                bearish_signal = True
            elif coloring_sensitivity == 0 and p is not None and p < 0:
                bearish_signal = True
        else:
            # If not boost1 and not boost2, only check price if sensitivity is 0
            if coloring_sensitivity == 0:
                if p is not None and p >= 0:
                    bullish_signal = True
                elif p is not None and p < 0:
                    bearish_signal = True
        
        bar_coloring_bullish.append(bullish_signal)
        bar_coloring_bearish.append(bearish_signal)
    
    return {
        "basis": basis,
        "dev": dev,
        "upper": upper,
        "lower": lower,
        "upper1": upper1,
        "lower1": lower1,
        "upper3": upper3,
        "lower3": lower3,
        "price": price,
        "sq": sq,
        "top": top,
        "up_break": up_break,
        "low_break": low_break,
        "up_break1": up_break1,
        "low_break1": low_break1,
        "up_break3": up_break3,
        "low_break3": low_break3,
        "magnet_up": magnet_up,
        "magnet_down": magnet_down,
        "bounce_up": bounce_up,
        "bounce_down": bounce_down,
        "explode_up": explode_up,
        "explode_down": explode_down,
        "bar_coloring_bullish": bar_coloring_bullish,
        "bar_coloring_bearish": bar_coloring_bearish,
        "squeeze_release": squeeze_release,
        "squeeze_contract": squeeze_contract,
        "squeeze_active": squeeze_active,
        "expansion_bullish": expansion_bullish,
        "expansion_bullish_rising": expansion_bullish_rising,
        "expansion_bullish_rising_any": expansion_bullish_rising_any,  # Green line rising (any green)
        "expansion_bearish": expansion_bearish,
        "expansion_bearish_rising": expansion_bearish_rising,
    }

