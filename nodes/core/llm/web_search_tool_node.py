from typing import Dict, Any

from nodes.base.base_node import BaseNode
from core.types_registry import get_type
from services.tools.web_search import WebSearchTool


class WebSearchToolNode(BaseNode):
    """
    Atomic tool node that outputs the web_search tool schema configured by params.

    Params:
    - provider: combo [tavily]
    - default_k: number (1..10)
    - time_range: combo [day, week, month, year, all]
    - lang: text (e.g., en)
    - require_api_key: combo [True, False] (if True, checks env var present)

    Output:
    - tool: LLMToolSpec

    Note: API keys are supplied via environment (e.g., TAVILY_API_KEY). This node does not
    embed secrets. The handler will read env at execution time.
    """

    inputs = {}
    outputs = {
        "tool": get_type("LLMToolSpec"),
    }

    default_params = {
        "provider": "tavily",
        "default_k": 5,
        "time_range": "month",
        "lang": "en",
        "require_api_key": True,
    }

    params_meta = [
        {"name": "provider", "type": "combo", "default": "tavily", "options": ["tavily"]},
        {"name": "default_k", "type": "number", "default": 5},
        {"name": "time_range", "type": "combo", "default": "month", "options": ["day", "week", "month", "year", "all"]},
        {"name": "lang", "type": "text", "default": "en"},
        {"name": "require_api_key", "type": "combo", "default": True, "options": [True, False]},
    ]

    CATEGORY = "llm"

    async def execute(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        # Build a schema from the provider object and inject defaults as JSON Schema "default" values
        tool = WebSearchTool()
        schema = tool.schema()
        try:
            fn = schema.get("function", {})
            params = fn.get("parameters", {})
            props = params.get("properties", {})
            if "k" in props:
                props["k"]["default"] = int(self.params.get("default_k", 5) or 5)
            if "time_range" in props:
                tr = self.params.get("time_range") or "month"
                if tr in ["day", "week", "month", "year", "all"]:
                    props["time_range"]["default"] = tr
            if "lang" in props:
                lg = self.params.get("lang") or "en"
                props["lang"]["default"] = str(lg)
        except Exception:
            pass

        return {"tool": schema}


