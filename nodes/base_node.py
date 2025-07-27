from typing import Dict, Any, List

class BaseNode:
    def __init__(self, id: str, params: Dict[str, Any] = None):
        self.id = id
        self.params = params or {}

    @property
    def inputs(self) -> List[str]:
        return []

    @property
    def outputs(self) -> List[str]:
        return ['output']

    def validate_inputs(self, inputs: Dict[str, Any]) -> bool:
        return all(key in inputs for key in self.inputs)

    def execute(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        if not self.validate_inputs(inputs):
            raise ValueError(f"Missing inputs for node {self.id}: {self.inputs}")
        raise NotImplementedError("Subclasses must implement execute()") 