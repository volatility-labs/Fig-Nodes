import logging
import pandas as pd
from typing import Dict, Any, List
from nodes.core.market.filters.base.base_filter_node import BaseFilterNode
from core.types_registry import get_type, AssetSymbol, OHLCVBar, IndicatorResult, IndicatorType, MultiAssetIndicatorResults
from services.indicators_service import IndicatorsService

logger = logging.getLogger(__name__)


class BaseIndicatorFilterNode(BaseFilterNode):
    """
    Base class for indicator filter nodes that filter OHLCV bundles based on technical indicators.

    Input: OHLCV bundle (Dict[AssetSymbol, List[OHLCVBar]])
    Output: Filtered OHLCV bundle (Dict[AssetSymbol, List[OHLCVBar]])
    """
    outputs = {
        "filtered_ohlcv_bundle": Dict[AssetSymbol, List[OHLCVBar]],
        "indicator_results": MultiAssetIndicatorResults  # Additional output for computed indicators
    }

    def __init__(self, node_id: str, params: Dict[str, Any]):
        super().__init__(node_id, params)
        self.indicators_service = IndicatorsService()
        self._validate_indicator_params()

    def _validate_indicator_params(self):
        """Override in subclasses to validate indicator-specific parameters."""
        pass

    def _calculate_indicator(self, ohlcv_data: List[OHLCVBar]) -> IndicatorResult:
        """Calculate the indicator using IndicatorsService and return IndicatorResult.
        Must be implemented by subclasses to specify IndicatorType and mapping."""
        raise NotImplementedError("Subclasses must implement _calculate_indicator with IndicatorResult")

    def _should_pass_filter(self, indicator_result: IndicatorResult) -> bool:
        """Determine if the asset should pass based on IndicatorResult.
        Must be implemented by subclasses."""
        raise NotImplementedError("Subclasses must implement _should_pass_filter with IndicatorResult")

    async def execute(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        ohlcv_bundle: Dict[AssetSymbol, List[OHLCVBar]] = inputs.get("ohlcv_bundle", {})

        if not ohlcv_bundle:
            return {"filtered_ohlcv_bundle": {}, "indicator_results": {}}

        filtered_bundle = {}
        indicator_results: MultiAssetIndicatorResults = {}

        for symbol, ohlcv_data in ohlcv_bundle.items():
            if not ohlcv_data:
                continue

            try:
                # Convert to DataFrame for service
                df_data = [{
                    'timestamp': pd.to_datetime(bar['timestamp'], unit='ms'),
                    'Open': bar['open'],
                    'High': bar['high'],
                    'Low': bar['low'],
                    'Close': bar['close'],
                    'Volume': bar['volume']
                } for bar in ohlcv_data]
                df = pd.DataFrame(df_data).set_index('timestamp')

                if df.empty:
                    continue

                # Calculate using subclass method
                indicator_result = self._calculate_indicator(ohlcv_data)

                # Store result
                indicator_results[symbol] = [indicator_result]

                # Filter
                if self._should_pass_filter(indicator_result):
                    filtered_bundle[symbol] = ohlcv_data

            except Exception as e:
                logger.warning(f"Failed to process indicator for {symbol}: {e}")
                # Create error indicator result
                error_result = IndicatorResult(
                    indicator_type=IndicatorType.ADX,
                    timestamp=ohlcv_data[-1]['timestamp'] if ohlcv_data else 0,
                    values={"single": 0.0},
                    error=str(e)
                )
                indicator_results[symbol] = [error_result]
                continue

        return {
            "filtered_ohlcv_bundle": filtered_bundle,
            "indicator_results": indicator_results
        }
