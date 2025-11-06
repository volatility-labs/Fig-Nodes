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

    # Support up to 3 OHLCV bundles as inputs to merge different feeds
    inputs = {
        "ohlcv_bundle_1": get_type("OHLCVBundle"),
        "ohlcv_bundle_2": get_type("OHLCVBundle"),
        "ohlcv_bundle_3": get_type("OHLCVBundle"),
    }
    outputs = {"filtered_ohlcv_bundle": get_type("OHLCVBundle")}

    default_params = {
        # unique: keep the first occurrence per compare key
        # duplicates_only: keep only entries whose compare key appears > 1
        "mode": "unique",  # "unique" | "duplicates_only"
        # compare by: 'ticker' (base symbol ticker) or 'symbol_string' (str(symbol))
        "compare_by": "ticker",  # "ticker" | "symbol_string"
        "case_insensitive": True,
        # Pairwise comparison for two-input workflows (overrides global mode when active)
        # Options:
        #  - global: use global duplicate logic across all merged inputs (default)
        #  - intersection_1_2: keep only symbols present in both input 1 and input 2
        #  - left_only_1_minus_2: keep symbols present in input 1 but not input 2
        #  - right_only_2_minus_1: keep symbols present in input 2 but not input 1
        "pair_mode": "global",
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
        {
            "name": "pair_mode",
            "type": "combo",
            "default": "global",
            "options": [
                "global",
                "intersection_1_2",
                "left_only_1_minus_2",
                "right_only_2_minus_1",
            ],
            "label": "Two-Input Mode",
            "description": "Apply pairwise filtering between inputs 1 and 2 instead of global dedupe",
        },
    ]

    def _filter_condition(self, symbol: AssetSymbol, ohlcv_data: list[OHLCVBar]) -> bool:
        # Not used; we override _execute_impl to handle bundle-level logic
        return True

    async def _execute_impl(self, inputs: dict[str, Any]) -> dict[str, Any]:
        # Grab individual bundles
        b1: dict[AssetSymbol, list[OHLCVBar]] = inputs.get("ohlcv_bundle_1", {}) or {}
        b2: dict[AssetSymbol, list[OHLCVBar]] = inputs.get("ohlcv_bundle_2", {}) or {}
        b3: dict[AssetSymbol, list[OHLCVBar]] = inputs.get("ohlcv_bundle_3", {}) or {}
        # Combined view for global logic
        bundle: dict[AssetSymbol, list[OHLCVBar]] = {}
        for b in (b1, b2, b3):
            if isinstance(b, dict):
                bundle.update(b)
        if not bundle and not (b1 or b2 or b3):
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

        # Optional pairwise mode between inputs 1 and 2
        pair_mode = str(self.params.get("pair_mode", "global"))
        if pair_mode != "global" and (b1 or b2):
            # Build key sets per input
            keys1 = {make_key(sym) for sym in b1.keys()}
            keys2 = {make_key(sym) for sym in b2.keys()}

            if pair_mode == "intersection_1_2":
                keys_final = keys1 & keys2
                source = {}
                source.update(b1)
                source.update(b2)
                filtered = {s: source[s] for s in source.keys() if make_key(s) in keys_final}
                return {"filtered_ohlcv_bundle": filtered}

            if pair_mode == "left_only_1_minus_2":
                keys_final = keys1 - keys2
                filtered = {s: b1[s] for s in b1.keys() if make_key(s) in keys_final}
                return {"filtered_ohlcv_bundle": filtered}

            if pair_mode == "right_only_2_minus_1":
                keys_final = keys2 - keys1
                filtered = {s: b2[s] for s in b2.keys() if make_key(s) in keys_final}
                return {"filtered_ohlcv_bundle": filtered}

        # Global (merged) duplicate logic
        key_to_symbols: Dict[str, list[AssetSymbol]] = {}
        for sym in bundle.keys():
            key = make_key(sym)
            key_to_symbols.setdefault(key, []).append(sym)

        filtered: dict[AssetSymbol, list[OHLCVBar]] = {}

        if mode == "duplicates_only":
            for key, syms in key_to_symbols.items():
                # keep all symbols whose compare key appears more than once ANYWHERE (across merged inputs)
                if len(syms) > 1:
                    for s in syms:
                        filtered[s] = bundle[s]
        else:  # unique (keep first occurrence only globally)
            for key, syms in key_to_symbols.items():
                first = syms[0]
                filtered[first] = bundle[first]

        return {"filtered_ohlcv_bundle": filtered}


