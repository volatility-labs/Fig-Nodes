from typing import Any, TypeGuard

from core.types_registry import LLMChatMessage, NodeCategory, get_type
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

    def _is_llm_chat_message(self, msg: Any) -> TypeGuard[LLMChatMessage]:
        """Type guard to validate LLMChatMessage structure."""
        return (
            isinstance(msg, dict)
            and "role" in msg
            and "content" in msg
            and isinstance(msg["role"], str)
            and msg["role"] in ("system", "user", "assistant", "tool")
        )

    async def _execute_impl(self, inputs: dict[str, Any]) -> dict[str, Any]:
        merged: list[LLMChatMessage] = []
        for i in range(10):
            msg = inputs.get(f"message_{i}")
            if msg:
                if self._is_llm_chat_message(msg):
                    merged.append(msg)
                else:
                    raise TypeError(f"Expected LLMChatMessage, got {type(msg)}")

        # Always drop empty messages
        messages = [m for m in merged if m and str(m.get("content") or "").strip()]

        return {"messages": messages}
