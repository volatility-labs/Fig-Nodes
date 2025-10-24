from collections.abc import Sequence
from typing import Any

from .atr_calculator import calculate_atr
from .sma_calculator import calculate_sma


def calculate_atrx(
    highs: Sequence[float | None],
    lows: Sequence[float | None],
    closes: Sequence[float | None],
    prices: Sequence[float | None],
    length: int = 14,
    ma_length: int = 50,
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

    # Calculate ATR
    atr_result = calculate_atr(highs, lows, closes, length)
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
