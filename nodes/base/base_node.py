from typing import Dict, Any, Type, Optional, get_origin, get_args
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

    def validate_inputs(self, inputs: Dict[str, Any]) -> bool:
        """
        Validates that provided inputs match expected types and requirements.
        
        Raises:
            TypeError: If types don't match
            ValueError: If required inputs missing or invalid asset class
        """
        for key, expected_type in self.inputs.items():
            if key not in inputs:
                if hasattr(self, 'optional_inputs') and key in self.optional_inputs:
                    continue
                return False

            value = inputs[key]
            origin = get_origin(expected_type)

            if origin is not None:  # Generic type like List[T]
                if not isinstance(value, origin):
                    raise TypeError(f"Invalid container type for input '{key}' in node {self.id}: expected {origin}, got {type(value)}")
                
                if origin is list and value:  # It's a list, check elements
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
        return True

    async def execute(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """Core execution method - must be implemented by subclasses."""
        if not self.validate_inputs(inputs):
            raise ValueError(f"Missing or invalid inputs for node {self.id}: {self.inputs}")
        raise NotImplementedError("Subclasses must implement execute()") 