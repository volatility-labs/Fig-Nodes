from typing import Dict, Any, Type, Optional
from core.types_registry import get_type, AssetSymbol, AssetClass

class BaseNode:
    inputs: Dict[str, Type] = {}
    outputs: Dict[str, Type] = {"output": Any}
    default_params: Dict[str, Any] = {}
    required_asset_class: Optional[AssetClass] = None

    def __init__(self, id: str, params: Dict[str, Any] = None):
        self.id = id
        self.params = {**self.default_params, **(params or {})}

    def validate_inputs(self, inputs: Dict[str, Any]) -> bool:
        for key, expected_type in self.inputs.items():
            if key not in inputs:
                return False
            value = inputs[key]
            if expected_type is not Any and not isinstance(value, expected_type):
                raise TypeError(f"Invalid type for input '{key}' in node {self.id}: expected {expected_type}, got {type(value)}")
            if expected_type == AssetSymbol and self.required_asset_class and value.asset_class != self.required_asset_class:
                raise ValueError(f"Invalid asset class for '{key}' in node {self.id}: expected {self.required_asset_class}, got {value.asset_class}")
        return True

    async def execute(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        if not self.validate_inputs(inputs):
            raise ValueError(f"Missing or invalid inputs for node {self.id}: {self.inputs}")
        raise NotImplementedError("Subclasses must implement execute()") 