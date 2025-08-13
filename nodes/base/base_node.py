import typing
from typing import Dict, Any, Type, Optional, get_origin, get_args, List
from core.types_registry import get_type, AssetSymbol, AssetClass

class BaseNode:
    """
    Abstract base class for all graph nodes.
    
    Subclasses must define:
    - inputs: Dict[str, Type] - Expected input types
    - outputs: Dict[str, Type] - Produced output types
    - default_params: Dict[str, Any] - Default parameter values
    - Optional: params_meta - List of dicts for UI parameter config
    - execute(self, inputs: Dict[str, Any]) -> Dict[str, Any]
    
    Optional:
    - required_asset_class: AssetClass - For asset-specific nodes
    - validate_inputs(self, inputs) - Custom validation
    """
    inputs: Dict[str, Type] = {}
    outputs: Dict[str, Type] = {"output": Any}
    default_params: Dict[str, Any] = {}
    required_asset_class: Optional[AssetClass] = None

    def __init__(self, id: str, params: Dict[str, Any] = None):
        self.id = id
        self.params = {**self.default_params, **(params or {})}

    def collect_multi_input(self, key: str, inputs: Dict[str, Any]) -> List[Any]:
        expected_type = self.inputs.get(key)
        if expected_type is None:
            return inputs.get(key, [])
        origin = get_origin(expected_type)
        if origin not in (list, typing.List):
            return inputs.get(key, [])
        
        collected = []
        i = 0
        while True:
            multi_key = f"{key}_{i}"
            if multi_key not in inputs:
                break
            val = inputs[multi_key]
            if val is None:
                i += 1
                continue
            if isinstance(val, list):
                collected.extend(val)
            else:
                collected.append(val)
            i += 1
        
        # Deduplicate
        seen = set()
        unique = []
        for item in collected:
            item_str = str(item)  # Assuming str(item) uniquely identifies
            if item_str not in seen:
                seen.add(item_str)
                unique.append(item)
        
        return unique

    def validate_inputs(self, inputs: Dict[str, Any]) -> bool:
        for key, expected_type in self.inputs.items():
            if key in inputs:
                # Handle as single input
                value = inputs[key]
                origin = get_origin(expected_type)
                if origin is not None:
                    base_type = {
                        typing.List: list,
                        typing.Dict: dict,
                        # Add other typing generics if needed
                    }.get(origin, origin)
                    if not isinstance(value, base_type):
                        raise TypeError(f"Invalid container type for input '{key}' in node {self.id}: expected {base_type}, got {type(value)}")
                    if origin in (typing.List, list) and value:
                        element_type = get_args(expected_type)[0]
                        if element_type is not Any:
                            for item in value:
                                if not isinstance(item, element_type):
                                    raise TypeError(f"Invalid element type in list for input '{key}' in node {self.id}: expected {element_type}, found {type(item)}")
                                if isinstance(item, AssetSymbol) and self.required_asset_class and item.asset_class != self.required_asset_class:
                                    raise ValueError(f"Invalid asset class for item in '{key}' in node {self.id}: expected {self.required_asset_class}, got {item.asset_class}")
                elif expected_type is not Any and not isinstance(value, expected_type):
                    raise TypeError(f"Invalid type for input '{key}' in node {self.id}: expected {expected_type}, got {type(value)}")
                if expected_type == AssetSymbol and self.required_asset_class and value.asset_class != self.required_asset_class:
                    raise ValueError(f"Invalid asset class for '{key}' in node {self.id}: expected {self.required_asset_class}, got {value.asset_class}")
            else:
                # Try multi-input handling
                origin = get_origin(expected_type)
                if origin not in (list, typing.List):
                    if hasattr(self, 'optional_inputs') and key in self.optional_inputs:
                        continue
                    return False
                element_type = get_args(expected_type)[0]
                found = False
                i = 0
                while True:
                    multi_key = f"{key}_{i}"
                    if multi_key not in inputs:
                        break
                    value = inputs[multi_key]
                    if value is None:
                        i += 1
                        continue
                    found = True
                    if isinstance(value, list):
                        for item in value:
                            if element_type is not Any and not isinstance(item, element_type):
                                raise TypeError(f"Invalid element type in list for input '{multi_key}' in node {self.id}: expected {element_type}, got {type(item)}")
                            if isinstance(item, AssetSymbol) and self.required_asset_class and item.asset_class != self.required_asset_class:
                                raise ValueError(f"Invalid asset class for item in '{multi_key}' in node {self.id}: expected {self.required_asset_class}, got {item.asset_class}")
                    else:
                        if element_type is not Any and not isinstance(value, element_type):
                            raise TypeError(f"Invalid type for input '{multi_key}' in node {self.id}: expected {element_type} or list[{element_type}], got {type(value)}")
                        if isinstance(value, AssetSymbol) and self.required_asset_class and value.asset_class != self.required_asset_class:
                            raise ValueError(f"Invalid asset class for '{multi_key}' in node {self.id}: expected {self.required_asset_class}, got {value.asset_class}")
                    i += 1
                if not found:
                    if hasattr(self, 'optional_inputs') and key in self.optional_inputs:
                        continue
                    return False
        return True

    async def execute(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """Core execution method - must be implemented by subclasses."""
        if not self.validate_inputs(inputs):
            raise ValueError(f"Missing or invalid inputs for node {self.id}: {self.inputs}")
        raise NotImplementedError("Subclasses must implement execute()") 