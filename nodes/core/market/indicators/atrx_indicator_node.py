import logging
from typing import Any, cast

import numpy as np
import pandas as pd

from core.types_registry import AssetSymbol, IndicatorResult, IndicatorType, IndicatorValue, get_type
from nodes.core.market.indicators.base.base_indicator_node import BaseIndicator
from services.indicator_calculators.atrx_calculator import calculate_atrx

logger = logging.getLogger(__name__)


class AtrXIndicator(BaseIndicator):
    """
    Computes the ATRX indicator for a single asset's OHLCV data.
    A = ATR% = ATR / Last Done Price
    B = % Gain From 50-MA = (Price - SMA50) / SMA50
    ATRX = B / A = (% Gain From 50-MA) / ATR%

    Reference:
        https://www.tradingview.com/script/oimVgV7e-ATR-multiple-from-50-MA/
    """

    inputs = {"ohlcv": get_type("OHLCVBundle")}
    outputs = {"results": list[IndicatorResult]}
    default_params = {
        "length": 14,  # ATR period
        "ma_length": 50,  # SMA period for trend calculation
    }
    params_meta = [
        {"name": "length", "type": "integer", "default": 14, "description": "ATR period"},
        {
            "name": "ma_length",
            "type": "integer",
            "default": 50,
            "description": "SMA period for trend calculation",
        },
    ]

    def _map_to_indicator_value(
        self, ind_type: IndicatorType, raw: dict[str, Any]
    ) -> IndicatorValue:
        """
        Satisfy BaseIndicatorNode's abstract contract. ATRX node uses its own
        _execute_impl path and does not rely on base mapping.
        """
        return IndicatorValue(single=float("nan"))

    async def _execute_impl(self, inputs: dict[str, Any]) -> dict[str, Any]:
        ohlcv_bundle: dict[AssetSymbol, list[dict[str, float]]] = inputs.get("ohlcv", {})
        if not ohlcv_bundle:
            logger.warning("Empty OHLCV bundle provided to ATRX indicator")
            return {"results": []}

        # Get the first (and typically only) symbol's bars
        ohlcv = next(iter(ohlcv_bundle.values()))
        
        if not ohlcv:
            logger.warning("Empty OHLCV data provided to ATRX indicator")
            return {"results": []}

        try:
            # Check for minimum data requirements first
            length_value = int(cast(int, self.params.get("length", 14)))
            ma_length_value = int(cast(int, self.params.get("ma_length", 50)))
            min_required = max(length_value, ma_length_value)
            if len(ohlcv) < min_required:
                logger.warning(
                    f"Insufficient data for ATRX calculation: {len(ohlcv)} bars, need {min_required}"
                )
                return {"results": []}

            # Extract lists directly from OHLCV data
            high_prices = [bar["high"] for bar in ohlcv]
            low_prices = [bar["low"] for bar in ohlcv]
            close_prices = [bar["close"] for bar in ohlcv]

            # Create minimal DataFrame for calculator API
            df_calc = pd.DataFrame(
                {
                    "high": high_prices,
                    "low": low_prices,
                    "close": close_prices,
                }
            )

            # Call calculator directly
            atrx_result = calculate_atrx(
                df_calc,
                length=length_value,
                ma_length=ma_length_value,
                source="close",
            )
            atrx_values = atrx_result.get("atrx", [])

            if not atrx_values:
                logger.warning("ATRX calculation returned empty results")
                return {"results": []}

            # Get the last value
            atrx_value = atrx_values[-1]

            # Filter out NaN results (e.g., zero volatility cases)
            if atrx_value is None or np.isnan(atrx_value):
                logger.warning("ATRX calculation resulted in NaN (likely zero volatility)")
                return {"results": []}

            result = IndicatorResult(
                indicator_type=IndicatorType.ATRX,
                timestamp=int(ohlcv[-1]["timestamp"]),
                values=IndicatorValue(single=atrx_value),
            )
            return {"results": [result]}

        except Exception as e:
            logger.error(f"Error calculating ATRX indicator: {e}")
            return {"results": []}
