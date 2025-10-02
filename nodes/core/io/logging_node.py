from typing import Dict, Any, List
import json
from nodes.base.base_node import BaseNode
from core.types_registry import AssetSymbol


class LoggingNode(BaseNode):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.last_content_length = 0

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
        
        if isinstance(value, dict) and "message" in value and isinstance(value["message"], dict) and value["message"].get("role") == "assistant" and isinstance(value["message"].get("content"), str):
            content = value["message"]["content"]
            is_partial = not value.get("done", False)
            delta = content[self.last_content_length:]
            
            print(delta, end='', flush=True)
            
            if not is_partial:
                print()  # Newline for final
                if "thinking" in value["message"] and isinstance(value["message"]["thinking"], str):
                    print("Thinking:", value["message"]["thinking"])
                self.last_content_length = 0
            else:
                self.last_content_length = len(content)
            
            text = content  # Full current text for output/UI
        elif isinstance(value, list) and value and all(isinstance(x, AssetSymbol) for x in value):
            preview_symbols = [str(sym) for sym in value[:100]]
            text = "Preview of first 100 symbols:\n" + "\n".join(preview_symbols)
            if len(value) > 100:
                text += f"\n... and {len(value) - 100} more"
            print(text)
        elif isinstance(value, list) and value and all(isinstance(x, dict) and 'timestamp' in x and 'open' in x and 'high' in x and 'low' in x and 'close' in x for x in value):
            # OHLCV data preview
            preview_count = min(10, len(value))
            text = f"OHLCV data ({len(value)} bars):\n"
            for i, bar in enumerate(value[:preview_count]):
                text += f"Bar {i+1}: {bar['timestamp']} O:{bar['open']} H:{bar['high']} L:{bar['low']} C:{bar['close']} V:{bar['volume']}\n"
            if len(value) > preview_count:
                text += f"... and {len(value) - preview_count} more bars"
            # Only print in debug mode to reduce log verbosity
            import os
            if os.getenv("DEBUG_LOGGING") == "1":
                print(f"LoggingNode {self.id}: {text}")
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
                # Prefer message.content if present to keep logging concise
                try:
                    if isinstance(value, dict) and isinstance(value.get("message"), dict):
                        inner = value.get("message")
                        if isinstance(inner.get("content"), str):
                            text = inner.get("content")
                        else:
                            text = str(value)
                    else:
                        text = str(value)
                except Exception:
                    text = str(value)
            print(f"LoggingNode {self.id}: {text}")
        
        return {"output": text}


