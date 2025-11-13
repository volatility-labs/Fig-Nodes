import logging
from typing import Any

from core.types_registry import AssetSymbol, OHLCVBar, get_type
from nodes.core.market.filters.base.base_filter_node import BaseFilter

logger = logging.getLogger(__name__)


class DuplicateSymbolFilter(BaseFilter):
    """
    Compare symbols across up to 3 inputs to find common or unique symbols.

    Accepts OHLCV bundles or symbol lists from ExtractSymbols.
    Connect up to 3 inputs to compare symbols between them.
    """

    inputs = {
        "ohlcv_bundle_1": get_type("OHLCVBundle") | get_type("AssetSymbolList") | None,
        "ohlcv_bundle_2": get_type("OHLCVBundle") | get_type("AssetSymbolList") | None,
        "ohlcv_bundle_3": get_type("OHLCVBundle") | get_type("AssetSymbolList") | None,
    }

    default_params = {
        "operation": "common",  # common, unique_to_1, unique_to_2, unique_to_3, all
        "compare_by": "ticker",  # ticker, symbol_string
        "case_insensitive": True,
    }

    params_meta = [
        {
            "name": "operation",
            "type": "combo",
            "default": "common",
            "options": [
                "common",
                "unique_to_1",
                "unique_to_2",
                "unique_to_3",
                "all",
            ],
            "label": "Operation",
            "description": "common: symbols in all connected inputs | unique_to_X: symbols only in ohlcv_bundle_X | all: union of all symbols",
        },
        {
            "name": "compare_by",
            "type": "combo",
            "default": "ticker",
            "options": ["ticker", "symbol_string"],
            "label": "Compare By",
            "description": "Compare symbols by ticker (base symbol) or full symbol string",
        },
        {
            "name": "case_insensitive",
            "type": "boolean",
            "default": True,
            "label": "Case Insensitive",
            "description": "Compare symbols case-insensitively",
        },
    ]

    def __init__(
        self,
        id: int,
        params: dict[str, Any] | None = None,
        graph_context: dict[str, Any] | None = None,
    ):
        super().__init__(id, params or {}, graph_context)

    def _normalize_input(self, input_data: Any) -> dict[AssetSymbol, list[OHLCVBar]]:
        """Normalize input to OHLCV bundle format.

        Handles both OHLCV bundles (dict[AssetSymbol, list[OHLCVBar]])
        and symbol lists (list[AssetSymbol]).
        """
        if input_data is None:
            return {}

        # If it's a list, treat as symbol list and create empty bundles
        if isinstance(input_data, list):
            result: dict[AssetSymbol, list[OHLCVBar]] = {}
            symbol_list: list[Any] = input_data
            for item in symbol_list:
                if isinstance(item, AssetSymbol):
                    result[item] = []
            return result

        # If it's a dict, assume it's an OHLCV bundle
        if isinstance(input_data, dict):
            result: dict[AssetSymbol, list[OHLCVBar]] = {}
            input_dict: dict[Any, Any] = input_data
            for key, value in input_dict.items():
                if isinstance(key, AssetSymbol) and isinstance(value, list):
                    # Type guard: verify value is a list and convert to list[OHLCVBar]
                    ohlcv_list: list[OHLCVBar] = []
                    value_list: list[Any] = value
                    for bar_item in value_list:
                        # Check if bar_item has the structure of OHLCVBar
                        if isinstance(bar_item, dict):
                            bar_dict: dict[str, Any] = bar_item
                            if all(
                                field in bar_dict
                                for field in ["timestamp", "open", "high", "low", "close", "volume"]
                            ):
                                # Create properly typed OHLCVBar dict
                                ohlcv_bar: OHLCVBar = {
                                    "timestamp": bar_dict["timestamp"],
                                    "open": bar_dict["open"],
                                    "high": bar_dict["high"],
                                    "low": bar_dict["low"],
                                    "close": bar_dict["close"],
                                    "volume": bar_dict["volume"],
                                }
                                ohlcv_list.append(ohlcv_bar)
                    result[key] = ohlcv_list
            return result

        return {}

    def _get_symbols_from_input(
        self, input_data: dict[AssetSymbol, list[OHLCVBar]]
    ) -> list[AssetSymbol]:
        """Extract list of symbols from normalized input."""
        return list(input_data.keys())

    def _make_key(self, symbol: AssetSymbol) -> str:
        """Create a comparison key from a symbol based on compare_by setting."""
        compare_by = self.params.get("compare_by", "ticker")
        case_insensitive = self.params.get("case_insensitive", True)

        if compare_by == "ticker":
            key = symbol.ticker
        else:  # symbol_string
            key = str(symbol)

        if case_insensitive:
            return key.lower()
        return key

    async def _execute_impl(self, inputs: dict[str, Any]) -> dict[str, Any]:
        # Normalize all inputs to OHLCV bundle format
        ohlcv_bundle_1 = self._normalize_input(inputs.get("ohlcv_bundle_1"))
        ohlcv_bundle_2 = self._normalize_input(inputs.get("ohlcv_bundle_2"))
        ohlcv_bundle_3 = self._normalize_input(inputs.get("ohlcv_bundle_3"))

        # Get operation mode
        operation = self.params.get("operation", "common")

        # Determine which inputs are connected
        connected_inputs: list[tuple[str, dict[AssetSymbol, list[OHLCVBar]]]] = []
        if ohlcv_bundle_1:
            connected_inputs.append(("ohlcv_bundle_1", ohlcv_bundle_1))
        if ohlcv_bundle_2:
            connected_inputs.append(("ohlcv_bundle_2", ohlcv_bundle_2))
        if ohlcv_bundle_3:
            connected_inputs.append(("ohlcv_bundle_3", ohlcv_bundle_3))

        if not connected_inputs:
            logger.warning("DuplicateSymbolFilter: No inputs connected")
            return {"filtered_ohlcv_bundle": {}}

        # Build symbol sets for each input
        symbol_sets: dict[str, set[str]] = {}
        symbol_maps: dict[str, dict[str, AssetSymbol]] = {}
        input_bundles: dict[str, dict[AssetSymbol, list[OHLCVBar]]] = {}

        for name, bundle in connected_inputs:
            symbols = self._get_symbols_from_input(bundle)
            keys: set[str] = set()
            key_to_symbol: dict[str, AssetSymbol] = {}

            for symbol in symbols:
                k = self._make_key(symbol)
                keys.add(k)
                if k not in key_to_symbol:
                    key_to_symbol[k] = symbol

            symbol_sets[name] = keys
            symbol_maps[name] = key_to_symbol
            input_bundles[name] = bundle

        # Execute operation
        filtered: dict[AssetSymbol, list[OHLCVBar]] = {}

        if operation == "common":
            # Symbols in ALL connected inputs
            if len(connected_inputs) == 0:
                pass
            elif len(connected_inputs) == 1:
                # If only one input, return all symbols from it
                name, bundle = connected_inputs[0]
                filtered = bundle
            else:
                # Intersection of all inputs
                common_keys = symbol_sets[connected_inputs[0][0]]
                for name, _bundle in connected_inputs[1:]:
                    common_keys &= symbol_sets[name]

                # Use first input's bundle for data
                first_name, _first_bundle = connected_inputs[0]
                for k in common_keys:
                    symbol = symbol_maps[first_name][k]
                    # Try to get data from any input that has it
                    for name, bundle in connected_inputs:
                        if symbol in bundle:
                            filtered[symbol] = bundle[symbol]
                            break
                    else:
                        # If no bundle has data, create empty entry
                        filtered[symbol] = []

        elif operation == "unique_to_1" and "ohlcv_bundle_1" in symbol_sets:
            # Symbols only in ohlcv_bundle_1, not in others
            unique_keys = symbol_sets["ohlcv_bundle_1"]
            for name, _bundle in connected_inputs:
                if name != "ohlcv_bundle_1":
                    unique_keys -= symbol_sets[name]

            for k in unique_keys:
                symbol = symbol_maps["ohlcv_bundle_1"][k]
                filtered[symbol] = input_bundles["ohlcv_bundle_1"].get(symbol, [])

        elif operation == "unique_to_2" and "ohlcv_bundle_2" in symbol_sets:
            # Symbols only in ohlcv_bundle_2, not in others
            unique_keys = symbol_sets["ohlcv_bundle_2"]
            for name, _bundle in connected_inputs:
                if name != "ohlcv_bundle_2":
                    unique_keys -= symbol_sets[name]

            for k in unique_keys:
                symbol = symbol_maps["ohlcv_bundle_2"][k]
                filtered[symbol] = input_bundles["ohlcv_bundle_2"].get(symbol, [])

        elif operation == "unique_to_3" and "ohlcv_bundle_3" in symbol_sets:
            # Symbols only in ohlcv_bundle_3, not in others
            unique_keys = symbol_sets["ohlcv_bundle_3"]
            for name, _bundle in connected_inputs:
                if name != "ohlcv_bundle_3":
                    unique_keys -= symbol_sets[name]

            for k in unique_keys:
                symbol = symbol_maps["ohlcv_bundle_3"][k]
                filtered[symbol] = input_bundles["ohlcv_bundle_3"].get(symbol, [])

        elif operation == "all":
            # Union of all symbols from all inputs
            all_keys: set[str] = set()
            for name, _bundle in connected_inputs:
                all_keys |= symbol_sets[name]

            # Build merged result, preferring data from first input that has it
            for k in all_keys:
                symbol: AssetSymbol | None = None
                bundle_data: list[OHLCVBar] = []

                # Find symbol and data from first input that has this key
                for name, bundle in connected_inputs:
                    if k in symbol_maps[name]:
                        symbol = symbol_maps[name][k]
                        if symbol in bundle:
                            bundle_data = bundle[symbol]
                        break

                if symbol:
                    filtered[symbol] = bundle_data

        logger.info(
            f"DuplicateSymbolFilter: Operation '{operation}' returned {len(filtered)} symbols"
        )
        return {"filtered_ohlcv_bundle": filtered}
