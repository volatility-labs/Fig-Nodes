import logging
from typing import Dict, Any, List
from nodes.base.base_node import Base
from core.types_registry import get_type, AssetSymbol, OHLCVBar

logger = logging.getLogger(__name__)


class BaseFilter(Base):
    """
    Base class for general filter nodes that filter OHLCV bundles based on arbitrary conditions.
    Suitable for non-indicator based filters (e.g., volume thresholds, price ranges, market cap).

    Input: OHLCV bundle (Dict[AssetSymbol, List[OHLCVBar]])
    Output: Filtered OHLCV bundle (Dict[AssetSymbol, List[OHLCVBar]])
    """
    inputs = {"ohlcv_bundle": get_type("OHLCVBundle")}
    outputs = {"filtered_ohlcv_bundle": get_type("OHLCVBundle")}

    def _filter_condition(self, symbol: AssetSymbol, ohlcv_data: List[OHLCVBar]) -> bool:
        """
        Determine if the asset should pass the filter.
        Must be implemented by subclasses.

        Args:
            symbol: The asset symbol
            ohlcv_data: List of OHLCV bars

        Returns:
            True if the asset passes the filter, False otherwise
        """
        raise NotImplementedError("Subclasses must implement _filter_condition")

    async def _execute_impl(self, inputs: Dict[str, Any]) -> Dict[str, Any]:  # Renamed from execute to _execute_impl
        ohlcv_bundle: Dict[AssetSymbol, List[OHLCVBar]] = inputs.get("ohlcv_bundle", {})

        if not ohlcv_bundle:
            return {"filtered_ohlcv_bundle": {}}

        filtered_bundle = {}

        for symbol, ohlcv_data in ohlcv_bundle.items():
            if not ohlcv_data:
                continue

            if self._filter_condition(symbol, ohlcv_data):
                filtered_bundle[symbol] = ohlcv_data

        return {"filtered_ohlcv_bundle": filtered_bundle}
