from collections.abc import Sequence
from typing import Any


def calculate_wilder_ma(arr: Sequence[float | None], period: int) -> list[float | None]:
    """
    Calculate Wilder's Moving Average (exponential moving average with alpha = 1/period).

    Args:
        arr: List of values, can contain None values
        period: The period for the moving average

    Returns:
        List of Wilder MA values (same length as input)
    """
    ma: list[float | None] = []
    sum_val = 0.0
    count = 0
    started = False
    has_broken = False

    for i in range(len(arr)):
        if has_broken:
            ma.append(None)
            continue

        current_val = arr[i]
        if current_val is None:
            if count > 0 or started:
                has_broken = True
            sum_val = 0.0
            count = 0
            ma.append(None)
            continue

        sum_val += current_val
        count += 1

        if count < period:
            ma.append(None)
            continue

        if count == period:
            ma.append(sum_val / period)
            started = True
            continue

        # Subsequent values use Wilder's smoothing formula
        prev = ma[i - 1]
        if prev is not None:
            ma.append((prev * (period - 1) + current_val) / period)
        else:
            ma.append(None)

    return ma


def calculate_adx(
    highs: Sequence[float | None],
    lows: Sequence[float | None],
    closes: Sequence[float | None],
    period: int = 14,
) -> dict[str, Any]:
    """
    Calculate ADX (Average Directional Index) indicator.

    Args:
        highs: List of high prices (can contain None values)
        lows: List of low prices (can contain None values)
        closes: List of close prices (can contain None values)
        period: Period for ADX calculation (default: 14)

    Returns:
        Dictionary with 'adx', 'pdi', 'ndi' as lists of calculated values for each row,
        matching the TypeScript implementation that returns full time series.
        Each list contains the calculated values for corresponding rows in the input data.
    """
    data_length = len(highs)
    if data_length == 0 or data_length < period or period <= 0:
        return {"adx": [], "pdi": [], "ndi": []}

    if len(lows) != data_length or len(closes) != data_length:
        return {"adx": [], "pdi": [], "ndi": []}

    # Calculate True Range
    tr: list[float | None] = []
    pdm: list[float | None] = []
    ndm: list[float | None] = []

    for i in range(data_length):
        current_high = highs[i]
        current_low = lows[i]

        if current_high is None or current_low is None:
            tr.append(None)
            pdm.append(None)
            ndm.append(None)
            continue

        # Previous values
        prev_high = highs[i - 1] if i > 0 else None
        prev_low = lows[i - 1] if i > 0 else None
        prev_close = closes[i - 1] if i > 0 else None

        # True Range calculation
        hl_range = current_high - current_low

        hc_range = 0.0
        if prev_close is not None:
            hc_range = abs(current_high - prev_close)

        lc_range = 0.0
        if prev_close is not None:
            lc_range = abs(current_low - prev_close)

        tr_val = max(hl_range, hc_range, lc_range)
        tr.append(tr_val)

        # Directional Movement
        if i > 0 and prev_high is not None and prev_low is not None:
            up_move = current_high - prev_high
            down_move = prev_low - current_low
            pdm.append(up_move if (up_move > down_move and up_move > 0) else 0.0)
            ndm.append(down_move if (down_move > up_move and down_move > 0) else 0.0)
        else:
            pdm.append(0.0)
            ndm.append(0.0)

    # Calculate smoothed values using Wilder's MA
    smoothed_tr = calculate_wilder_ma(tr, period)
    smoothed_pdm = calculate_wilder_ma(pdm, period)
    smoothed_ndm = calculate_wilder_ma(ndm, period)

    # Calculate PDI and NDI
    pdi: list[float | None] = []
    ndi: list[float | None] = []
    dx: list[float | None] = []

    for i in range(data_length):
        s_tr = smoothed_tr[i]
        s_pdm = smoothed_pdm[i]
        s_ndm = smoothed_ndm[i]

        if s_tr is not None and s_pdm is not None and s_ndm is not None and s_tr > 0:
            current_pdi = (s_pdm / s_tr) * 100
            current_ndi = (s_ndm / s_tr) * 100
            pdi.append(current_pdi)
            ndi.append(current_ndi)

            di_sum = current_pdi + current_ndi
            dx_val = 0 if di_sum == 0 else (abs(current_pdi - current_ndi) / di_sum) * 100
            dx.append(dx_val)
        else:
            pdi.append(None)
            ndi.append(None)
            dx.append(None)

    # Calculate ADX using Wilder's MA on DX
    adx = calculate_wilder_ma(dx, period)

    # Return full time series matching TypeScript implementation
    return {
        "adx": adx,
        "pdi": pdi,
        "ndi": ndi,
    }
