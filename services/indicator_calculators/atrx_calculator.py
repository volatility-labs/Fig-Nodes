from collections import deque
from collections.abc import Sequence
from typing import Any, cast

from .atr_calculator import calculate_atr, calculate_tr
from .sma_calculator import calculate_sma


def calculate_atrx(
    highs: Sequence[float | None],
    lows: Sequence[float | None],
    closes: Sequence[float | None],
    prices: Sequence[float | None],
    length: int = 14,
    ma_length: int = 50,
    smoothing: str = "RMA",
) -> dict[str, Any]:
    """
    Calculate ATRX indicator following TradingView methodology:
    A = ATR% = ATR / Last Done Price
    B = % Gain From 50-MA = (Price - SMA50) / SMA50
    ATRX = B / A = (% Gain From 50-MA) / ATR%

    Args:
        highs: List of high prices (can contain None values)
        lows: List of low prices (can contain None values)
        closes: List of close prices (can contain None values)
        prices: List of prices to use for calculation (can contain None values)
        length: Period for ATR calculation (default: 14)
        ma_length: Period for SMA calculation (default: 50)
        smoothing: Smoothing method for ATR - "RMA" (default), "SMA", or "EMA"

    Returns:
        Dictionary with 'atrx' as a list of calculated values for each row,
        matching the TypeScript implementation that returns full time series.
        Each list contains the calculated values for corresponding rows in the input data.

    Reference:
        https://www.tradingview.com/script/oimVgV7e-ATR-multiple-from-50-MA/
    """
    data_length = len(highs)
    if length <= 0 or ma_length <= 0:
        return {"atrx": [None] * data_length}

    if len(lows) != data_length or len(closes) != data_length or len(prices) != data_length:
        return {"atrx": [None] * data_length}

    # Calculate ATR with specified smoothing
    atr_result = calculate_atr(highs, lows, closes, length, smoothing=smoothing)
    atr_values = atr_result.get("atr", [])

    if not atr_values or len(atr_values) == 0:
        return {"atrx": [None] * data_length}

    # Calculate SMA
    sma_result = calculate_sma(prices, period=ma_length)
    sma_values = sma_result.get("sma", [])

    if not sma_values or len(sma_values) == 0:
        return {"atrx": [None] * data_length}

    # Calculate ATRX for each point
    results: list[float | None] = []

    for i in range(data_length):
        # Need at least ma_length points for SMA and length points for ATR
        if i < max(length, ma_length) - 1:
            results.append(None)
            continue

        current_price = prices[i]
        current_atr = atr_values[i]
        current_sma = sma_values[i]

        # Check for invalid values
        if (
            current_price is None
            or current_atr is None
            or current_sma is None
            or current_atr == 0
            or current_sma == 0
            or current_price == 0
        ):
            results.append(None)
            continue

        # Calculate ATR% = ATR / Last Done Price
        atr_percent = current_atr / current_price

        # Calculate % Gain From 50-MA = (Price - SMA50) / SMA50
        percent_gain_from_50ma = (current_price - current_sma) / current_sma

        # Calculate ATRX = (% Gain From 50-MA) / ATR%
        if atr_percent == 0:
            results.append(None)
        else:
            atrx = percent_gain_from_50ma / atr_percent
            results.append(atrx)

    return {"atrx": results}


def calculate_atrx_last_value(
    highs: Sequence[float | None],
    lows: Sequence[float | None],
    closes: Sequence[float | None],
    prices: Sequence[float | None],
    length: int = 14,
    ma_length: int = 50,
    smoothing: str = "RMA",
) -> float | None:
    """
    Optimized ATRX calculation that only computes the last value.
    Uses incremental sliding windows instead of full array calculations.

    This is 10-30x faster than calculate_atrx() when only the last value is needed.

    Args:
        Same as calculate_atrx()

    Returns:
        The last ATRX value or None if calculation is not possible.
    """
    data_length = len(highs)
    if length <= 0 or ma_length <= 0:
        return None

    if len(lows) != data_length or len(closes) != data_length or len(prices) != data_length:
        return None

    min_required = max(length, ma_length)
    if data_length < min_required:
        return None

    # Calculate TR values incrementally - only what we need for the last ATR
    tr_values: list[float | None] = []
    for i in range(data_length):
        current_high = highs[i]
        current_low = lows[i]
        prev_close = closes[i - 1] if i > 0 else None
        tr_val = calculate_tr(current_high, current_low, prev_close)
        tr_values.append(tr_val)

    # Calculate last ATR value using incremental smoothing
    last_atr: float | None = None

    if smoothing == "SMA":
        # Get last 'length' valid TR values
        tr_window = [v for v in tr_values[-length:] if v is not None]
        if len(tr_window) == length:
            last_atr = sum(tr_window) / length

    elif smoothing == "EMA":
        # EMA: Compute incrementally, only track what's needed for last value
        k = 2 / (length + 1)
        ema: float | None = None
        valid_count = 0

        # Find first valid window to initialize
        for i in range(length - 1, data_length):
            window = tr_values[i - length + 1 : i + 1]
            valid_values = [v for v in window if v is not None]
            if len(valid_values) == length:
                ema = sum(valid_values) / length
                valid_count = i + 1
                break

        if ema is None:
            return None

        # Continue EMA calculation from initialization point
        # ema is guaranteed to be float at this point
        current_ema: float = ema
        for i in range(valid_count, data_length):
            tr_val = tr_values[i]
            if tr_val is not None:
                current_ema = tr_val * k + current_ema * (1 - k)

        last_atr = current_ema

    else:  # RMA (Wilder's Smoothing)
        # RMA: (RMA_prev * (period - 1) + value) / period
        rma: float | None = None
        first_valid_index = -1

        # Find first valid window
        for i in range(length - 1, data_length):
            window = tr_values[i - length + 1 : i + 1]
            valid_values = [v for v in window if v is not None]
            if len(valid_values) == length:
                first_valid_index = i
                seed_window = tr_values[i - length + 1 : i + 1]
                rma = sum(seed_window) / length  # type: ignore
                break

        if rma is None:
            return None

        # Continue RMA calculation incrementally
        # rma is guaranteed to be float at this point
        current_rma: float = cast(float, rma)
        for i in range(first_valid_index + 1, data_length):
            tr_val = tr_values[i]
            if tr_val is not None:
                current_rma = (current_rma * (length - 1) + tr_val) / length

        last_atr = current_rma

    if last_atr is None or last_atr == 0:
        return None

    # Type narrowing: last_atr is guaranteed to be float at this point
    final_atr: float = last_atr

    # Incremental SMA calculation for last value only
    # Use running sum with deque for O(1) window management
    sma_sum = 0.0
    price_deque: deque[float] = deque(maxlen=ma_length)

    for price in prices:
        if price is not None:
            # If deque is at max capacity, remove oldest value from sum
            if len(price_deque) == ma_length:
                oldest = price_deque[0]
                sma_sum -= oldest

            price_deque.append(price)
            sma_sum += price

    if len(price_deque) < ma_length:
        return None

    last_sma = sma_sum / ma_length

    if last_sma == 0:
        return None

    last_price = prices[-1]
    if last_price is None or last_price == 0:
        return None

    # Calculate ATRX from last values
    atr_percent = final_atr / last_price
    if atr_percent == 0:
        return None

    percent_gain_from_50ma = (last_price - last_sma) / last_sma
    atrx = percent_gain_from_50ma / atr_percent

    return atrx
