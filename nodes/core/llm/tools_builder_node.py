from typing import Any

from core.types_registry import (
    LLMToolSpec,
    NodeCategory,
    NodeInputs,
    get_type,
    serialize_for_api,
    validate_llm_tool_spec,
)
from nodes.base.base_node import Base


class ToolsBuilder(Base):
    """
    Takes a list of max 5 tool specs and outputs them as LLMToolSpecList.

    Input:
    - tools_list: List[LLMToolSpec] - less than 5 tool specifications

    Output:
    - tools: LLMToolSpecList
    """

    inputs = {
        "tools_list": get_type("LLMToolSpecList"),
    }

    optional_inputs = ["tools_list"]

    outputs = {
        "tools": get_type("LLMToolSpecList"),
    }

    CATEGORY = NodeCategory.LLM

    async def _execute_impl(self, inputs: NodeInputs) -> dict[str, Any]:
        tools_input = inputs.get("tools_list", [])

        if len(tools_input) > 5:
            raise ValueError(f"tools_list must be less than 5 tools, got {len(tools_input)}")

        # Validate and convert each tool spec to LLMToolSpec Pydantic model
        validated_tools: list[LLMToolSpec] = []
        for i, tool_spec in enumerate(tools_input):
            validated = validate_llm_tool_spec(tool_spec)
            if validated:
                validated_tools.append(validated)
            else:
                raise ValueError(f"Tool at index {i} is invalid: expected LLMToolSpec")

        return {"tools": serialize_for_api(validated_tools)}
