from typing import Dict, Any
from nodes.base.base_node import BaseNode
from core.types_registry import get_type


class OllamaChatViewerNode(BaseNode):
    """
    UI sink node to display chat outputs from OllamaChatNode.
    Accepts progressive assistant_text or a final assistant_message.
    """

    inputs = {"assistant_text": str, "assistant_message": get_type("LLMChatMessage")}
    optional_inputs = ["assistant_text", "assistant_message"]
    outputs = {"output": str}
    default_params = {}

    ui_module = "OllamaChatViewerNodeUI"

    async def execute(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        msg = inputs.get("assistant_message")
        text = inputs.get("assistant_text")
        if isinstance(msg, dict) and isinstance(msg.get("content"), str):
            return {"output": msg["content"]}
        if isinstance(text, str):
            return {"output": text}
        return {"output": ""}


