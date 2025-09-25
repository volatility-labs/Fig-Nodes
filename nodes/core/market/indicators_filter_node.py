import logging
from typing import Dict, Any, List
from nodes.base.base_node import BaseNode
from core.types_registry import get_type, AssetSymbol

logger = logging.getLogger(__name__)

class IndicatorsFilterNode(BaseNode):
    """
    Filters a list of symbols based on technical indicator thresholds.
    """
    inputs = {"indicators": Dict[AssetSymbol, Dict[str, Any]]}
    outputs = {"filtered_symbols": List[AssetSymbol]}
    default_params = {
        "min_adx": 0.0,
        "require_eis_bullish": False,
        "require_eis_bearish": False,
        "min_hurst": 0.0,
        "min_acceleration": -10.0,  # Allow negative acceleration (declining momentum)
        "min_volume_ratio": 0.0,     # Allow any volume ratio
    }
    params_meta = [
        {"name": "min_adx", "type": "number", "default": 0.0, "min": 0.0, "step": 0.1},
        {"name": "require_eis_bullish", "type": "combo", "default": False, "options": [True, False]},
        {"name": "require_eis_bearish", "type": "combo", "default": False, "options": [True, False]},
        {"name": "min_hurst", "type": "number", "default": 0.0, "min": 0.0, "step": 0.1},
        {"name": "min_acceleration", "type": "number", "default": -10.0, "step": 0.01},
        {"name": "min_volume_ratio", "type": "number", "default": 0.0, "min": 0.0, "step": 0.1},
    ]

    async def execute(self, inputs: Dict[str, Any]) -> Dict[str, List[AssetSymbol]]:
        indicators: Dict[AssetSymbol, Dict[str, Any]] = inputs.get("indicators", {})
        if not indicators:
            return {"filtered_symbols": []}

        min_adx = self.params.get("min_adx", 0.0)
        require_eis_bullish = self.params.get("require_eis_bullish", False)
        require_eis_bearish = self.params.get("require_eis_bearish", False)
        min_hurst = self.params.get("min_hurst", 0.0)
        min_acceleration = self.params.get("min_acceleration", 0.0)
        min_volume_ratio = self.params.get("min_volume_ratio", 1.0)

        filtered = []
        for symbol, ind in indicators.items():
            if not ind:
                continue
            # Handle NaN values by treating them as passing (don't filter out due to missing data)
            adx_val = ind.get("adx", 0)
            hurst_val = ind.get("hurst", 0)
            acceleration_val = ind.get("acceleration", 0)
            volume_ratio_val = ind.get("volume_ratio", 1.0)

            # Use math.isnan if available, otherwise check for NaN values
            import math
            adx_ok = math.isnan(adx_val) or adx_val >= min_adx
            hurst_ok = math.isnan(hurst_val) or hurst_val >= min_hurst
            acceleration_ok = math.isnan(acceleration_val) or acceleration_val >= min_acceleration
            volume_ratio_ok = math.isnan(volume_ratio_val) or volume_ratio_val >= min_volume_ratio

            eis_bullish_ok = not require_eis_bullish or ind.get("eis_bullish", False)
            eis_bearish_ok = not require_eis_bearish or ind.get("eis_bearish", False)

            if adx_ok and eis_bullish_ok and eis_bearish_ok and hurst_ok and acceleration_ok and volume_ratio_ok:
                filtered.append(symbol)

        return {"filtered_symbols": filtered}
