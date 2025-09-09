from typing import Dict, Any
from nodes.base.base_node import BaseNode


class TextInputNode(BaseNode):
    """Simple node that outputs a static text value from parameters."""
    inputs = {}
    outputs = {"text": str}
    default_params = {"value": ""}
    params_meta = [
        {"name": "value", "type": "textarea", "default": ""}
    ]

    async def execute(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        return {"text": self.params.get("value")}


