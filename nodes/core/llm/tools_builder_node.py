from typing import Any

from core.types_registry import LLMToolSpec, NodeCategory, NodeInputs, get_type
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
        tools_list: list[LLMToolSpec] = inputs.get("tools_list", [])

        if len(tools_list) > 5:
            raise ValueError(f"tools_list must be less than 5 tools, got {len(tools_list)}")

        # Validate each tool spec according to LLMToolSpec TypedDict
        validated_tools: list[LLMToolSpec] = []
        for i, tool_spec in enumerate(tools_list):
            # Validate required 'type' field
            if "type" not in tool_spec:
                raise ValueError(f"Tool at index {i} must have a 'type' field")
            if tool_spec["type"] != "function":
                raise ValueError(
                    f"Tool at index {i} must have type 'function', got '{tool_spec['type']}'"
                )

            # Validate required 'function' field
            if "function" not in tool_spec:
                raise ValueError(f"Tool at index {i} must have a 'function' field")

            function_spec = tool_spec["function"]

            # Validate LLMToolFunction fields (name is required, description and parameters are optional)
            if "name" not in function_spec:
                raise ValueError(f"Tool at index {i} function must have a 'name' field")

            validated_tools.append(tool_spec)

        return {"tools": validated_tools}
