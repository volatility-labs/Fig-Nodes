from typing import Dict, Any
from nodes.base.base_node import BaseNode


class SampleCustomNode(BaseNode):
    inputs = {"input_data": Any}
    outputs = {"output_data": Any}

    async def _execute_impl(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        return {"output_data": inputs["input_data"] + "_custom_processed"}


