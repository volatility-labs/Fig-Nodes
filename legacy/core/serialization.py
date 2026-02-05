from __future__ import annotations

from typing import Any, Dict, List, Union, cast
import logging

logger = logging.getLogger(__name__)

# Type definitions for serialized values
SerializedScalar = str
SerializedValue = Union[
    SerializedScalar,
    Dict[str, "SerializedValue"],
    List["SerializedValue"],
    List[Dict[str, "SerializedValue"]],
]

# Type aliases for input/output
ExecutionResults = Dict[int, Dict[str, Any]]
SerializedResults = Dict[str, Dict[str, SerializedValue]]


def _is_dataframe(v: Any) -> bool:
    """Check if value is a pandas DataFrame (lazy import to avoid hard dependency)."""
    try:
        import pandas as pd  # type: ignore
        return isinstance(v, pd.DataFrame)
    except Exception:
        return False


def serialize_value(v: Any) -> SerializedValue:
    """
    Serialize a value to a JSON-safe format.
    
    Handles:
    - Primitives (str, int, float, bool) -> str
    - Lists -> recursive serialization
    - Dicts -> recursive serialization with string keys
    - DataFrames -> list of dicts
    - Custom dataclasses -> via to_dict() method
    - Enum -> name/value
    
    Args:
        v: Value to serialize
        
    Returns:
        Serialized value (JSON-safe)
    """
    # Handle None
    if v is None:
        return "None"
    
    # Handle lists
    if isinstance(v, list):
        return [serialize_value(item) for item in cast(List[Any], v)]
    
    # Handle dicts
    if isinstance(v, dict):
        return {str(key): serialize_value(val) for key, val in cast(Dict[Any, Any], v).items()}
    
    # Handle DataFrames
    if _is_dataframe(v):
        records_raw = v.to_dict(orient="records") 
        return [{str(k): serialize_value(val) for k, val in row.items()} for row in records_raw]
    
    # Handle custom dataclasses with to_dict() method
    if hasattr(v, "to_dict") and callable(getattr(v, "to_dict")):
        try:
            d = cast(Dict[str, Any], v.to_dict())
            return {str(k): serialize_value(val) for k, val in d.items()}
        except Exception as e:
            logger.warning(f"Failed to serialize {type(v).__name__} via to_dict(): {e}")
            return str(v)
    
    # Handle dataclasses via asdict
    try:
        from dataclasses import is_dataclass, asdict  # noqa: WPS433
        if is_dataclass(v) and not isinstance(v, type):  # Check it's an instance, not a class
            d = asdict(v)
            return {str(k): serialize_value(val) for k, val in d.items()}
    except Exception:
        pass
    
    # Handle enums
    try:
        from enum import Enum
        if isinstance(v, Enum):
            return v.name if hasattr(v, 'name') else str(v.value)
    except Exception:
        pass
    
    # Handle primitives
    if isinstance(v, (str, int, float, bool)):
        return str(v)
    
    # Fallback for unhandled types
    logger.warning(f"Fallback to str() for unhandled type: {type(v).__name__}")
    return str(v)


def serialize_results(results: ExecutionResults) -> SerializedResults:
    """
    Serialize graph execution results for WebSocket transmission.
    
    Converts node IDs from integers to strings and recursively serializes
    all output values to ensure they can be JSON-encoded.
    
    Args:
        results: Dictionary mapping node IDs to their output dictionaries
        
    Returns:
        Dictionary with string node IDs and serialized output values
    """
    serialized_results: Dict[str, Dict[str, SerializedValue]] = {}
    
    for node_id, node_res in results.items():
        # Convert node ID to string for JSON compatibility
        node_id_str = str(node_id)
        
        # Serialize each output from this node
        serialized_outputs = {}
        for output_name, output_value in node_res.items():
            serialized_outputs[output_name] = serialize_value(output_value)
        
        serialized_results[node_id_str] = serialized_outputs
    
    return serialized_results

