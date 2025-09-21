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
        "user": get_type("LLMChatMessageList"),
        "assistant": get_type("LLMChatMessageList"),
        "tool": get_type("LLMChatMessageList"),
        **{f"message_{i}": get_type("LLMChatMessage") for i in range(10)},
        "prompt": str,
    }
    optional_inputs = ["base", "system_text", "user", "assistant", "tool", "prompt"] + [f"message_{i}" for i in range(10)]

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
            # Only add system_text if there are no existing system messages in base
            has_existing_system = any(m.get("role") == "system" for m in merged)
            if not has_existing_system:
                merged.insert(0, {"role": "system", "content": inputs["system_text"]})

        # Handle multi-inputs: user, assistant, tool
        for input_name in ["user", "assistant", "tool"]:
            input_value = inputs.get(input_name)
            if input_value:
                for item in input_value:
                    if isinstance(item, list):
                        merged.extend(item)
                    else:
                        merged.append(item)

        for i in range(10):
            msg = inputs.get(f"message_{i}")
            if msg:
                merged.append(msg)
        if inputs.get("prompt"):
            merged.append({"role": "user", "content": inputs["prompt"]})

        # Apply filtering based on params
        messages = merged
        if self.params.get("drop_empty", True):
            messages = [m for m in messages if m and (m.get("content") or "").strip()]
        if self.params.get("enforce_single_system", True):
            system_msgs = [m for m in messages if m.get("role") == "system"]
            if len(system_msgs) > 1:
                messages = [m for m in messages if m.get("role") != "system"]
                messages.insert(0, system_msgs[0])
        if self.params.get("ensure_system_first", True):
            system_msgs = [m for m in messages if m.get("role") == "system"]
            non_system_msgs = [m for m in messages if m.get("role") != "system"]
            messages = system_msgs + non_system_msgs

        return {"messages": messages}


