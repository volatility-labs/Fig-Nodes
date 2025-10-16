from typing import Dict, Any, List
from nodes.base.base_node import Base


class ForEach(Base):
    """
    Iterates over a list and executes a subgraph for each item.
    This node is special and requires custom handling in the GraphExecutor.
    """
    inputs = {"list": List[Any]}
    outputs = {"item": Any}
    default_params = {}

    def __init__(self, id: int, params: Dict[str, Any] = None):
        super().__init__(id, params)

    async def _execute_impl(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        item_list = inputs.get("list", [])
        return {"item": item_list}


