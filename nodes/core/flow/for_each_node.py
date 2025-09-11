from typing import Dict, Any, List
from nodes.base.base_node import BaseNode


class ForEachNode(BaseNode):
    """
    Iterates over a list and executes a subgraph for each item.
    This node is special and requires custom handling in the GraphExecutor.
    """
    inputs = {"list": List[Any]}
    outputs = {"item": Any}
    default_params = {}

    def __init__(self, node_id: str, params: Dict[str, Any]):
        super().__init__(node_id, params)

    async def execute(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        # Validate inputs using BaseNode's validation
        if not self.validate_inputs(inputs):
            return {"list": []}
        item_list = inputs.get("list", [])
        return {"list": item_list}


