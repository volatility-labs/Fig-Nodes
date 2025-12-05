"""
Fractal Resonance Bar Calculator

Implements the Fractal Resonance Bar indicator based on WaveTrend oscillators
at multiple timeframes (1x, 2x, 4x, 8x, 16x, 32x, 64x, 128x).

Based on TradingView Pine Script by Pythagoras.
"""

from collections.abc import Sequence
from typing import Any

from .ema_calculator import calculate_ema
from .sma_calculator import calculate_sma


def stochastic_trend(
    ap: Sequence[float | None],
    n_channel: int,
    n_average: int,
    crossover_sma_len: int,
    time_multiplier: int,
) -> tuple[list[float | None], list[float | None], list[float | None]]:
    """
    Calculate WaveTrend oscillator values for a given timeframe multiplier.
    
    Args:
        ap: Price series (typically close prices)
        n_channel: Channel length parameter
        n_average: Stochastic ratio length parameter
        crossover_sma_len: Crossover lag length
        time_multiplier: Time multiplier (1, 2, 4, 8, 16, 32, 64, 128)
    
    Returns:
        Tuple of (wtA, wtB, wtDiff) lists
    """
    if not ap or len(ap) == 0:
        return ([None] * len(ap), [None] * len(ap), [None] * len(ap))
    
    # Calculate ESA (Channel EMA)
    esa_period = n_channel * time_multiplier
    esa_result = calculate_ema(ap, esa_period)
    esa = esa_result.get("ema", [None] * len(ap))
    
    # Calculate deviation d = EMA(abs(ap - esa), n_channel * timeMultiplier)
    deviations: list[float | None] = []
    for i in range(len(ap)):
        if ap[i] is not None and esa[i] is not None:
            deviations.append(abs(ap[i] - esa[i]))
        else:
            deviations.append(None)
    
    d_result = calculate_ema(deviations, esa_period)
    d = d_result.get("ema", [None] * len(ap))
    
    # Calculate CI = 100 * (ap - esa) / d
    ci: list[float | None] = []
    for i in range(len(ap)):
        if ap[i] is not None and esa[i] is not None and d[i] is not None and d[i] != 0:
            ci.append(100.0 * (ap[i] - esa[i]) / d[i])
        else:
            ci.append(None)
    
    # Calculate TCI = EMA(CI, n_average * timeMultiplier)
    tci_period = n_average * time_multiplier
    tci_result = calculate_ema(ci, tci_period)
    tci = tci_result.get("ema", [None] * len(ap))
    
    # wtA = TCI
    wt_a = tci
    
    # wtB = SMA(wtA, crossover_sma_len * timeMultiplier)
    wtb_period = crossover_sma_len * time_multiplier
    wtb_result = calculate_sma(wt_a, wtb_period)
    wt_b = wtb_result.get("sma", [None] * len(ap))
    
    # wtDiff = wtA - wtB
    wt_diff: list[float | None] = []
    for i in range(len(ap)):
        if wt_a[i] is not None and wt_b[i] is not None:
            wt_diff.append(wt_a[i] - wt_b[i])
        else:
            wt_diff.append(None)
    
    return (wt_a, wt_b, wt_diff)


def calculate_fractal_resonance(
    closes: Sequence[float | None],
    n1: int = 10,
    n2: int = 21,
    crossover_sma_len: int = 3,
    ob_level: float = 75.0,
    ob_embed_level: float = 88.0,
    ob_extreme_level: float = 100.0,
    cross_separation: float = 3.0,
) -> dict[str, Any]:
    """
    Calculate Fractal Resonance Bar indicator.
    
    Args:
        closes: Close prices
        n1: Channel length (>1)
        n2: Stochastic ratio length (>1)
        crossover_sma_len: Crossover lag (>1)
        ob_level: Overbought level (default 75)
        os_level: Oversold level (default -ob_level)
        ob_embed_level: Embedded overbought level (default 88)
        ob_extreme_level: Extreme overbought level (default 100)
        cross_separation: Embed separation (default 3)
    
    Returns:
        Dictionary with:
        - 'wt_a': Dict of timeframe -> list of wtA values
        - 'wt_b': Dict of timeframe -> list of wtB values
        - 'wt_diff': Dict of timeframe -> list of wtDiff values
        - 'colors': Dict of timeframe -> list of color hex codes
        - 'block_colors': Dict of timeframe -> list of color hex codes (with embedding)
        - 'highest_overbought': List of highest overbought layer indices
        - 'highest_oversold': List of highest oversold layer indices
    """
    if not closes or len(closes) == 0:
        return {
            "wt_a": {},
            "wt_b": {},
            "wt_diff": {},
            "colors": {},
            "block_colors": {},
            "highest_overbought": [],
            "highest_oversold": [],
        }
    
    # Time multipliers: 1, 2, 4, 8, 16, 32, 64, 128
    time_multipliers = [1, 2, 4, 8, 16, 32, 64, 128]
    
    # Calculate oversold levels (negative of overbought)
    os_level = -ob_level
    os_embed_level = -ob_embed_level
    os_extreme_level = -ob_extreme_level
    ob_mild_level = 2 * ob_level / 3
    os_mild_level = -ob_mild_level
    
    # Color definitions (matching Pine Script)
    color_extreme_sell = "#ff00c0"  # fuschia pink
    color_sell = "#FF0060"  # red
    color_mid_sell = "#d01030"  # burgundy
    color_weak_sell = "#b02020"  # brown
    color_neutral_sell = "#903010"  # dark orange
    color_under_mid_sell = "#703010"
    color_under_sell = "#503020"
    color_under_extreme_sell = "#301030"
    
    color_extreme_buy = "#00FFa0"  # lime
    color_buy = "#00ff60"  # bright green
    color_mid_buy = "#00dd40"  # green
    color_weak_buy = "#10b020"  # brown
    color_neutral_buy = "#109030"  # dark orange
    color_under_mid_buy = "#107030"
    color_under_buy = "#105040"
    color_under_extreme_buy = "#104030"
    
    def wt_color(a: float | None, b: float | None) -> str:
        """Calculate color based on wtA and wtB values."""
        if a is None or b is None:
            return "#ffffff"  # white - return white if either value is None
        
        if a < b:
            # Sell colors
            if a >= ob_extreme_level:
                return color_extreme_sell
            elif a >= ob_level:
                return color_sell
            elif a >= ob_mild_level:
                return color_mid_sell
            elif a >= 0:
                return color_weak_sell
            elif a >= os_mild_level:
                return color_neutral_sell
            elif a >= os_level:
                return color_under_mid_sell
            elif a >= os_extreme_level:
                return color_under_sell
            else:
                return color_under_extreme_sell
        else:
            # Buy colors
            if a <= os_extreme_level:
                return color_extreme_buy
            elif a <= os_level:
                return color_buy
            elif a <= os_mild_level:
                return color_mid_buy
            elif a <= 0:
                return color_weak_buy
            elif a <= ob_mild_level:
                return color_neutral_buy
            elif a <= ob_level:
                return color_under_mid_buy
            elif a <= ob_extreme_level:
                return color_under_buy
            else:
                return color_under_extreme_buy
    
    # Calculate WaveTrend for each timeframe
    wt_a_dict: dict[int, list[float | None]] = {}
    wt_b_dict: dict[int, list[float | None]] = {}
    wt_diff_dict: dict[int, list[float | None]] = {}
    colors_dict: dict[int, list[str]] = {}
    debug_info: dict[int, dict[str, float | int]] = {}
    
    for tm in time_multipliers:
        wt_a, wt_b, wt_diff = stochastic_trend(closes, n1, n2, crossover_sma_len, tm)
        wt_a_dict[tm] = wt_a
        wt_b_dict[tm] = wt_b
        wt_diff_dict[tm] = wt_diff
        
        # Calculate colors
        colors: list[str] = []
        for i in range(len(closes)):
            colors.append(wt_color(wt_a[i], wt_b[i]))
        colors_dict[tm] = colors

        # Collect lightweight debug statistics (non-None counts, min/max)
        non_none_a = [x for x in wt_a if x is not None]
        non_none_b = [x for x in wt_b if x is not None]
        debug_info[tm] = {
            "len": len(closes),
            "a_non_none": len(non_none_a),
            "b_non_none": len(non_none_b),
            "a_min": min(non_none_a) if non_none_a else None,
            "a_max": max(non_none_a) if non_none_a else None,
            "b_min": min(non_none_b) if non_none_b else None,
            "b_max": max(non_none_b) if non_none_b else None,
        }
    
    # Calculate embedding conditions and highest overbought/oversold layers
    highest_overbought: list[int] = []
    highest_oversold: list[int] = []
    
    for i in range(len(closes)):
        # Check overbought conditions for each timeframe (skip 1x, start from 2x)
        highest_ob = 0
        highest_os = 0
        
        # Check from highest to lowest timeframe
        for idx, tm in enumerate([64, 32, 16, 8, 4, 2]):
            wt_a = wt_a_dict.get(tm, [None] * len(closes))
            wt_diff = wt_diff_dict.get(tm, [None] * len(closes))
            
            if i < len(wt_a) and i < len(wt_diff):
                a_val = wt_a[i]
                diff_val = wt_diff[i]
                
                if a_val is not None and diff_val is not None:
                    # Overbought embedding check
                    if a_val > ob_embed_level and diff_val > cross_separation:
                        highest_ob = max(highest_ob, idx + 1)
                    
                    # Oversold embedding check
                    if a_val < os_embed_level and diff_val < -cross_separation:
                        highest_os = max(highest_os, idx + 1)
        
        highest_overbought.append(highest_ob)
        highest_oversold.append(highest_os)
    
    # Calculate block colors (with embedding white stripes)
    block_colors_dict: dict[int, list[str]] = {}
    
    def wt_block_color(
        layer_2exponent: int,
        a: float | None,
        b: float | None,
        a_x2: float | None,
        b_x2: float | None,
        highest_overbought_layer: int,
        highest_oversold_layer: int,
        wt_color_val: str,
    ) -> str:
        """Calculate block color with embedding detection."""
        # If any value is None, return the base color (don't apply embedding logic)
        if a is None or b is None or a_x2 is None or b_x2 is None:
            return wt_color_val
        
        # Check for embedding conditions
        if (a is not None and b is not None and a < b) and (
            (a_x2 is not None and b_x2 is not None and a_x2 > ob_extreme_level and a_x2 > b_x2)
            or (layer_2exponent <= (highest_overbought_layer - 1))
        ):
            return "#ffffff"  # white stripe for overbought embedding
        
        if (a is not None and b is not None and a > b) and (
            (a_x2 is not None and b_x2 is not None and a_x2 < os_extreme_level and a_x2 < b_x2)
            or (layer_2exponent <= (highest_oversold_layer - 1))
        ):
            return "#ffffff"  # white stripe for oversold embedding
        
        return wt_color_val
    
    # Calculate block colors for each layer (except 128 which doesn't have a higher layer)
    for idx, tm in enumerate(time_multipliers[:-1]):  # Skip 128
        wt_a = wt_a_dict[tm]
        wt_b = wt_b_dict[tm]
        next_tm = time_multipliers[idx + 1]
        wt_a_next = wt_a_dict[next_tm]
        wt_b_next = wt_b_dict[next_tm]
        colors = colors_dict[tm]
        
        block_colors: list[str] = []
        for i in range(len(closes)):
            block_colors.append(
                wt_block_color(
                    idx,
                    wt_a[i],
                    wt_b[i],
                    wt_a_next[i],
                    wt_b_next[i],
                    highest_overbought[i],
                    highest_oversold[i],
                    colors[i],
                )
            )
        block_colors_dict[tm] = block_colors
    
    # 128 doesn't have a higher layer, so use regular colors
    block_colors_dict[128] = colors_dict[128]
    
    return {
        "wt_a": {str(k): v for k, v in wt_a_dict.items()},
        "wt_b": {str(k): v for k, v in wt_b_dict.items()},
        "wt_diff": {str(k): v for k, v in wt_diff_dict.items()},
        "colors": {str(k): v for k, v in colors_dict.items()},
        "block_colors": {str(k): v for k, v in block_colors_dict.items()},
        "highest_overbought": highest_overbought,
        "highest_oversold": highest_oversold,
        "debug": {str(k): v for k, v in debug_info.items()},
    }

