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

    inputs = {
        "base": get_type("LLMChatMessageList"),
        "system_text": str,
        "user": get_type("LLMChatMessageList"),
        "assistant": get_type("LLMChatMessageList"),
        "tool": get_type("LLMChatMessageList"),
        "prompt": str,
    }

    # All inputs are optional; builder will produce an empty list if nothing is provided
    optional_inputs = ["base", "system_text", "user", "assistant", "tool", "prompt"]

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
        merged: List[Dict[str, Any]] = []

        base_messages = inputs.get("base") or []
        if isinstance(base_messages, list):
            for item in base_messages:
                if isinstance(item, dict):
                    merged.append(item)

        system_text: Optional[str] = inputs.get("system_text")
        if system_text and isinstance(system_text, str) and system_text.strip():
            if self.params.get("enforce_single_system", True):
                has_system = any(isinstance(m, dict) and m.get("role") == "system" for m in merged)
                if not has_system:
                    merged.insert(0, {"role": "system", "content": system_text})
                elif self.params.get("ensure_system_first", True):
                    for idx, m in enumerate(merged):
                        if m.get("role") == "system":
                            sys_msg = merged.pop(idx)
                            merged.insert(0, sys_msg)
                            break
            else:
                merged.insert(0, {"role": "system", "content": system_text})

        def _append_messages_from_key(key: str):
            values = self.collect_multi_input(key, inputs)
            for v in values:
                if isinstance(v, list):
                    for item in v:
                        if isinstance(item, dict):
                            merged.append(item)
                elif isinstance(v, dict):
                    merged.append(v)

        _append_messages_from_key("user")
        _append_messages_from_key("assistant")
        _append_messages_from_key("tool")

        prompt_text: Optional[str] = inputs.get("prompt")
        if isinstance(prompt_text, str) and prompt_text.strip():
            merged.append({"role": "user", "content": prompt_text})

        if self.params.get("drop_empty", True):
            filtered: List[Dict[str, Any]] = []
            for m in merged:
                if not isinstance(m, dict):
                    continue
                content = m.get("content")
                if isinstance(content, str):
                    if content.strip():
                        filtered.append(m)
                else:
                    # Allow non-string content (e.g., structured JSON) to pass through
                    filtered.append(m)
            merged = filtered

        # Basic role validation: keep only recognized roles when present
        allowed_roles = {"system", "user", "assistant", "tool"}
        normalized: List[Dict[str, Any]] = []
        for m in merged:
            if not isinstance(m, dict):
                continue
            role = m.get("role")
            if role is None or role in allowed_roles:
                normalized.append(m)
        merged = normalized

        return {"messages": merged}


