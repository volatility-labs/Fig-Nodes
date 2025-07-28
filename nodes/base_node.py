from typing import Dict, Any, Type

class BaseNode:
    inputs: Dict[str, Type] = {}
    outputs: Dict[str, Type] = {"output": Any}
    default_params: Dict[str, Any] = {}

    def __init__(self, id: str, params: Dict[str, Any] = None):
        self.id = id
        self.params = {**self.default_params, **(params or {})}

    def validate_inputs(self, inputs: Dict[str, Any]) -> bool:
        for key, expected_type in self.inputs.items():
            if key not in inputs:
                return False
            if not isinstance(inputs[key], expected_type):
                raise TypeError(f"Invalid type for input '{key}' in node {self.id}: expected {expected_type}, got {type(inputs[key])}")
        return True

    async def execute(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        if not self.validate_inputs(inputs):
            raise ValueError(f"Missing inputs for node {self.id}: {self.inputs}")
        raise NotImplementedError("Subclasses must implement execute()") 