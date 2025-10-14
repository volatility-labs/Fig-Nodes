from typing import Dict, Any
from nodes.base.base_node import BaseNode


class TextInputNode(BaseNode):
    """Simple node that outputs a static text value from parameters."""
    inputs = {}
    outputs = {"text": str}
    # Support both legacy "value" and preferred "text" parameter keys
    default_params = {"value": "", "text": None}
    params_meta = [
        {"name": "value", "type": "textarea", "default": ""}
    ]

    async def _execute_impl(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        # Prefer explicit "text" param if provided; fall back to legacy "value"
        value = self.params.get("text")
        if value is None or (isinstance(value, str) and value == ""):
            value = self.params.get("value", "")
        return {"text": value}


