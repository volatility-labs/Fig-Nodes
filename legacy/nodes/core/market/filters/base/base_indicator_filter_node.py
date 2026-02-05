import logging
from collections.abc import ItemsView
from typing import Any

from core.types_registry import AssetSymbol, IndicatorResult, NodeCategory, OHLCVBar
from nodes.core.market.filters.base.base_filter_node import BaseFilter

logger = logging.getLogger(__name__)


class BaseIndicatorFilter(BaseFilter):
    """
    Base class for indicator filter nodes that filter OHLCV bundles based on technical indicators.

    Input: OHLCV bundle (Dict[AssetSymbol, List[OHLCVBar]])
    Output: Filtered OHLCV bundle (Dict[AssetSymbol, List[OHLCVBar]])
    """

    CATEGORY = NodeCategory.MARKET

    def __init__(
        self, id: int, params: dict[str, Any], graph_context: dict[str, Any] | None = None
    ):  # Explicit constructor for consistency
        super().__init__(id, params, graph_context)
        self._validate_indicator_params()

    def _validate_indicator_params(self):
        """Override in subclasses to validate indicator-specific parameters."""
        pass

    def validate_inputs(self, inputs: dict[str, Any]) -> None:
        """
        Normalize ohlcv_bundle to ensure all values are lists, not None.

        This provides consistent handling across all indicator filters for cases where
        upstream nodes may not have normalized None values in bundles. Empty lists
        indicate no data and are skipped during execution.
        """
        bundle_raw = inputs.get("ohlcv_bundle")
        if bundle_raw is not None and isinstance(bundle_raw, dict):
            # Normalize the bundle by ensuring all values are lists
            normalized_bundle: dict[AssetSymbol, list[OHLCVBar]] = {}
            items: ItemsView[Any, Any] = bundle_raw.items()
            for key, value in items:
                # Type guard: ensure key is AssetSymbol
                if not isinstance(key, AssetSymbol):
                    continue
                symbol: AssetSymbol = key
                # Type guard: ensure value is either a list or None
                if value is None:
                    normalized_bundle[symbol] = []
                elif isinstance(value, list):
                    normalized_bundle[symbol] = value
                else:
                    # If value is neither None nor a list, skip this entry
                    continue
            inputs["ohlcv_bundle"] = normalized_bundle
        super().validate_inputs(inputs)

    def _calculate_indicator(self, ohlcv_data: list[OHLCVBar]) -> IndicatorResult:
        """Calculate the indicator and return IndicatorResult.
        Must be implemented by subclasses to specify IndicatorType and mapping."""
        raise NotImplementedError(
            "Subclasses must implement _calculate_indicator with IndicatorResult"
        )

    def _should_pass_filter(self, indicator_result: IndicatorResult) -> bool:
        """Determine if the asset should pass based on IndicatorResult.
        Must be implemented by subclasses."""
        raise NotImplementedError(
            "Subclasses must implement _should_pass_filter with IndicatorResult"
        )

    async def _execute_impl(self, inputs: dict[str, Any]) -> dict[str, Any]:
        ohlcv_bundle: dict[AssetSymbol, list[OHLCVBar]] = inputs.get("ohlcv_bundle", {})

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
