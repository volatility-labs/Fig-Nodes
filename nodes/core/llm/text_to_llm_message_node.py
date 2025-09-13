from typing import Dict, Any

from nodes.base.base_node import BaseNode
from core.types_registry import get_type


class TextToLLMMessageNode(BaseNode):
    """
    Adapter node: wraps a plain text string into an LLMChatMessage and LLMChatMessageList.

    Inputs:
    - text: str (required)

    Params:
    - role: str in {"user", "assistant", "system", "tool"}

    Outputs:
    - message: LLMChatMessage
    - messages: LLMChatMessageList (single-element list)
    """

    inputs = {
        "text": str,
    }

    outputs = {
        "message": get_type("LLMChatMessage"),
        "messages": get_type("LLMChatMessageList"),
    }

    default_params = {
        "role": "user",
    }

    params_meta = [
        {"name": "role", "type": "combo", "default": "user", "options": ["user", "assistant", "system", "tool"]},
    ]

    CATEGORY = "llm"

    async def execute(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        text = inputs.get("text")
        role = (self.params.get("role") or "user").lower()
        if role not in {"user", "assistant", "system", "tool"}:
            role = "user"

        # Coerce non-string into string for safety
        if not isinstance(text, str):
            text = "" if text is None else str(text)

        msg = {"role": role, "content": text}
        return {
            "message": msg,
            "messages": [msg],
        }


