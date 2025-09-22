from typing import Dict, Any

from nodes.base.base_node import BaseNode
from core.types_registry import get_type
from services.tools.web_search import WebSearchTool
from services.tools.registry import register_credential_provider, get_tool_schema


class WebSearchToolNode(BaseNode):
    """
    Atomic tool node that outputs the web_search tool schema configured by params.

    Inputs:
    - api_key: APIKey (Tavily API key for authentication)

    Params:
    - provider: combo [tavily]
    - default_k: number (1..10)
    - time_range: combo [day, week, month, year, all]
    - lang: text (e.g., en)

    Output:
    - tool: LLMToolSpec

    Note: API key is supplied via input connection. The handler will use the provided key at execution time.
    """

    inputs = {
        "api_key": get_type("APIKey"),
    }
    outputs = {
        "tool": get_type("LLMToolSpec"),
    }

    default_params = {
        "provider": "tavily",
        "default_k": 5,
        "time_range": "month",
        "topic": "general",
        "lang": "en",
    }

    params_meta = [
        {"name": "provider", "type": "combo", "default": "tavily", "options": ["tavily"]},
        {"name": "default_k", "type": "number", "default": 5},
        {"name": "time_range", "type": "combo", "default": "month", "options": ["day", "week", "month", "year"]},
        {"name": "topic", "type": "combo", "default": "general", "options": ["general", "news", "finance"]},
        {"name": "lang", "type": "text", "default": "en"},
    ]

    CATEGORY = "llm"

    async def execute(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        api_key = inputs.get("api_key", "").strip()
        if not api_key:
            raise ValueError("Tavily API key is required")

        # Register the credential provider so tools can access the API key
        def _get_api_key() -> str:
            return api_key

        register_credential_provider("tavily_api_key", _get_api_key)

        # Get the base schema from the registry and inject defaults
        schema = get_tool_schema("web_search")
        if schema:
            try:
                fn = schema.get("function", {})
                params = fn.get("parameters", {})
                props = params.get("properties", {})
                if "k" in props:
                    props["k"]["default"] = int(self.params.get("default_k", 5) or 5)
                if "time_range" in props:
                    tr = self.params.get("time_range") or "month"
                    if tr in ["day", "week", "month", "year"]:
                        props["time_range"]["default"] = tr
                if "topic" in props:
                    tp = self.params.get("topic") or "general"
                    if tp in ["general", "news", "finance"]:
                        props["topic"]["default"] = tp
                if "lang" in props:
                    lg = self.params.get("lang") or "en"
                    props["lang"]["default"] = str(lg)
            except Exception:
                pass

        return {"tool": schema}


