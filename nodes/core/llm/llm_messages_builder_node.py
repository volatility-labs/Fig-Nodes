from typing import Dict, Any, List, Optional

from nodes.base.base_node import BaseNode
from core.types_registry import get_type


class LLMMessagesBuilderNode(BaseNode):
    """
    Builds a well-formed LLMChatMessageList by combining prior history, optional
    system text, and multiple message inputs (user/assistant/tool) and an
    optional prompt string.

    Inputs:
    - base: LLMChatMessageList (optional) – prior conversation history
    - system_text: str (optional) – system prompt content
    - user: LLMChatMessageList (multi) – user messages to append
    - assistant: LLMChatMessageList (multi) – assistant messages to append
    - tool: LLMChatMessageList (multi) – tool messages to append
    - prompt: str (optional) – convenience to add a single user message

    Output:
    - messages: LLMChatMessageList – merged, ordered, filtered
    """

    # Update inputs:
    inputs = {
        "base": get_type("LLMChatMessageList"),
        "system_text": str,
        **{f"message_{i}": get_type("LLMChatMessage") for i in range(10)},
        "prompt": str,
    }
    optional_inputs = ["base", "system_text", "prompt"] + [f"message_{i}" for i in range(10)]

    outputs = {
        "messages": get_type("LLMChatMessageList"),
    }

    default_params = {
        "enforce_single_system": True,
        "drop_empty": True,
        "ensure_system_first": True,
    }

    params_meta = [
        {"name": "enforce_single_system", "type": "combo", "default": True, "options": [True, False]},
        {"name": "drop_empty", "type": "combo", "default": True, "options": [True, False]},
        {"name": "ensure_system_first", "type": "combo", "default": True, "options": [True, False]},
    ]

    CATEGORY = "llm"
    ui_module = "LLMMessagesBuilderNodeUI"

    async def execute(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        merged = list(inputs.get("base") or [])
        if inputs.get("system_text"):
            merged.insert(0, {"role": "system", "content": inputs["system_text"]})
        for i in range(10):
            msg = inputs.get(f"message_{i}")
            if msg:
                merged.append(msg)
        if inputs.get("prompt"):
            merged.append({"role": "user", "content": inputs["prompt"]})
        # Add filtering if needed
        return {"messages": [m for m in merged if m]}


