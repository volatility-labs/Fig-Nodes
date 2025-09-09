from typing import Dict, Any
from nodes.base.base_node import BaseNode
from core.types_registry import get_type


class OllamaChatViewerNode(BaseNode):
    """
    UI sink node to display chat outputs from OllamaChatNode.
    Accepts either streaming deltas or a final assistant_message.
    """

    inputs = {"delta": str, "assistant_message": get_type("LLMChatMessage")}
    optional_inputs = ["delta", "assistant_message"]
    outputs = {"output": str}
    default_params = {}

    ui_module = "OllamaChatViewerNodeUI"

    async def execute(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        msg = inputs.get("assistant_message")
        delta = inputs.get("delta")
        if isinstance(msg, dict) and isinstance(msg.get("content"), str):
            return {"output": msg["content"]}
        if isinstance(delta, str):
            return {"output": delta}
        return {"output": ""}


