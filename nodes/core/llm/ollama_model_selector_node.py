from typing import Dict, Any, List
from nodes.base.base_node import BaseNode
import os


class OllamaModelSelectorNode(BaseNode):
    """
    Lists locally available Ollama models and outputs the selected model name.

    This node does not pull or download models; it only queries the local Ollama server.
    """

    inputs = {}
    outputs = {"host": str, "model": str, "models": List[str]}

    default_params = {
        "host": os.getenv("OLLAMA_HOST", "http://localhost:11434"),
        "selected": "",
    }

    params_meta = [
        {"name": "host", "type": "text", "default": os.getenv("OLLAMA_HOST", "http://localhost:11434")},
        {"name": "selected", "type": "combo", "default": "", "options": []},
    ]

    ui_module = None  # Backend provides list; UI will render dropdown using params_meta

    async def execute(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        host = self.params.get("host") or "http://localhost:11434"
        selected = self.params.get("selected") or ""

        print(f"OllamaModelSelectorNode: host={host}, selected='{selected}'")

        try:
            import httpx
            async with httpx.AsyncClient(timeout=10.0) as client:
                print(f"OllamaModelSelectorNode: Querying {host}/api/tags")
                r = await client.get(f"{host}/api/tags")
                r.raise_for_status()
                data = r.json()
                models_list = [m.get("name") for m in data.get("models", []) if m.get("name")]
                print(f"OllamaModelSelectorNode: Found {len(models_list)} models: {models_list}")
        except Exception as e:
            print(f"OllamaModelSelectorNode: Error querying Ollama models: {e}")
            models_list = []

        # Update params_meta options dynamically for UI consumption via /nodes metadata
        for p in self.params_meta:
            if p["name"] == "selected":
                p["options"] = models_list
                break

        # If selected is empty or not in list, choose first if available
        if (not selected or selected not in models_list) and models_list:
            selected = models_list[0]
            print(f"OllamaModelSelectorNode: Auto-selected first model: {selected}")
        
        # Validate final selection
        if not selected and not models_list:
            error_msg = "No local Ollama models found. Pull one via 'ollama pull <model>'"
            print(f"OllamaModelSelectorNode: ERROR - {error_msg}")
            raise ValueError(error_msg)
        elif selected and selected not in models_list:
            print(f"OllamaModelSelectorNode: WARNING - Selected model '{selected}' not in available models {models_list}")

        print(f"OllamaModelSelectorNode: Final output - host={host}, model='{selected}', models_count={len(models_list)}")
        return {"host": host, "model": selected, "models": models_list}


