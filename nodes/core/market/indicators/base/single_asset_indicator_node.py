import numpy as np
from typing import Dict
from core.types_registry import IndicatorType, IndicatorValue
from nodes.core.market.indicators.base.base_indicator_node import BaseIndicatorNode

class SingleAssetIndicatorNode(BaseIndicatorNode):
    """
    Concrete node for computing indicators on a single asset's OHLCV data.
    Extends BaseIndicatorNode with specific mappings for supported indicators.
    """

    def _map_to_indicator_value(self, ind_type: IndicatorType, raw: Dict[str, any]) -> IndicatorValue:
        """
        Maps raw indicator values from IndicatorsService to IndicatorValue format.
        Handles heterogeneous outputs per indicator type.
        """
        if ind_type == IndicatorType.EVWMA:
            return IndicatorValue(single=raw.get("evwma", np.nan))
        elif ind_type == IndicatorType.EIS:
            return IndicatorValue(single=float(raw.get("eis_bullish", False) or raw.get("eis_bearish", False)))
        elif ind_type == IndicatorType.ADX:
            return IndicatorValue(single=raw.get("adx", np.nan))
        elif ind_type == IndicatorType.HURST:
            return IndicatorValue(single=raw.get("hurst", np.nan))
        elif ind_type == IndicatorType.VOLUME_RATIO:
            return IndicatorValue(single=raw.get("volume_ratio", 1.0))
        elif ind_type == IndicatorType.MACD:
            # MACD has lines: macd, signal, histogram
            # Note: IndicatorsService doesn't compute full MACD; adapt or extend service
            return IndicatorValue(lines={
                "macd": np.nan,  # Placeholder; extend service if needed
                "signal": np.nan,
                "histogram": np.nan
            })
        elif ind_type == IndicatorType.RSI:
            # RSI series over time
            return IndicatorValue(series=[])  # Placeholder; compute via pandas-ta or extend
        else:
            raise ValueError(f"Unsupported indicator type: {ind_type.name}")

        # Fallback for unmapped
        return IndicatorValue(single=np.nan)
