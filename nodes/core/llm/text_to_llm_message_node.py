from typing import Dict, Any
import json

from nodes.base.base_node import Base
from core.types_registry import get_type


class TextToLLMMessage(Base):
    """
    Adapter node: wraps generic input data into an LLMChatMessage and LLMChatMessageList.

    Can handle various input types including strings, numbers, dictionaries, lists,
    and structured data like OHLCV bars from Polygon API.

    Inputs:
    - data: Any (required) - Generic input that will be converted to text

    Params:
    - role: str in {"user", "assistant", "system", "tool"}
    - format: str - How to format structured data ("json", "readable", "compact")

    Outputs:
    - message: LLMChatMessage
    - messages: LLMChatMessageList (single-element list)
    """

    inputs = {
        "data": Any,
    }

    outputs = {
        "message": get_type("LLMChatMessage"),
        "messages": get_type("LLMChatMessageList"),
    }

    default_params = {
        "role": "user",
        "format": "readable",
    }

    params_meta = [
        {"name": "role", "type": "combo", "default": "user", "options": ["user", "assistant", "system", "tool"]},
        {"name": "format", "type": "combo", "default": "readable", "options": ["json", "readable", "compact"]},
    ]

    CATEGORY = "llm"

    def _format_data(self, data: Any, format_type: str) -> str:
        """Convert various data types to string representation."""
        if data is None:
            return ""

        if isinstance(data, str):
            return data

        if isinstance(data, (int, float, bool)):
            return str(data)

        if format_type == "json":
            try:
                return json.dumps(data, indent=2, default=str)
            except Exception:
                return str(data)

        if format_type == "compact":
            try:
                return json.dumps(data, separators=(',', ':'), default=str)
            except Exception:
                return str(data)

        # format_type == "readable" (default)
        if isinstance(data, dict):
            if "ohlcv" in data and isinstance(data["ohlcv"], list):
                # Special handling for OHLCV data from Polygon
                return self._format_ohlcv_data(data["ohlcv"])
            else:
                # Generic dict formatting
                lines = []
                for key, value in data.items():
                    if isinstance(value, list) and value and isinstance(value[0], dict):
                        # Nested structured data
                        lines.append(f"{key}:")
                        for i, item in enumerate(value[:5]):  # Limit to first 5 items
                            lines.append(f"  {i+1}. {self._format_dict_item(item)}")
                        if len(value) > 5:
                            lines.append(f"  ... and {len(value) - 5} more items")
                    else:
                        lines.append(f"{key}: {value}")
                return "\n".join(lines)

        if isinstance(data, list):
            if not data:
                return "[]"
            if len(data) <= 10 and all(isinstance(item, dict) for item in data):
                # List of dicts - format as readable list
                lines = []
                for i, item in enumerate(data):
                    lines.append(f"{i+1}. {self._format_dict_item(item)}")
                return "\n".join(lines)
            else:
                # Other lists - JSON format
                try:
                    return json.dumps(data, indent=2, default=str)
                except Exception:
                    return str(data)

        # Fallback to string conversion
        return str(data)

    def _format_ohlcv_data(self, ohlcv_list: list) -> str:
        """Special formatting for OHLCV data."""
        if not ohlcv_list:
            return "No OHLCV data available"

        lines = ["OHLCV Data:"]
        for i, bar in enumerate(ohlcv_list[:20]):  # Limit to first 20 bars
            timestamp = bar.get("timestamp", "N/A")
            open_price = bar.get("open", "N/A")
            high_price = bar.get("high", "N/A")
            low_price = bar.get("low", "N/A")
            close_price = bar.get("close", "N/A")
            volume = bar.get("volume", "N/A")

            # Convert timestamp if it's Unix milliseconds
            if isinstance(timestamp, (int, float)) and timestamp > 1e10:  # Unix ms
                from datetime import datetime
                dt = datetime.fromtimestamp(timestamp / 1000)
                timestamp = dt.strftime("%Y-%m-%d %H:%M:%S")

            lines.append(f"  {i+1}. {timestamp} | O:{open_price} H:{high_price} L:{low_price} C:{close_price} V:{volume}")

        if len(ohlcv_list) > 20:
            lines.append(f"  ... and {len(ohlcv_list) - 20} more bars")

        return "\n".join(lines)

    def _format_dict_item(self, item: dict) -> str:
        """Format a single dict item for readable display."""
        if not item:
            return "{}"

        # For OHLCV bars, show key values
        if all(key in item for key in ["open", "high", "low", "close"]):
            return f"O:{item.get('open')} H:{item.get('high')} L:{item.get('low')} C:{item.get('close')} V:{item.get('volume', 'N/A')}"

        # For other dicts, show first few key-value pairs
        pairs = []
        for key, value in list(item.items())[:3]:  # First 3 items
            if isinstance(value, (str, int, float)) and len(str(value)) < 50:
                pairs.append(f"{key}={value}")
            else:
                pairs.append(f"{key}=({type(value).__name__})")

        result = ", ".join(pairs)
        if len(item) > 3:
            result += f" (+{len(item) - 3} more)"
        return result

    async def _execute_impl(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        data = inputs.get("data")
        role = (self.params.get("role") or "user").lower()
        format_type = (self.params.get("format") or "readable").lower()

        if role not in {"user", "assistant", "system", "tool"}:
            role = "user"

        if format_type not in {"json", "readable", "compact"}:
            format_type = "readable"

        # Convert data to string representation
        content = self._format_data(data, format_type)

        msg = {"role": role, "content": content}
        return {
            "message": msg,
            "messages": [msg],
        }


