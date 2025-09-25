import logging
import pandas as pd
from typing import Dict, Any, List
from nodes.base.base_node import BaseNode
from core.types_registry import get_type, AssetSymbol, OHLCVBar

logger = logging.getLogger(__name__)


class BaseIndicatorFilterNode(BaseNode):
    """
    Base class for indicator filter nodes that filter OHLCV bundles based on technical indicators.

    Input: OHLCV bundle (Dict[AssetSymbol, List[OHLCVBar]])
    Output: Filtered OHLCV bundle (Dict[AssetSymbol, List[OHLCVBar]])
    """
    inputs = {"ohlcv_bundle": Dict[AssetSymbol, List[OHLCVBar]]}
    outputs = {"filtered_ohlcv_bundle": Dict[AssetSymbol, List[OHLCVBar]]}

    def __init__(self, node_id: str, params: Dict[str, Any]):
        super().__init__(node_id, params)
        self._validate_indicator_params()

    def _validate_indicator_params(self):
        """Override in subclasses to validate indicator-specific parameters."""
        pass

    def _calculate_indicator(self, ohlcv_data: List[OHLCVBar]) -> pd.Series:
        """
        Calculate the indicator for the given OHLCV data.
        Must be implemented by subclasses.

        Args:
            ohlcv_data: List of OHLCV bars

        Returns:
            pandas Series with indicator values aligned with the input data
        """
        raise NotImplementedError("Subclasses must implement _calculate_indicator")

    def _should_pass_filter(self, indicator_values: pd.Series) -> bool:
        """
        Determine if the asset should pass the filter based on indicator values.
        Must be implemented by subclasses.

        Args:
            indicator_values: pandas Series with indicator values

        Returns:
            True if the asset passes the filter, False otherwise
        """
        raise NotImplementedError("Subclasses must implement _should_pass_filter")

    async def execute(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        ohlcv_bundle: Dict[AssetSymbol, List[OHLCVBar]] = inputs.get("ohlcv_bundle", {})

        if not ohlcv_bundle:
            return {"filtered_ohlcv_bundle": {}}

        filtered_bundle = {}

        for symbol, ohlcv_data in ohlcv_bundle.items():
            if not ohlcv_data:
                continue

            try:
                # Calculate indicator
                indicator_values = self._calculate_indicator(ohlcv_data)

                # Check if asset passes the filter
                if self._should_pass_filter(indicator_values):
                    filtered_bundle[symbol] = ohlcv_data

            except Exception as e:
                logger.warning(f"Failed to process indicator for {symbol}: {e}")
                continue

        return {"filtered_ohlcv_bundle": filtered_bundle}
