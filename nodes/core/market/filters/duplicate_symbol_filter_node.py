from typing import Any, Dict

from core.types_registry import AssetClass, AssetSymbol, NodeCategory, OHLCVBar, get_type
from nodes.core.market.filters.base.base_filter_node import BaseFilter


class DuplicateSymbolFilter(BaseFilter):
    """
    Filters an OHLCV bundle to handle duplicate symbols.

    Usage:
    - Connect an OHLCV bundle input.
    - Choose how duplicates are handled (drop duplicates keeping first, or keep only duplicates).
    - Optionally choose the comparison key (ticker vs symbol string) and case sensitivity.

    Inputs:
      - ohlcv_bundle: Dict[AssetSymbol, List[OHLCVBar]]

    Outputs:
      - filtered_ohlcv_bundle: Dict[AssetSymbol, List[OHLCVBar]]
    """

    CATEGORY = NodeCategory.MARKET

    # Inherit inputs/outputs from BaseFilter
    inputs = {"ohlcv_bundle": get_type("OHLCVBundle")}
    outputs = {"filtered_ohlcv_bundle": get_type("OHLCVBundle")}

    default_params = {
        # unique: keep the first occurrence per compare key
        # duplicates_only: keep only entries whose compare key appears > 1
        "mode": "unique",  # "unique" | "duplicates_only"
        # compare by: 'ticker' (base symbol ticker) or 'symbol_string' (str(symbol))
        "compare_by": "ticker",  # "ticker" | "symbol_string"
        "case_insensitive": True,
    }

    params_meta = [
        {
            "name": "mode",
            "type": "combo",
            "default": "unique",
            "options": ["unique", "duplicates_only"],
            "label": "Duplicate Mode",
            "description": "How to handle duplicates: keep first unique or only duplicates",
        },
        {
            "name": "compare_by",
            "type": "combo",
            "default": "ticker",
            "options": ["ticker", "symbol_string"],
            "label": "Compare By",
            "description": "Key used to detect duplicates (ticker ignores quote currency)",
        },
        {
            "name": "case_insensitive",
            "type": "combo",
            "default": True,
            "options": [True, False],
            "label": "Case Insensitive",
            "description": "Compare keys without case sensitivity",
        },
    ]

    def _filter_condition(self, symbol: AssetSymbol, ohlcv_data: list[OHLCVBar]) -> bool:
        # Not used; we override _execute_impl to handle bundle-level logic
        return True

    async def _execute_impl(self, inputs: dict[str, Any]) -> dict[str, Any]:
        bundle: dict[AssetSymbol, list[OHLCVBar]] = inputs.get("ohlcv_bundle", {})
        if not bundle:
            return {"filtered_ohlcv_bundle": {}}

        mode = self.params.get("mode", "unique")
        compare_by = self.params.get("compare_by", "ticker")
        case_insensitive = bool(self.params.get("case_insensitive", True))

        def make_key(sym: AssetSymbol) -> str:
            if compare_by == "symbol_string":
                # Uses __str__ -> may include quote currency
                k = str(sym)
            else:
                # ticker only; ignore quote currency to catch dup variants
                k = sym.ticker
            return k.lower() if case_insensitive else k

        # Build index of compare keys to list of symbols
        key_to_symbols: Dict[str, list[AssetSymbol]] = {}
        for sym in bundle.keys():
            key = make_key(sym)
            key_to_symbols.setdefault(key, []).append(sym)

        filtered: dict[AssetSymbol, list[OHLCVBar]] = {}

        if mode == "duplicates_only":
            for key, syms in key_to_symbols.items():
                if len(syms) > 1:
                    for s in syms:
                        filtered[s] = bundle[s]
        else:  # unique (keep first occurrence only)
            for key, syms in key_to_symbols.items():
                # Keep the first symbol encountered for the key
                first = syms[0]
                filtered[first] = bundle[first]

        return {"filtered_ohlcv_bundle": filtered}


