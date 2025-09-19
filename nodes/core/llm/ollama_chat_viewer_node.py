from typing import Dict, Any
from nodes.base.base_node import BaseNode
from core.types_registry import get_type


class OllamaChatViewerNode(BaseNode):
    """
    UI sink node to display chat outputs from OllamaChatNode.
    Accepts message (LLMChatMessage) and renders content.
    """

    inputs = {"message": get_type("LLMChatMessage")}
    optional_inputs = ["message"]
    outputs = {"output": str}
    default_params = {}

    ui_module = "OllamaChatViewerNodeUI"

    async def execute(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        msg = inputs.get("message")
        if isinstance(msg, dict) and isinstance(msg.get("content"), str):
            return {"output": msg["content"]}
        return {"output": ""}


