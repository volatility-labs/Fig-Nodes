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
        "min_acceleration": 0.0,
        "min_volume_ratio": 1.0,
        # Add more based on indicators_service.py keys
    }
    params_meta = [
        {"name": "min_adx", "type": "number", "default": 0.0, "min": 0.0, "step": 0.1},
        {"name": "require_eis_bullish", "type": "combo", "default": False, "options": [True, False]},
        {"name": "require_eis_bearish", "type": "combo", "default": False, "options": [True, False]},
        {"name": "min_hurst", "type": "number", "default": 0.0, "min": 0.0, "step": 0.1},
        {"name": "min_acceleration", "type": "number", "default": 0.0, "step": 0.01},
        {"name": "min_volume_ratio", "type": "number", "default": 1.0, "min": 0.0, "step": 0.1},
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
            if (ind.get("adx", 0) >= min_adx and
                (not require_eis_bullish or ind.get("eis_bullish", False)) and
                (not require_eis_bearish or ind.get("eis_bearish", False)) and
                ind.get("hurst", 0) >= min_hurst and
                ind.get("acceleration", 0) >= min_acceleration and
                ind.get("volume_ratio", 1.0) >= min_volume_ratio):
                filtered.append(symbol)

        return {"filtered_symbols": filtered}
