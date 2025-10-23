from typing import Dict, Any, List

from nodes.base.base_node import Base
from core.types_registry import LLMChatMessage, NodeCategory, get_type


class LLMMessagesBuilder(Base):
    """
    Builds a well-formed LLMChatMessageList by merging multiple input lists.

    Inputs:
    - message_i: LLMChatMessageList (optional, up to 10) – message lists to append in order

    Output:
    - messages: LLMChatMessageList – merged, ordered, filtered
    """

    # Update inputs:
    inputs = {
        **{f"message_{i}": get_type("LLMChatMessageList") for i in range(10)},
    }
    optional_inputs = [f"message_{i}" for i in range(10)]

    outputs = {
        "messages": get_type("LLMChatMessageList"),
    }

    default_params = {
        "drop_empty": True,
    }

    params_meta = [
        {"name": "drop_empty", "type": "combo", "default": True, "options": [True, False]},
    ]

    CATEGORY = NodeCategory.LLM

    async def _execute_impl(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        merged: List[LLMChatMessage] = []
        for i in range(10):
            msg_list = inputs.get(f"message_{i}")
            if msg_list:
                merged.extend(msg_list)

        # Apply filtering based on params
        messages = merged
        if self.params.get("drop_empty", True):
            messages = [m for m in messages if m and str(m.get("content") or "").strip()]

        return {"messages": messages}


