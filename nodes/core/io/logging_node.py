from typing import Dict, Any, List
import json
from nodes.base.base_node import BaseNode
from core.types_registry import AssetSymbol


class LoggingNode(BaseNode):
    inputs = {"input": Any}
    outputs = {"output": str}
    
    # Allow UI to select how to display/parse the output text
    default_params = {
        "format": "auto",  # one of: auto | plain | json | markdown
    }
    params_meta = [
        {"name": "format", "type": "combo", "default": "auto", "options": ["auto", "plain", "json", "markdown"]},
    ]

    async def execute(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        value = inputs.get("input")
        selected_format = (self.params.get("format") or "auto").strip()
        if isinstance(value, list) and value and all(isinstance(x, AssetSymbol) for x in value):
            preview_symbols = [str(sym) for sym in value[:100]]
            text = "Preview of first 100 symbols:\n" + "\n".join(preview_symbols)
            if len(value) > 100:
                text += f"\n... and {len(value) - 100} more"
            print(f"LoggingNode {self.id}: Received {len(value)} symbols. Preview:\n{text}")
        else:
            if selected_format == "json":
                # Produce a valid JSON string to enable UI pretty printing
                try:
                    if isinstance(value, str):
                        # If it's already a string, prefer parsing to validate; otherwise keep raw
                        try:
                            parsed = json.loads(value)
                            text = json.dumps(parsed, ensure_ascii=False)
                        except Exception:
                            # Fall back to serializing the original value if possible
                            text = json.dumps(value, ensure_ascii=False)
                    else:
                        text = json.dumps(value, ensure_ascii=False, default=str)
                except Exception:
                    text = str(value)
            else:
                text = str(value)
            print(f"LoggingNode {self.id}: {text}")
        return {"output": text}


