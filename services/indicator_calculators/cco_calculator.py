"""
Cycle Channel Oscillator (CCO) Calculator

Implements the Cycle Channel Oscillator indicator by LazyBear.

Based on TradingView script: https://www.tradingview.com/script/3yAQDB3h-Cycle-Channel-Oscillator-LazyBear/

The indicator calculates two oscillators:

- Fast Oscillator (oshort): Shows price location within the medium-term channel

- Slow Oscillator (omed): Shows location of short-term midline within medium-term channel
"""

from collections.abc import Sequence
from typing import Any

from .atr_calculator import calculate_atr
from .rma_calculator import calculate_rma


def calculate_cco(
    closes: Sequence[float | None],
    highs: Sequence[float | None] | None = None,
    lows: Sequence[float | None] | None = None,
    short_cycle_length: int = 10,
    medium_cycle_length: int = 30,
    short_cycle_multiplier: float = 1.0,
    medium_cycle_multiplier: float = 3.0,
) -> dict[str, Any]:
    """
    Calculate Cycle Channel Oscillator (CCO).

    Args:
        closes: Close prices
        highs: High prices (optional, for ATR calculation)
        lows: Low prices (optional, for ATR calculation)
        short_cycle_length: Short cycle length (default 10)
        medium_cycle_length: Medium cycle length (default 30)
        short_cycle_multiplier: Short cycle multiplier for ATR offset (default 1.0)
        medium_cycle_multiplier: Medium cycle multiplier for ATR offset (default 3.0)

    Returns:
        Dictionary with:
        - 'fast_osc': Fast oscillator values (oshort)
        - 'slow_osc': Slow oscillator values (omed)
        - 'short_cycle_top': Short cycle channel top
        - 'short_cycle_bottom': Short cycle channel bottom
        - 'short_cycle_midline': Short cycle channel midline
        - 'medium_cycle_top': Medium cycle channel top
        - 'medium_cycle_bottom': Medium cycle channel bottom
    """
    if not closes or len(closes) == 0:
        return {
            "fast_osc": [],
            "slow_osc": [],
            "short_cycle_top": [],
            "short_cycle_bottom": [],
            "short_cycle_midline": [],
            "medium_cycle_top": [],
            "medium_cycle_bottom": [],
        }

    if short_cycle_length <= 0 or medium_cycle_length <= 0:
        data_length = len(closes)
        return {
            "fast_osc": [None] * data_length,
            "slow_osc": [None] * data_length,
            "short_cycle_top": [None] * data_length,
            "short_cycle_bottom": [None] * data_length,
            "short_cycle_midline": [None] * data_length,
            "medium_cycle_top": [None] * data_length,
            "medium_cycle_bottom": [None] * data_length,
        }

    # Convert to lists
    closes_list = list(closes)
    data_length = len(closes_list)

    # Calculate cycle lengths (divided by 2 as in PineScript)
    scl = short_cycle_length / 2.0  # Short cycle length / 2
    mcl = medium_cycle_length / 2.0  # Medium cycle length / 2
    scl_2 = scl / 2.0  # Half of short cycle
    mcl_2 = mcl / 2.0  # Half of medium cycle

    # Calculate RMAs
    rma_short_result = calculate_rma(closes_list, int(scl))
    rma_medium_result = calculate_rma(closes_list, int(mcl))

    ma_scl = rma_short_result.get("rma", [None] * data_length)
    ma_mcl = rma_medium_result.get("rma", [None] * data_length)

    # Calculate ATR for offsets
    # Use closes for ATR if highs/lows not available (less accurate but works)
    if highs is None or lows is None:
        # Approximate ATR using closes (not ideal but works)
        highs_list = closes_list
        lows_list = closes_list
    else:
        highs_list = list(highs)
        lows_list = list(lows)

    # Calculate ATR for short and medium cycles
    atr_short_result = calculate_atr(highs_list, lows_list, closes_list, int(scl), smoothing="RMA")
    atr_medium_result = calculate_atr(highs_list, lows_list, closes_list, int(mcl), smoothing="RMA")

    atr_short = atr_short_result.get("atr", [None] * data_length)
    atr_medium = atr_medium_result.get("atr", [None] * data_length)

    # Calculate offsets
    scm_off: list[float | None] = []
    mcm_off: list[float | None] = []
    for i in range(data_length):
        if atr_short[i] is not None:
            scm_off.append(short_cycle_multiplier * atr_short[i])
        else:
            scm_off.append(None)

        if atr_medium[i] is not None:
            mcm_off.append(medium_cycle_multiplier * atr_medium[i])
        else:
            mcm_off.append(None)

    # Calculate channel tops and bottoms
    # sct = nz(ma_scl[scl_2], src) + scm_off
    # scb = nz(ma_scl[scl_2], src) - scm_off
    # mct = nz(ma_mcl[mcl_2], src) + mcm_off
    # mcb = nz(ma_mcl[mcl_2], src) - mcm_off

    sct: list[float | None] = []
    scb: list[float | None] = []
    mct: list[float | None] = []
    mcb: list[float | None] = []

    for i in range(data_length):
        # Short cycle channels
        scl_2_idx = int(i - scl_2) if i >= scl_2 else 0
        ma_scl_val_raw = (
            ma_scl[scl_2_idx]
            if scl_2_idx >= 0 and ma_scl[scl_2_idx] is not None
            else closes_list[i]
        )
        scm_off_raw = scm_off[i]
        scm_off_val: float = scm_off_raw if scm_off_raw is not None else 0.0

        if ma_scl_val_raw is not None:
            ma_scl_val: float = ma_scl_val_raw
            sct.append(ma_scl_val + scm_off_val)
            scb.append(ma_scl_val - scm_off_val)
        else:
            sct.append(None)
            scb.append(None)

        # Medium cycle channels
        mcl_2_idx = int(i - mcl_2) if i >= mcl_2 else 0
        ma_mcl_val_raw = (
            ma_mcl[mcl_2_idx]
            if mcl_2_idx >= 0 and ma_mcl[mcl_2_idx] is not None
            else closes_list[i]
        )
        mcm_off_raw = mcm_off[i]
        mcm_off_val: float = mcm_off_raw if mcm_off_raw is not None else 0.0

        if ma_mcl_val_raw is not None:
            ma_mcl_val: float = ma_mcl_val_raw
            mct.append(ma_mcl_val + mcm_off_val)
            mcb.append(ma_mcl_val - mcm_off_val)
        else:
            mct.append(None)
            mcb.append(None)

    # Calculate short cycle midline (average of top and bottom)
    scmm: list[float | None] = []
    for i in range(data_length):
        sct_val = sct[i]
        scb_val = scb[i]
        if sct_val is not None and scb_val is not None:
            scmm.append((sct_val + scb_val) / 2.0)
        else:
            scmm.append(None)

    # Calculate oscillators
    # omed = (scmm - mcb) / (mct - mcb)  # Slow oscillator
    # oshort = (src - mcb) / (mct - mcb)  # Fast oscillator

    omed: list[float | None] = []
    oshort: list[float | None] = []

    for i in range(data_length):
        # Slow oscillator (omed)
        scmm_val = scmm[i]
        mcb_val = mcb[i]
        mct_val = mct[i]
        if scmm_val is not None and mcb_val is not None and mct_val is not None:
            mct_mcb_diff = mct_val - mcb_val
            if mct_mcb_diff != 0:
                omed_val = (scmm_val - mcb_val) / mct_mcb_diff
                omed.append(omed_val)
            else:
                omed.append(0.5)  # Default to middle if no range
        else:
            omed.append(None)

        # Fast oscillator (oshort)
        close_val = closes_list[i]
        mcb_val = mcb[i]
        mct_val = mct[i]
        if close_val is not None and mcb_val is not None and mct_val is not None:
            mct_mcb_diff = mct_val - mcb_val
            if mct_mcb_diff != 0:
                oshort_val = (close_val - mcb_val) / mct_mcb_diff
                oshort.append(oshort_val)
            else:
                oshort.append(0.5)  # Default to middle if no range
        else:
            oshort.append(None)

    return {
        "fast_osc": oshort,
        "slow_osc": omed,
        "short_cycle_top": sct,
        "short_cycle_bottom": scb,
        "short_cycle_midline": scmm,
        "medium_cycle_top": mct,
        "medium_cycle_bottom": mcb,
    }
