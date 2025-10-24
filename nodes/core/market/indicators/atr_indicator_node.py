import logging
from typing import Any

from core.types_registry import IndicatorResult, IndicatorType, IndicatorValue, get_type
from nodes.core.market.indicators.base.base_indicator_node import BaseIndicator
from services.indicator_calculators.atr_calculator import calculate_atr

logger = logging.getLogger(__name__)


class ATRIndicator(BaseIndicator):
    """
    Computes the ATR indicator for a single asset's OHLCV data.
    """

    inputs = {"ohlcv": get_type("OHLCV")}
    outputs = {"results": list[IndicatorResult]}
    default_params = {
        "window": 14,
    }
    params_meta = [
        {"name": "window", "type": "integer", "default": 14, "min": 1, "step": 1},
    ]

    async def _execute_impl(self, inputs: dict[str, Any]) -> dict[str, Any]:
        ohlcv: list[dict[str, float]] = inputs.get("ohlcv", [])
        if not ohlcv:
            return {"results": []}

        window_value = self.params.get("window", 14)
        if not isinstance(window_value, int):
            return {"results": []}

        highs = [bar["high"] for bar in ohlcv]
        lows = [bar["low"] for bar in ohlcv]
        closes = [bar["close"] for bar in ohlcv]

        if len(highs) < window_value:
            return {"results": []}

        atr_result = calculate_atr(highs, lows, closes, window_value)
        atr_values = atr_result["atr"]
        latest_atr = atr_values[-1] if atr_values else None

        latest_timestamp_ms = int(ohlcv[-1]["timestamp"])
        result = IndicatorResult(
            indicator_type=IndicatorType.ATR,
            timestamp=latest_timestamp_ms,
            values=IndicatorValue(single=latest_atr if latest_atr is not None else 0.0),
            params=self.params,
        )
        return {"results": [result.to_dict()]}

    def _map_to_indicator_value(
        self, ind_type: IndicatorType, raw: dict[str, Any]
    ) -> IndicatorValue:
        # This node computes ATR locally and does not use IndicatorsService mappings.
        # Implementing to satisfy BaseIndicatorNode's abstract method.
        raise ValueError(f"Unsupported indicator type for ATRIndicatorNode: {ind_type.name}")
