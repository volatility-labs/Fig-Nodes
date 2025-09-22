from typing import Dict, Any
from nodes.base.base_node import BaseNode
from core.types_registry import get_type


class TavilyAPIKeyNode(BaseNode):
    """
    Node to provide Tavily.io API key securely.
    Connect output to nodes that require Tavily API access.
    """
    ui_module = "TavilyAPIKeyNodeUI"
    inputs = {}
    outputs = {"api_key": get_type("APIKey")}
    default_params = {"api_key": ""}
    params_meta = [
        {"name": "api_key", "type": "text", "default": "", "secret": True}  # Mark as secret for UI masking
    ]

    async def execute(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        api_key = self.params.get("api_key", "").strip()
        if not api_key:
            raise ValueError("Tavily API key is required")
        return {"api_key": api_key}
