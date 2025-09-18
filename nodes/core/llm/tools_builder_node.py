from typing import Dict, Any, List

from nodes.base.base_node import BaseNode
from core.types_registry import get_type


class ToolsBuilderNode(BaseNode):
    """
    Aggregates multiple tool specs into a single LLMToolSpecList output.

    Inputs (all optional, multi-input):
    - tool: LLMToolSpec (multi)
    - tools: LLMToolSpecList (multi)

    Output:
    - tools: LLMToolSpecList
    """

    inputs = {
        # Declare as list to enable multi-input slots: tool_0, tool_1, ...
        "tool": get_type("LLMToolSpecList"),
    }

    # Allow both inputs to be optional
    optional_inputs = ["tool"]

    outputs = {
        "tools": get_type("LLMToolSpecList"),
    }

    CATEGORY = "llm"

    async def execute(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        result: List[Dict[str, Any]] = []

        def _append_tool_spec(v):
            if isinstance(v, dict) and v.get("type") == "function" and isinstance(v.get("function"), dict):
                result.append(v)

        # Collect single tool specs from multi input "tool"
        for v in self.collect_multi_input("tool", inputs):
            if isinstance(v, list):
                for item in v:
                    _append_tool_spec(item)
            else:
                _append_tool_spec(v)

        # No additional list input; only aggregate from multi "tool" inputs

        # Deduplicate by function.name when possible
        seen = set()
        deduped: List[Dict[str, Any]] = []
        for spec in result:
            name = None
            try:
                name = spec.get("function", {}).get("name")
            except Exception:
                name = None
            key = name or id(spec)
            if key in seen:
                continue
            seen.add(key)
            deduped.append(spec)

        return {"tools": deduped}


