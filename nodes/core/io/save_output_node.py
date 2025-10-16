import os
import json
import uuid
from datetime import datetime
from typing import Dict, Any, List, Union
from nodes.base.base_node import Base
from core.types_registry import AssetSymbol, OHLCVBar, LLMChatMessage, LLMToolSpec, LLMChatMetrics, LLMToolHistoryItem, LLMThinkingHistoryItem
import io


class SaveOutput(Base):
    """
    Node to save node outputs to disk in the output folder.

    The saved data is serialized in a format that preserves type information
    so it can be read back by a corresponding load node.

    Input:
    - data: Any - The data to save (any type defined in types_registry)

    Output:
    - filepath: str - The path to the saved file

    Parameters:
    - filename: str - Optional filename (auto-generated if empty)
    - format: str - Serialization format ("json" or "jsonl" for lists)
    - overwrite: bool - Whether to overwrite existing files
    """

    inputs = {"data": Any}
    outputs = {"filepath": str}

    default_params = {
        "filename": "",
        "format": "json",
        "overwrite": False,
    }

    params_meta = [
        {"name": "filename", "type": "text", "default": ""},
        {"name": "format", "type": "combo", "default": "json", "options": ["json", "jsonl"]},
        {"name": "overwrite", "type": "combo", "default": False, "options": [True, False]},
    ]

    CATEGORY = "io"
    ui_module = "io/SaveOutputNodeUI"

    def _serialize_value(self, value: Any) -> Any:
        """Recursively serialize a value to JSON-compatible format with type preservation."""
        if value is None:
            return {"__type__": "None", "value": None}

        # Handle AssetSymbol
        if isinstance(value, AssetSymbol):
            return {"__type__": "AssetSymbol", "data": value.to_dict()}

        # Handle lists
        if isinstance(value, list):
            return {"__type__": "list", "items": [self._serialize_value(item) for item in value]}

        # Handle dicts
        if isinstance(value, dict):
            # Check if it's a TypedDict (OHLCVBar, LLMChatMessage, etc.)
            if self._is_ohlcv_bar(value):
                return {"__type__": "OHLCVBar", "data": value}
            elif self._is_llm_chat_message(value):
                return {"__type__": "LLMChatMessage", "data": value}
            elif self._is_llm_tool_spec(value):
                return {"__type__": "LLMToolSpec", "data": value}
            elif self._is_llm_chat_metrics(value):
                return {"__type__": "LLMChatMetrics", "data": value}
            elif self._is_llm_tool_history_item(value):
                return {"__type__": "LLMToolHistoryItem", "data": value}
            elif self._is_llm_thinking_history_item(value):
                return {"__type__": "LLMThinkingHistoryItem", "data": value}
            else:
                # Regular dict
                return {"__type__": "dict", "data": {k: self._serialize_value(v) for k, v in value.items()}}

        # Handle basic types
        if isinstance(value, (str, int, float, bool)):
            return {"__type__": type(value).__name__, "value": value}

        # Fallback: try to convert to string and store as such
        try:
            return {"__type__": "str", "value": str(value)}
        except Exception:
            return {"__type__": "str", "value": repr(value)}

    def _is_ohlcv_bar(self, value: Dict[str, Any]) -> bool:
        """Check if dict represents an OHLCVBar."""
        required_keys = {"timestamp", "open", "high", "low", "close", "volume"}
        return isinstance(value, dict) and all(key in value for key in required_keys)

    def _is_llm_chat_message(self, value: Dict[str, Any]) -> bool:
        """Check if dict represents an LLMChatMessage."""
        required_keys = {"role", "content"}
        return isinstance(value, dict) and all(key in value for key in required_keys)

    def _is_llm_tool_spec(self, value: Dict[str, Any]) -> bool:
        """Check if dict represents an LLMToolSpec."""
        return isinstance(value, dict) and value.get("type") == "function" and "function" in value

    def _is_llm_chat_metrics(self, value: Dict[str, Any]) -> bool:
        """Check if dict represents LLMChatMetrics."""
        metric_keys = {"total_duration", "load_duration", "prompt_eval_count",
                      "prompt_eval_duration", "eval_count", "eval_duration", "error"}
        return isinstance(value, dict) and any(key in value for key in metric_keys)

    def _is_llm_tool_history_item(self, value: Dict[str, Any]) -> bool:
        """Check if dict represents an LLMToolHistoryItem."""
        return isinstance(value, dict) and "call" in value and "result" in value

    def _is_llm_thinking_history_item(self, value: Dict[str, Any]) -> bool:
        """Check if dict represents an LLMThinkingHistoryItem."""
        return isinstance(value, dict) and "thinking" in value and "iteration" in value

    def _generate_filename(self, base_name: str, data: Any, format_ext: str = '.json') -> str:
        """Generate a unique filename based on base name, data type, timestamp, and increment if needed."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Determine type prefix
        if isinstance(data, AssetSymbol):
            type_prefix = "assetsymbol"
        elif isinstance(data, list):
            if data and isinstance(data[0], AssetSymbol):
                type_prefix = "assetsymbol_list"
            elif data and self._is_ohlcv_bar(data[0]):
                type_prefix = "ohlcv"
            else:
                type_prefix = "list"
        elif isinstance(data, dict):
            if self._is_ohlcv_bar(data):
                type_prefix = "ohlcv_bar"
            elif self._is_llm_chat_message(data):
                type_prefix = "llm_message"
            else:
                type_prefix = "dict"
        elif isinstance(data, str):
            type_prefix = "text"
        else:
            type_prefix = type(data).__name__.lower()
        
        if not base_name:
            base_name = f"{type_prefix}_{timestamp}_{str(uuid.uuid4())[:8]}"
        
        # Ensure extension
        if not base_name.endswith(format_ext):
            base_name += format_ext
        
        return base_name

    async def _execute_impl(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        data = inputs.get("data")
        if data is None:
            raise ValueError("No data provided to save")
        
        # Get parameters
        base_filename = self.params.get("filename", "").strip()
        format_type = self.params.get("format", "json")
        overwrite = self.params.get("overwrite", False)
        format_ext = '.jsonl' if format_type == 'jsonl' else '.json'
        
        # Generate initial filename
        filename = self._generate_filename(base_filename, data, format_ext)
        
        # Create output directory if it doesn't exist
        output_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))), 'output')
        os.makedirs(output_dir, exist_ok=True)
        
        filepath = os.path.join(output_dir, filename)
        
        # If not overwrite, find unique name with counter
        if not overwrite:
            counter = 1
            name_parts = filename.rsplit(format_ext, 1)
            while os.path.exists(filepath):
                filename = f"{name_parts[0]}_{counter:03d}{format_ext}"
                filepath = os.path.join(output_dir, filename)
                counter += 1
        
        # Serialize data
        try:
            if format_type == "jsonl" and isinstance(data, list):
                # JSON Lines format for lists
                serialized_data = {
                    "__metadata__": {
                        "type": "jsonl",
                        "item_type": self._infer_list_item_type(data),
                        "count": len(data),
                        "timestamp": datetime.now().isoformat()
                    }
                }
                
                with open(filepath, 'w', encoding='utf-8') as f:
                    # Write metadata as first line
                    f.write(json.dumps(serialized_data, ensure_ascii=False) + '\n')
                    # Write each item as separate JSON line
                    for item in data:
                        serialized_item = self._serialize_value(item)
                        f.write(json.dumps(serialized_item, ensure_ascii=False) + '\n')
            else:
                # Regular JSON format
                serialized_data = {
                    "__metadata__": {
                        "type": "json",
                        "data_type": self._infer_data_type(data),
                        "timestamp": datetime.now().isoformat()
                    },
                    "data": self._serialize_value(data)
                }
                
                with open(filepath, 'w', encoding='utf-8') as f:
                    json.dump(serialized_data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            raise IOError(f"Failed to save to {filepath}: {str(e)}") from e
        
        return {"filepath": filepath}

    def _infer_data_type(self, data: Any) -> str:
        """Infer the type name for metadata."""
        if isinstance(data, AssetSymbol):
            return "AssetSymbol"
        elif isinstance(data, list):
            if data and isinstance(data[0], AssetSymbol):
                return "AssetSymbolList"
            elif data and self._is_ohlcv_bar(data[0]):
                return "OHLCV"
            else:
                return "List"
        elif isinstance(data, dict):
            if self._is_ohlcv_bar(data):
                return "OHLCVBar"
            elif self._is_llm_chat_message(data):
                return "LLMChatMessage"
            else:
                return "Dict"
        else:
            return type(data).__name__

    def _infer_list_item_type(self, data: List[Any]) -> str:
        """Infer the type of items in a list."""
        if not data:
            return "Any"
        first_item = data[0]
        return self._infer_data_type(first_item)
