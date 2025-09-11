from typing import Dict, Any
from nodes.base.base_node import BaseNode


class SystemPromptLoaderNode(BaseNode):
    """Loads a system prompt from UI-provided content (e.g., uploaded .md/.txt).

    Outputs:
    - system: str
    """

    inputs = {}
    outputs = {"system": str}
    default_params = {"content": ""}
    params_meta = [
        {"name": "content", "type": "textarea", "default": ""},
    ]

    # Keep visible in IO category
    CATEGORY = 'io'

    # Custom UI component for file upload & preview
    ui_module = "SystemPromptLoaderNodeUI"

    async def execute(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        content = self.params.get("content") or ""
        if not isinstance(content, str):
            content = str(content)
        return {"system": content}


