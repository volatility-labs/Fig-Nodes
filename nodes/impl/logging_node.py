
from typing import Dict, Any, List
from nodes.base.base_node import BaseNode
from core.types_registry import AssetSymbol

class LoggingNode(BaseNode):
    inputs = {"input": Any}
    outputs = {"output": str}

    async def execute(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        value = inputs.get("input")
        if isinstance(value, list) and value and all(isinstance(x, AssetSymbol) for x in value):
            preview_symbols = [str(sym) for sym in value[:100]]
            text = "Preview of first 100 symbols:\n" + "\n".join(preview_symbols)
            if len(value) > 100:
                text += f"\n... and {len(value) - 100} more"
            print(f"LoggingNode {self.id}: Received {len(value)} symbols. Preview:\n{text}")
        else:
            text = str(value)
            print(f"LoggingNode {self.id}: {text}")
        return {"output": text}