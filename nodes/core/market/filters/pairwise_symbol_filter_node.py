from typing import Any, Dict

from core.types_registry import AssetSymbol, NodeCategory, OHLCVBar, get_type
from nodes.base.base_node import Base


class PairwiseSymbolFilter(Base):
    """
    Pairwise symbol filter for two OHLCV bundles (left and right).

    Supports set operations on symbol keys:
      - intersection: keep symbols present in both inputs
      - left_minus_right: keep symbols present in left but not right
      - right_minus_left: keep symbols present in right but not left
      - union_unique: merge both, keeping first occurrence per compare key

    compare_by options:
      - ticker: use AssetSymbol.ticker (base) for comparison
      - symbol_string: use str(AssetSymbol) (may include quote)
      - base_ticker: try to normalize by stripping known quote suffixes if quote not present
    """

    CATEGORY = NodeCategory.MARKET

    inputs = {
        "left_bundle": get_type("OHLCVBundle"),
        "right_bundle": get_type("OHLCVBundle"),
    }
    outputs = {"ohlcv_bundle": get_type("OHLCVBundle")}

    default_params = {
        "operation": "intersection",  # intersection | left_minus_right | right_minus_left | union_unique
        "compare_by": "base_ticker",  # ticker | symbol_string | base_ticker
        "case_insensitive": True,
    }

    params_meta = [
        {
            "name": "operation",
            "type": "combo",
            "default": "intersection",
            "options": ["intersection", "left_minus_right", "right_minus_left", "union_unique"],
            "label": "Operation",
        },
        {
            "name": "compare_by",
            "type": "combo",
            "default": "base_ticker",
            "options": ["ticker", "symbol_string", "base_ticker"],
            "label": "Compare By",
        },
        {
            "name": "case_insensitive",
            "type": "combo",
            "default": True,
            "options": [True, False],
            "label": "Case Insensitive",
        },
    ]

    def _make_key(self, sym: AssetSymbol, compare_by: str, case_insensitive: bool) -> str:
        if compare_by == "symbol_string":
            k = str(sym)
        elif compare_by == "ticker":
            k = sym.ticker
        else:  # base_ticker
            # Prefer explicit base ticker
            base = sym.ticker
            if base:
                k = base
            else:
                # Fallback: strip known quote suffixes from str(sym)
                s = str(sym)
                known = ("USDT", "USDC", "USD", "EUR", "AUD", "BTC", "ETH")
                k = s
                for q in known:
                    if s.endswith(q):
                        k = s[: -len(q)]
                        break
        return k.lower() if case_insensitive else k

    async def _execute_impl(self, inputs: dict[str, Any]) -> dict[str, Any]:
        left: dict[AssetSymbol, list[OHLCVBar]] = inputs.get("left_bundle", {}) or {}
        right: dict[AssetSymbol, list[OHLCVBar]] = inputs.get("right_bundle", {}) or {}

        if not left and not right:
            return {"ohlcv_bundle": {}}

        operation = str(self.params.get("operation", "intersection"))
        compare_by = str(self.params.get("compare_by", "base_ticker"))
        case_insensitive = bool(self.params.get("case_insensitive", True))

        # Build key maps
        left_keys: Dict[str, list[AssetSymbol]] = {}
        right_keys: Dict[str, list[AssetSymbol]] = {}

        for s in left.keys():
            k = self._make_key(s, compare_by, case_insensitive)
            left_keys.setdefault(k, []).append(s)
        for s in right.keys():
            k = self._make_key(s, compare_by, case_insensitive)
            right_keys.setdefault(k, []).append(s)

        result: dict[AssetSymbol, list[OHLCVBar]] = {}

        if operation == "intersection":
            keys_final = set(left_keys.keys()) & set(right_keys.keys())
            # Prefer symbols from left, then fill from right for any missing compare keys
            for k in keys_final:
                s_left = left_keys[k][0]
                result[s_left] = left[s_left]
        elif operation == "left_minus_right":
            keys_final = set(left_keys.keys()) - set(right_keys.keys())
            for k in keys_final:
                s_left = left_keys[k][0]
                result[s_left] = left[s_left]
        elif operation == "right_minus_left":
            keys_final = set(right_keys.keys()) - set(left_keys.keys())
            for k in keys_final:
                s_right = right_keys[k][0]
                result[s_right] = right[s_right]
        else:  # union_unique
            merged: dict[str, AssetSymbol] = {}
            for s in list(left.keys()) + list(right.keys()):
                k = self._make_key(s, compare_by, case_insensitive)
                if k not in merged:
                    merged[k] = s
            # Use left first preference when both present
            for k, s in merged.items():
                if s in left:
                    result[s] = left[s]
                elif s in right:
                    result[s] = right[s]

        return {"ohlcv_bundle": result}


