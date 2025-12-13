import logging
from collections.abc import ItemsView
from typing import Any

from core.types_registry import AssetSymbol, ConfigDict, IndicatorResult, NodeCategory, OHLCVBar, get_type
from nodes.core.market.filters.base.base_filter_node import BaseFilter

logger = logging.getLogger(__name__)


class BaseIndicatorFilter(BaseFilter):
    """
    Base class for indicator filter nodes that filter OHLCV bundles based on technical indicators.

    Input: OHLCV bundle (Dict[AssetSymbol, List[OHLCVBar]])
    Outputs:
    - filtered_ohlcv_bundle: Filtered OHLCV bundle (Dict[AssetSymbol, List[OHLCVBar]])
    - indicator_data: Optional indicator data for filtered symbols (ConfigDict)
    
    When output_indicator_data=True, outputs indicator values for symbols that passed the filter.
    This allows connecting filter nodes directly to MultiIndicatorChart without duplicate calculations.
    """

    CATEGORY = NodeCategory.MARKET
    
    # Override outputs to include optional indicator_data
    outputs = {
        "filtered_ohlcv_bundle": get_type("OHLCVBundle"),
        "indicator_data": get_type("ConfigDict") | None,
    }
    
    default_params = {
        # Default to True so indicator outputs are available without extra clicks
        "output_indicator_data": True,
    }
    
    params_meta = [
        {
            "name": "output_indicator_data",
            "type": "combo",
            "default": True,
            "options": [True, False],
            "label": "Output Indicator Data",
            "description": "Output indicator values for symbols that passed the filter (for use with MultiIndicatorChart)",
        },
    ]

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
            output_indicator_data = self.params.get("output_indicator_data", self.default_params.get("output_indicator_data", True))
            result = {"filtered_ohlcv_bundle": {}}
            # ALWAYS output indicator_data (even if empty) so connections are visible
            result["indicator_data"] = {}
            return result

        filtered_bundle = {}
        indicator_data_output: dict[str, Any] = {}  # Per-symbol indicator data
        # Default to True (from default_params) if not explicitly set
        output_indicator_data = self.params.get("output_indicator_data", self.default_params.get("output_indicator_data", True))
        
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
                    
                    # Store indicator data if enabled
                    if output_indicator_data:
                        # Convert IndicatorResult to dict format compatible with MultiIndicatorChart
                        # Store as per-symbol structure: {symbol: indicator_data}
                        # This format allows MultiIndicatorChart to extract indicators for filtered symbols
                        symbol_key = str(symbol)
                        try:
                            # Use to_dict() method if available (preferred)
                            indicator_dict = indicator_result.to_dict()
                        except (AttributeError, TypeError):
                            # Fallback: manually construct dict
                            indicator_dict = {
                                "indicator_type": str(indicator_result.indicator_type) if hasattr(indicator_result, 'indicator_type') else "unknown",
                                "values": {},
                                "timestamp": indicator_result.timestamp if hasattr(indicator_result, 'timestamp') else None,
                                "params": indicator_result.params if hasattr(indicator_result, 'params') else {},
                            }
                            # Try to extract values
                            if hasattr(indicator_result, 'values'):
                                values = indicator_result.values
                                if hasattr(values, 'to_dict'):
                                    indicator_dict["values"] = values.to_dict()
                                else:
                                    # Manual extraction
                                    indicator_dict["values"] = {
                                        "single": getattr(values, 'single', None),
                                        "lines": getattr(values, 'lines', {}),
                                        "series": getattr(values, 'series', []),
                                    }
                        indicator_data_output[symbol_key] = indicator_dict

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

        result = {
            "filtered_ohlcv_bundle": filtered_bundle,
        }
        
        # ALWAYS output indicator_data (even if empty) so MultiIndicatorChart can detect the connection
        # This ensures the graph executor will pass it even if empty
        
        # ALWAYS include indicator_data in output, even if empty
        # This ensures the graph executor will pass it to downstream nodes
        result["indicator_data"] = indicator_data_output if output_indicator_data else {}
        
        return result
