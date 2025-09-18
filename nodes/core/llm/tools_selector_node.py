from typing import Dict, Any, List

from nodes.base.base_node import BaseNode
from core.types_registry import get_type
from services.tools.registry import list_tool_names, get_tool_schema


class ToolsSelectorNode(BaseNode):
    """
    Selects one or more registered tool schemas and outputs them as LLMToolSpecList.

    Params:
    - selected: List[str] – names of tools to include

    Outputs:
    - tools: LLMToolSpecList
    - available: List[str] – names of available tools for UI consumption
    """

    inputs = {}
    outputs = {
        "tools": get_type("LLMToolSpecList"),
        "available": List[str],
    }

    default_params = {
        "selected": [],
    }

    params_meta = [
        {"name": "selected", "type": "multiselect", "default": [], "options": []},
    ]

    CATEGORY = "llm"

    async def execute(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        names = list_tool_names()
        # update UI options dynamically
        for p in self.params_meta:
            if p["name"] == "selected":
                p["options"] = names
                break

        selected = self.params.get("selected") or []
        if not isinstance(selected, list):
            selected = []

        schemas: List[Dict[str, Any]] = []
        for name in selected:
            schema = get_tool_schema(name)
            if schema:
                schemas.append(schema)

        return {"tools": schemas, "available": names}


