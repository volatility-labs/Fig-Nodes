from typing import Any

from core.types_registry import (
    LLMChatMessage,
    NodeCategory,
    get_type,
    serialize_for_api,
    validate_llm_chat_message,
)
from nodes.base.base_node import Base


class LLMMessagesBuilder(Base):
    """
    Builds a well-formed LLMChatMessageList by merging multiple input messages.

    Inputs:
    - message_i: LLMChatMessage (optional, up to 10) – individual messages or lists to append in order

    Output:
    - messages: LLMChatMessageList – merged, ordered, filtered
    """

    # Update inputs:
    inputs = {
        **{f"message_{i}": get_type("LLMChatMessage") | None for i in range(10)},
    }

    outputs = {
        "messages": get_type("LLMChatMessageList") | None,
    }

    default_params = {}

    params_meta = []

    CATEGORY = NodeCategory.LLM

    async def _execute_impl(self, inputs: dict[str, Any]) -> dict[str, Any]:
        merged: list[LLMChatMessage] = []
        for i in range(10):
            msg = inputs.get(f"message_{i}")
            if msg:
                validated = validate_llm_chat_message(msg)
                if validated:
                    merged.append(validated)
                else:
                    raise TypeError(f"Expected LLMChatMessage, got {type(msg)}")

        # Always drop empty messages
        messages = [
            m for m in merged if m and str(m.content if isinstance(m.content, str) else "").strip()
        ]

        return {"messages": serialize_for_api(messages)}
