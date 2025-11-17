from collections.abc import Sequence
from typing import Any

from .atr_calculator import calculate_atr
from .rma_calculator import calculate_rma


def calculate_cycle_channel_oscillator(
    closes: Sequence[float | None],
    highs: Sequence[float | None],
    lows: Sequence[float | None],
    short_cycle_length: int = 10,
    medium_cycle_length: int = 30,
    short_cycle_multiplier: float = 1.0,
    medium_cycle_multiplier: float = 3.0,
) -> dict[str, Any]:
    """
    Calculate Cycle Channel Oscillator (CCO) indicator.
    
    Based on LazyBear's Cycle Channel Oscillator:
    https://www.tradingview.com/script/3yAQDB3h-Cycle-Channel-Oscillator-LazyBear/
    
    Args:
        closes: List of close prices (source)
        highs: List of high prices (for ATR calculation)
        lows: List of low prices (for ATR calculation)
        short_cycle_length: Short cycle length (default: 10)
        medium_cycle_length: Medium cycle length (default: 30)
        short_cycle_multiplier: Short cycle multiplier (default: 1.0)
        medium_cycle_multiplier: Medium cycle multiplier (default: 3.0)
    
    Returns:
        Dictionary with:
        - 'fast_osc': Fast oscillator (price position in medium channel)
        - 'slow_osc': Slow oscillator (short cycle midline position in medium channel)
    """
    data_length = len(closes)
    
    if data_length == 0:
        return {"fast_osc": [], "slow_osc": []}
    
    if len(highs) != data_length or len(lows) != data_length:
        return {"fast_osc": [None] * data_length, "slow_osc": [None] * data_length}
    
    # Calculate cycle lengths (divided by 2)
    scl = short_cycle_length / 2  # Short cycle length / 2
    mcl = medium_cycle_length / 2  # Medium cycle length / 2
    
    if scl < 1 or mcl < 1:
        return {"fast_osc": [None] * data_length, "slow_osc": [None] * data_length}
    
    # Calculate RMAs
    rma_scl_result = calculate_rma(closes, period=int(scl))
    rma_mcl_result = calculate_rma(closes, period=int(mcl))
    ma_scl = rma_scl_result.get("rma", [])
    ma_mcl = rma_mcl_result.get("rma", [])
    
    # Calculate ATRs
    atr_scl_result = calculate_atr(highs, lows, closes, length=int(scl), smoothing="RMA")
    atr_mcl_result = calculate_atr(highs, lows, closes, length=int(mcl), smoothing="RMA")
    atr_scl = atr_scl_result.get("atr", [])
    atr_mcl = atr_mcl_result.get("atr", [])
    
    # Calculate offsets
    scm_off: list[float | None] = []
    mcm_off: list[float | None] = []
    for i in range(data_length):
        atr_scl_val = atr_scl[i] if i < len(atr_scl) else None
        atr_mcl_val = atr_mcl[i] if i < len(atr_mcl) else None
        scm_off.append(atr_scl_val * short_cycle_multiplier if atr_scl_val is not None else None)
        mcm_off.append(atr_mcl_val * medium_cycle_multiplier if atr_mcl_val is not None else None)
    
    # Calculate shifted indices
    scl_2 = int(scl / 2)
    mcl_2 = int(mcl / 2)
    
    # Calculate channel tops and bottoms
    sct: list[float | None] = []  # Short cycle top
    scb: list[float | None] = []  # Short cycle bottom
    mct: list[float | None] = []  # Medium cycle top
    mcb: list[float | None] = []  # Medium cycle bottom
    
    for i in range(data_length):
        src_val = closes[i]
        scm_off_val = scm_off[i]
        mcm_off_val = mcm_off[i]
        
        # Short cycle: use shifted RMA value, or fallback to src if not available
        ma_scl_idx = i - scl_2
        ma_scl_val = ma_scl[ma_scl_idx] if ma_scl_idx >= 0 and ma_scl_idx < len(ma_scl) and ma_scl[ma_scl_idx] is not None else None
        base_scl = ma_scl_val if ma_scl_val is not None else (src_val if src_val is not None else None)
        
        if base_scl is not None and scm_off_val is not None:
            sct.append(base_scl + scm_off_val)
            scb.append(base_scl - scm_off_val)
        else:
            sct.append(None)
            scb.append(None)
        
        # Medium cycle: use shifted RMA value, or fallback to src if not available
        ma_mcl_idx = i - mcl_2
        ma_mcl_val = ma_mcl[ma_mcl_idx] if ma_mcl_idx >= 0 and ma_mcl_idx < len(ma_mcl) and ma_mcl[ma_mcl_idx] is not None else None
        base_mcl = ma_mcl_val if ma_mcl_val is not None else (src_val if src_val is not None else None)
        
        if base_mcl is not None and mcm_off_val is not None:
            mct.append(base_mcl + mcm_off_val)
            mcb.append(base_mcl - mcm_off_val)
        else:
            mct.append(None)
            mcb.append(None)
    
    # Calculate short cycle midline (average of top and bottom)
    scmm: list[float | None] = []
    for i in range(data_length):
        sct_val = sct[i]
        scb_val = scb[i]
        if sct_val is not None and scb_val is not None:
            scmm.append((sct_val + scb_val) / 2)
        else:
            scmm.append(None)
    
    # Calculate oscillators
    fast_osc: list[float | None] = []  # oshort: price position in medium channel
    slow_osc: list[float | None] = []  # omed: short cycle midline position in medium channel
    
    for i in range(data_length):
        src_val = closes[i]
        mct_val = mct[i]
        mcb_val = mcb[i]
        scmm_val = scmm[i]
        
        # Fast oscillator: (src - mcb) / (mct - mcb)
        if src_val is not None and mct_val is not None and mcb_val is not None:
            denominator = mct_val - mcb_val
            if denominator != 0:
                fast_osc.append((src_val - mcb_val) / denominator)
            else:
                fast_osc.append(None)
        else:
            fast_osc.append(None)
        
        # Slow oscillator: (scmm - mcb) / (mct - mcb)
        if scmm_val is not None and mct_val is not None and mcb_val is not None:
            denominator = mct_val - mcb_val
            if denominator != 0:
                slow_osc.append((scmm_val - mcb_val) / denominator)
            else:
                slow_osc.append(None)
        else:
            slow_osc.append(None)
    
    return {
        "fast_osc": fast_osc,
        "slow_osc": slow_osc,
    }

