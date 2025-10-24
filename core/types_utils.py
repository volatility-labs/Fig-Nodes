import typing
from typing import Any


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
    if origin is typing.Union:
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

    elif origin is typing.Union:
        subtypes = [parse_type(arg) for arg in args]
        return {"base": "union", "subtypes": subtypes}

    else:
        # Generic types with type parameters
        subtypes = [parse_type(arg) for arg in args]
        return {"base": base, "subtypes": subtypes}
