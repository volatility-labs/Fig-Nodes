from typing import Dict, Any, List
from .base_node import BaseNode

# TODO: Implement flow control nodes 

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
        # This node's logic is primarily handled by the GraphExecutor.
        # It just passes the list through.
        item_list = inputs.get("list", [])
        return {"list": item_list} 