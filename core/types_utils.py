import types
import typing
from typing import Any, TypeGuard

from core.types_registry import (
    AssetSymbol,
    IndicatorResult,
    IndicatorValue,
)


def _is_dict(value: Any) -> TypeGuard[dict[str, Any]]:
    """Type guard to check if value is a dict[str, Any]."""
    return isinstance(value, dict)


def parse_type(type_hint: Any) -> dict[str, Any]:
    """
    Parse a Python type hint into a structured dictionary representation.

    Args:
        type_hint: The type hint to parse (e.g., int, List[str], Dict[str, int])

    Returns:
        Dictionary with 'base' key and optional 'subtypes', 'key_type', 'value_type'
    """
    origin = typing.get_origin(type_hint)

    if origin is None:
        # Simple types (int, str, float, etc.)
        name = getattr(type_hint, "__name__", str(type_hint))

        if name == "Any" or name.endswith(".Any"):
            return {"base": "Any"}
        elif type_hint in (list, set, tuple):
            return {"base": name, "subtypes": [{"base": "Any"}]}
        elif type_hint is dict:
            return {"base": name, "key_type": {"base": "Any"}, "value_type": {"base": "Any"}}
        else:
            return {"base": name}

    # Complex types (List[str], Dict[str, int], Union[int, str], etc.)
    args = typing.get_args(type_hint)

    # Determine base name
    if origin is typing.Union or origin is types.UnionType:
        base = "union"
    else:
        base = getattr(type_hint, "_name", None) or getattr(origin, "__name__", str(origin))

    # Handle different origin types
    if origin in (list, set, tuple):
        subtypes = [parse_type(arg) for arg in args]
        return {"base": base, "subtypes": subtypes}

    elif origin is dict:
        key_type = parse_type(args[0]) if args else None
        value_type = parse_type(args[1]) if len(args) > 1 else None
        return {"base": base, "key_type": key_type, "value_type": value_type}

    elif origin is typing.Union or origin is types.UnionType:
        # Normalize Optional types: Union[T, None] or Union[T, NoneType] -> T
        # Filter out None/NoneType from the union
        filtered_args = [arg for arg in args if arg is not type(None)]

        # If all args were None, return NoneType
        if not filtered_args:
            return {"base": "NoneType"}

        # If only one non-None type remains, return that type directly
        if len(filtered_args) == 1:
            return parse_type(filtered_args[0])

        # Otherwise, return union of non-None types
        subtypes = [parse_type(arg) for arg in filtered_args]
        return {"base": "union", "subtypes": subtypes}

    else:
        # Generic types with type parameters
        subtypes = [parse_type(arg) for arg in args]
        return {"base": base, "subtypes": subtypes}


def detect_type(value: Any) -> str:
    """
    Detect the type of a value and return a canonical type name.

    Args:
        value: The value to detect the type of

    Returns:
        Canonical type name string (e.g., "OHLCVBar", "AssetSymbol", "list", "dict")
    """
    if value is None:
        return "None"

    # AssetSymbol dataclass
    if isinstance(value, AssetSymbol):
        return "AssetSymbol"

    # IndicatorValue dataclass
    if isinstance(value, IndicatorValue):
        return "IndicatorValue"

    # IndicatorResult dataclass
    if isinstance(value, IndicatorResult):
        return "IndicatorResult"

    # OHLCVBar - TypedDict with required keys
    if isinstance(value, dict) and all(
        key in value for key in {"timestamp", "open", "high", "low", "close", "volume"}
    ):
        return "OHLCVBar"

    # LLMChatMessage - has role and content
    if isinstance(value, dict) and "role" in value and "content" in value:
        return "LLMChatMessage"

    # LLMToolSpec - type="function" and has function field
    if _is_dict(value) and value.get("type", None) == "function" and "function" in value:
        return "LLMToolSpec"

    # LLMChatMetrics - has metric keys
    if isinstance(value, dict) and any(
        key in value
        for key in {
            "total_duration",
            "load_duration",
            "prompt_eval_count",
            "prompt_eval_duration",
            "eval_count",
            "eval_duration",
            "error",
        }
    ):
        return "LLMChatMetrics"

    # LLMToolHistoryItem - has call and result
    if isinstance(value, dict) and "call" in value and "result" in value:
        return "LLMToolHistoryItem"

    # LLMThinkingHistoryItem - has thinking and iteration
    if isinstance(value, dict) and "thinking" in value and "iteration" in value:
        return "LLMThinkingHistoryItem"

    # Built-in types
    if isinstance(value, bool):
        return "bool"
    if isinstance(value, int):
        return "int"
    if isinstance(value, float):
        return "float"
    if isinstance(value, str):
        return "str"
    if isinstance(value, list):
        return "list"
    if isinstance(value, dict):
        return "dict"
    if isinstance(value, set):
        return "set"
    if isinstance(value, tuple):
        return "tuple"

    return type(value).__name__


def infer_data_type(data: Any) -> str:
    """
    Infer a high-level data type name for metadata purposes.

    Returns semantic names for common patterns (e.g., "OHLCV", "AssetSymbolList", "OHLCVBundle")
    """
    if data is None:
        return "None"

    if isinstance(data, AssetSymbol):
        return "AssetSymbol"

    if isinstance(data, IndicatorValue):
        return "IndicatorValue"

    if isinstance(data, IndicatorResult):
        return "IndicatorResult"

    if isinstance(data, list):
        if not data:
            return "EmptyList"

        item_type = detect_type(data[0])

        if item_type == "AssetSymbol":
            return "AssetSymbolList"
        if item_type == "OHLCVBar":
            return "OHLCV"
        if item_type == "LLMChatMessage":
            return "LLMChatMessageList"
        if item_type == "IndicatorResult":
            return "IndicatorResultList"

        return f"List[{item_type}]"

    if not _is_dict(data):
        # Check if it's a registered TypedDict type
        detected = detect_type(data)
        if detected in {
            "OHLCVBar",
            "LLMChatMessage",
            "LLMToolSpec",
            "LLMChatMetrics",
            "LLMToolHistoryItem",
            "LLMThinkingHistoryItem",
            "IndicatorValue",
            "IndicatorResult",
        }:
            return detected
        return detected

    if not data:
        return "EmptyDict"

    first_key: Any = next(iter(data.keys()))
    first_value: Any = next(iter(data.values()))

    # OHLCVBundle: dict[AssetSymbol, list[OHLCVBar]]
    if isinstance(first_key, AssetSymbol) and isinstance(first_value, list):
        if first_value and detect_type(first_value[0]) == "OHLCVBar":
            return "OHLCVBundle"

    return f"Dict[{detect_type(first_key)}, {detect_type(first_value)}]"
