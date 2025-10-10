import logging
import pandas as pd
from typing import Dict, Any, List
from nodes.core.market.filters.base.base_filter_node import BaseFilterNode
from core.types_registry import get_type, AssetSymbol, OHLCVBar, IndicatorResult, IndicatorType
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
    }

    def __init__(self, id, params: Dict[str, Any]):
        super().__init__(id, params)
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
            return {"filtered_ohlcv_bundle": {}}

        filtered_bundle = {}
        total_symbols = len(ohlcv_bundle)
        processed_symbols = 0

        # Initial progress signal
        try:
            self.report_progress(0.0, f"0/{total_symbols}")
        except Exception:
            pass

        for symbol, ohlcv_data in ohlcv_bundle.items():
            if not ohlcv_data:
                processed_symbols += 1
                try:
                    progress = (processed_symbols / max(1, total_symbols)) * 100.0
                    self.report_progress(progress, f"{processed_symbols}/{total_symbols}")
                except Exception:
                    pass
                continue

            try:
                indicator_result = self._calculate_indicator(ohlcv_data)

                if self._should_pass_filter(indicator_result):
                    filtered_bundle[symbol] = ohlcv_data

            except Exception as e:
                logger.warning(f"Failed to process indicator for {symbol}: {e}")
                # Progress should still advance even on failure
                processed_symbols += 1
                try:
                    progress = (processed_symbols / max(1, total_symbols)) * 100.0
                    self.report_progress(progress, f"{processed_symbols}/{total_symbols}")
                except Exception:
                    pass
                continue

            # Advance progress after successful processing
            processed_symbols += 1
            try:
                progress = (processed_symbols / max(1, total_symbols)) * 100.0
                self.report_progress(progress, f"{processed_symbols}/{total_symbols}")
            except Exception:
                pass

        return {
            "filtered_ohlcv_bundle": filtered_bundle,
        }
