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

    # Combined: support classic single-bundle AND optional pairwise bundles
    # Mark additional inputs as optional by allowing None
    ohlcv_tp = get_type("OHLCVBundle")
    inputs = {
        "ohlcv_bundle": ohlcv_tp | None,
        "left_bundle": ohlcv_tp | None,
        "right_bundle": ohlcv_tp | None,
        # New optional third input for 3-way set operations
        "third_bundle": ohlcv_tp | None,
        # Numbered ports for compatibility with alternate UI/graphs
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
        # Comparison modes for multi-input workflows (overrides global mode when active)
        # Options:
        #  - global: use global duplicate logic across a single bundle (default)
        #  - intersection_1_2: keep only symbols present in both left and right
        #  - intersection_1_2_3: keep only symbols present in left, right, and third
        #  - left_only_1_minus_2: keep symbols present in left but not right
        #  - right_only_2_minus_1: keep symbols present in right but not left
        #  - only_3_minus_1_2: keep symbols present in third but not in left or right
        #  - union_1_2_minus_3: keep symbols present in left or right but not in third
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
                "left_only_1_minus_2",
                "right_only_2_minus_1",
                "only_3_minus_1_2",
                "union_1_2_minus_3",
            ],
            "label": "Multi-Input Mode",
            "description": "Apply multi-input set operations across left/right/third instead of global dedupe",
        },
    ]

    def _filter_condition(self, symbol: AssetSymbol, ohlcv_data: list[OHLCVBar]) -> bool:
        # Not used; we override _execute_impl to handle bundle-level logic
        return True

    async def _execute_impl(self, inputs: dict[str, Any]) -> dict[str, Any]:
        # Inputs
        single_bundle: dict[AssetSymbol, list[OHLCVBar]] = inputs.get("ohlcv_bundle", {}) or {}
        left: dict[AssetSymbol, list[OHLCVBar]] = inputs.get("left_bundle", {}) or {}
        right: dict[AssetSymbol, list[OHLCVBar]] = inputs.get("right_bundle", {}) or {}
        third: dict[AssetSymbol, list[OHLCVBar]] = inputs.get("third_bundle", {}) or {}
        # Also accept numbered ports and merge if provided
        n1: dict[AssetSymbol, list[OHLCVBar]] = inputs.get("input_1", {}) or {}
        n2: dict[AssetSymbol, list[OHLCVBar]] = inputs.get("input_2", {}) or {}
        n3: dict[AssetSymbol, list[OHLCVBar]] = inputs.get("input_3", {}) or {}
        if n1:
            tmp = dict(left)
            tmp.update(n1)
            left = tmp
        if n2:
            tmp = dict(right)
            tmp.update(n2)
            right = tmp
        if n3:
            tmp = dict(third)
            tmp.update(n3)
            third = tmp

        compare_by = self.params.get("compare_by", "ticker")
        case_insensitive = bool(self.params.get("case_insensitive", True))

        def make_key(sym: AssetSymbol) -> str:
            if compare_by == "symbol_string":
                k = str(sym)
            else:
                k = sym.ticker
            return k.lower() if case_insensitive else k

        # Pairwise / Multi-input if any provided and not in global mode
        pair_mode = str(self.params.get("pair_mode", "global"))
        if (left or right or third) and pair_mode != "global":
            # Debug: show input sizes (after merging numbered ports)
            print(f"DuplicateSymbolFilter: left={len(left)}, right={len(right)}, third={len(third)}, pair_mode={pair_mode}")
            left_keys: Dict[str, list[AssetSymbol]] = {}
            right_keys: Dict[str, list[AssetSymbol]] = {}
            third_keys: Dict[str, list[AssetSymbol]] = {}
            for s in left.keys():
                left_keys.setdefault(make_key(s), []).append(s)
            for s in right.keys():
                right_keys.setdefault(make_key(s), []).append(s)
            for s in third.keys():
                third_keys.setdefault(make_key(s), []).append(s)

            filtered: dict[AssetSymbol, list[OHLCVBar]] = {}
            if pair_mode == "intersection_1_2":
                keys_final = set(left_keys.keys()) & set(right_keys.keys())
                for k in keys_final:
                    s_left = left_keys[k][0]
                    filtered[s_left] = left[s_left]
                print(f"DuplicateSymbolFilter: intersection_1_2 -> {len(filtered)} symbols")
            elif pair_mode == "intersection_1_2_3":
                keys_final = set(left_keys.keys()) & set(right_keys.keys()) & set(third_keys.keys())
                for k in keys_final:
                    s_left = left_keys[k][0]
                    filtered[s_left] = left[s_left]
                print(f"DuplicateSymbolFilter: intersection_1_2_3 -> {len(filtered)} symbols")
            elif pair_mode == "left_only_1_minus_2":
                keys_final = set(left_keys.keys()) - set(right_keys.keys())
                for k in keys_final:
                    s_left = left_keys[k][0]
                    filtered[s_left] = left[s_left]
            elif pair_mode == "right_only_2_minus_1":
                keys_final = set(right_keys.keys()) - set(left_keys.keys())
                for k in keys_final:
                    s_right = right_keys[k][0]
                    filtered[s_right] = right[s_right]
            elif pair_mode == "only_3_minus_1_2":
                keys_final = set(third_keys.keys()) - set(left_keys.keys()) - set(right_keys.keys())
                for k in keys_final:
                    s_third = third_keys[k][0]
                    filtered[s_third] = third[s_third]
            elif pair_mode == "union_1_2_minus_3":
                keys_union = set(left_keys.keys()) | set(right_keys.keys())
                keys_final = keys_union - set(third_keys.keys())
                for k in keys_final:
                    if k in left_keys:
                        s_left = left_keys[k][0]
                        filtered[s_left] = left[s_left]
                    elif k in right_keys:
                        s_right = right_keys[k][0]
                        filtered[s_right] = right[s_right]
            else:
                # Fallback to union unique across left/right/third
                merged: dict[str, AssetSymbol] = {}
                for s in list(left.keys()) + list(right.keys()) + list(third.keys()):
                    k = make_key(s)
                    if k not in merged:
                        merged[k] = s
                for k, s in merged.items():
                    if s in left:
                        filtered[s] = left[s]
                    elif s in right:
                        filtered[s] = right[s]
                    elif s in third:
                        filtered[s] = third[s]
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


