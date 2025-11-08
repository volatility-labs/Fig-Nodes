from typing import Any, Dict

from core.types_registry import AssetClass, AssetSymbol, NodeCategory, OHLCVBar, get_type
from nodes.core.market.filters.base.base_filter_node import BaseFilter


class DuplicateSymbolFilter(BaseFilter):
    """
    Filters an OHLCV bundle to handle duplicate symbols with support for multi-input operations.

    Usage:
    - Single input: Connect an OHLCV bundle to 'ohlcv_bundle' for standard deduplication.
    - Multi input: Connect up to 3 inputs ('input_1', 'input_2', 'input_3') for set operations.
    - Choose how duplicates are handled (drop duplicates keeping first, or keep only duplicates).
    - Optionally choose the comparison key (ticker vs symbol string) and case sensitivity.

    Inputs:
      - ohlcv_bundle: Dict[AssetSymbol, List[OHLCVBar]] (for single-input mode)
      - input_1: Dict[AssetSymbol, List[OHLCVBar]] (for multi-input operations)
      - input_2: Dict[AssetSymbol, List[OHLCVBar]] (for multi-input operations)
      - input_3: Dict[AssetSymbol, List[OHLCVBar]] (for multi-input operations)

    Outputs:
      - filtered_ohlcv_bundle: Dict[AssetSymbol, List[OHLCVBar]]
    """

    CATEGORY = NodeCategory.MARKET

    # Combined: support classic single-bundle AND optional multi-bundle operations
    # Mark additional inputs as optional by allowing None
    ohlcv_tp = get_type("OHLCVBundle")
    inputs = {
        "ohlcv_bundle": ohlcv_tp | None,
        "input_1": ohlcv_tp | None,
        "input_2": ohlcv_tp | None,
        "input_3": ohlcv_tp | None,
    }
    outputs = {"filtered_ohlcv_bundle": get_type("OHLCVBundle")}

    default_params = {
        # unique: keep the first occurrence per compare key
        # duplicates_only: keep only entries whose compare key appears > 1
        "mode": "unique",  # "unique" | "duplicates_only"
        # compare by: 'ticker' (base symbol ticker) or 'symbol_string' (str(symbol))
        "compare_by": "ticker",  # "ticker" | "symbol_string"
        "case_insensitive": True,
        # Multi-input comparison modes (overrides global mode when active)
        # Options:
        #  - global: use global duplicate logic across all merged inputs (default)
        #  - intersection_1_2: keep only symbols present in both input 1 and input 2
        #  - intersection_1_2_3: keep only symbols present in all three inputs (1, 2, and 3)
        #  - only_1_minus_2: keep symbols present in input 1 but not input 2
        #  - only_2_minus_1: keep symbols present in input 2 but not input 1
        #  - only_3_minus_1_2: keep symbols present in input 3 but not in inputs 1 or 2
        #  - union_1_2_minus_3: keep symbols present in inputs 1 or 2 but not in input 3
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
                "intersection_1_2_3",
                "only_1_minus_2",
                "only_2_minus_1",
                "only_3_minus_1_2",
                "union_1_2_minus_3",
            ],
            "label": "Multi-Input Mode",
            "description": "Apply multi-input filtering operations instead of global dedupe",
        },
    ]

    def _filter_condition(self, symbol: AssetSymbol, ohlcv_data: list[OHLCVBar]) -> bool:
        # Not used; we override _execute_impl to handle bundle-level logic
        return True

    async def _execute_impl(self, inputs: dict[str, Any]) -> dict[str, Any]:
        # Inputs
        single_bundle: dict[AssetSymbol, list[OHLCVBar]] = inputs.get("ohlcv_bundle", {}) or {}
        input_1: dict[AssetSymbol, list[OHLCVBar]] = inputs.get("input_1", {}) or {}
        input_2: dict[AssetSymbol, list[OHLCVBar]] = inputs.get("input_2", {}) or {}
        input_3: dict[AssetSymbol, list[OHLCVBar]] = inputs.get("input_3", {}) or {}
        # Back-compat: accept legacy port names if present (e.g., old graphs wired to left/right)
        # Map left_bundle -> input_1, right_bundle -> input_2, third_bundle -> input_3
        if not input_1:
            legacy_left = inputs.get("left_bundle") or inputs.get("left")
            if legacy_left:
                input_1 = legacy_left or {}
        if not input_2:
            legacy_right = inputs.get("right_bundle") or inputs.get("right")
            if legacy_right:
                input_2 = legacy_right or {}
        if not input_3:
            legacy_third = inputs.get("third_bundle") or inputs.get("bundle_3") or inputs.get("third")
            if legacy_third:
                input_3 = legacy_third or {}
        
        # Debug logging
        print(f"DuplicateSymbolFilter: input_1 has {len(input_1)} symbols")
        print(f"DuplicateSymbolFilter: input_2 has {len(input_2)} symbols")
        print(f"DuplicateSymbolFilter: input_3 has {len(input_3)} symbols")
        print(f"DuplicateSymbolFilter: pair_mode = {self.params.get('pair_mode', 'global')}")

        compare_by = self.params.get("compare_by", "ticker")
        case_insensitive = bool(self.params.get("case_insensitive", True))

        def make_key(sym: AssetSymbol) -> str:
            if compare_by == "symbol_string":
                k = str(sym)
            else:
                k = sym.ticker
            return k.lower() if case_insensitive else k

        # Multi-input operations if any inputs are provided
        pair_mode = str(self.params.get("pair_mode", "global"))
        if (input_1 or input_2 or input_3) and pair_mode != "global":
            # Build key mappings for each input
            keys_1: Dict[str, list[AssetSymbol]] = {}
            keys_2: Dict[str, list[AssetSymbol]] = {}
            keys_3: Dict[str, list[AssetSymbol]] = {}
            
            for s in input_1.keys():
                keys_1.setdefault(make_key(s), []).append(s)
            for s in input_2.keys():
                keys_2.setdefault(make_key(s), []).append(s)
            for s in input_3.keys():
                keys_3.setdefault(make_key(s), []).append(s)

            filtered: dict[AssetSymbol, list[OHLCVBar]] = {}
            
            if pair_mode == "intersection_1_2":
                keys_final = set(keys_1.keys()) & set(keys_2.keys())
                for k in keys_final:
                    if k in keys_1:
                        s = keys_1[k][0]
                        filtered[s] = input_1[s]
                        
            elif pair_mode == "intersection_1_2_3":
                keys_final = set(keys_1.keys()) & set(keys_2.keys()) & set(keys_3.keys())
                print(f"DuplicateSymbolFilter: Found {len(keys_final)} symbols in all 3 inputs: {sorted(keys_final)}")
                for k in keys_final:
                    if k in keys_1:
                        s = keys_1[k][0]
                        filtered[s] = input_1[s]
                        
            elif pair_mode == "only_1_minus_2":
                keys_final = set(keys_1.keys()) - set(keys_2.keys())
                for k in keys_final:
                    if k in keys_1:
                        s = keys_1[k][0]
                        filtered[s] = input_1[s]
                        
            elif pair_mode == "only_2_minus_1":
                keys_final = set(keys_2.keys()) - set(keys_1.keys())
                for k in keys_final:
                    if k in keys_2:
                        s = keys_2[k][0]
                        filtered[s] = input_2[s]
                        
            elif pair_mode == "only_3_minus_1_2":
                keys_final = set(keys_3.keys()) - set(keys_1.keys()) - set(keys_2.keys())
                for k in keys_final:
                    if k in keys_3:
                        s = keys_3[k][0]
                        filtered[s] = input_3[s]
                        
            elif pair_mode == "union_1_2_minus_3":
                keys_union = set(keys_1.keys()) | set(keys_2.keys())
                keys_final = keys_union - set(keys_3.keys())
                for k in keys_final:
                    if k in keys_1:
                        s = keys_1[k][0]
                        filtered[s] = input_1[s]
                    elif k in keys_2:
                        s = keys_2[k][0]
                        filtered[s] = input_2[s]
            else:
                # Fallback to union unique across all inputs
                merged: dict[str, AssetSymbol] = {}
                for s in list(input_1.keys()) + list(input_2.keys()) + list(input_3.keys()):
                    k = make_key(s)
                    if k not in merged:
                        merged[k] = s
                for k, s in merged.items():
                    if s in input_1:
                        filtered[s] = input_1[s]
                    elif s in input_2:
                        filtered[s] = input_2[s]
                    elif s in input_3:
                        filtered[s] = input_3[s]
            print(f"DuplicateSymbolFilter: Returning {len(filtered)} symbols from multi-input mode")
            return {"filtered_ohlcv_bundle": filtered}

        # Otherwise, run global single-bundle duplicate logic
        bundle = single_bundle
        if not bundle:
            return {"filtered_ohlcv_bundle": {}}

        mode = self.params.get("mode", "unique")
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
        else:  # unique
            for key, syms in key_to_symbols.items():
                first = syms[0]
                filtered[first] = bundle[first]

        return {"filtered_ohlcv_bundle": filtered}


