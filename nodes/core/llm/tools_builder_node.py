from typing import Dict, Any, List

from nodes.base.base_node import Base
from core.types_registry import get_type


class ToolsBuilder(Base):
    """
    Takes a list of exactly 5 tool specs and outputs them as LLMToolSpecList.

    Input:
    - tools_list: List[LLMToolSpec] - exactly 5 tool specifications

    Output:
    - tools: LLMToolSpecList
    """

    inputs = {
        "tools_list": get_type("LLMToolSpecList"),  # Changed from List[get_type("LLMToolSpec")]
    }

    optional_inputs = ["tools_list"]

    outputs = {
        "tools": get_type("LLMToolSpecList"),
    }

    CATEGORY = "llm"

    async def _execute_impl(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        tools_list = inputs.get("tools_list", [])

        if not isinstance(tools_list, list):
            raise ValueError("tools_list must be a list")

        if len(tools_list) != 5:
            raise ValueError(f"tools_list must contain exactly 5 tools, got {len(tools_list)}")

        # Validate each tool spec
        validated_tools = []
        for i, tool_spec in enumerate(tools_list):
            if not isinstance(tool_spec, dict):
                raise ValueError(f"Tool at index {i} must be a dict")
            if tool_spec.get("type") != "function":
                raise ValueError(f"Tool at index {i} must have type 'function'")
            if not isinstance(tool_spec.get("function"), dict):
                raise ValueError(f"Tool at index {i} must have a 'function' dict")
            validated_tools.append(tool_spec)

        return {"tools": validated_tools}


