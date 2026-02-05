import json
from datetime import datetime
from typing import Any, cast

from core.types_registry import NodeCategory, NodeInputs, get_type
from nodes.base.base_node import Base


class TextToLLMMessage(Base):
    """
    Adapter node: wraps generic input data into an LLMChatMessage.

    Can handle various input types including strings, numbers, dictionaries, lists,
    and structured data like OHLCV bars from Polygon API.

    Inputs:
    - data: Any (required) - Generic input that will be converted to text

    Params:
    - role: str in {"user", "assistant", "system", "tool"}
    - format: str - How to format structured data ("json", "readable", "compact")

    Outputs:
    - message: LLMChatMessage
    """

    inputs = {
        "data": Any,
    }

    outputs = {
        "message": get_type("LLMChatMessage") | None,
    }

    default_params = {
        "role": "user",
        "format": "readable",
    }

    params_meta = [
        {
            "name": "role",
            "type": "combo",
            "default": "user",
            "options": ["user", "assistant", "system", "tool"],
        },
        {
            "name": "format",
            "type": "combo",
            "default": "readable",
            "options": ["json", "readable", "compact"],
        },
    ]

    CATEGORY = NodeCategory.LLM

    def _is_ohlcv_bar(self, data: Any) -> bool:
        """Check if dict represents an OHLCVBar."""
        return isinstance(data, dict) and all(
            k in data for k in ("timestamp", "open", "high", "low", "close", "volume")
        )

    def _is_chat_message(self, data: Any) -> bool:
        """Check if dict represents an LLMChatMessage."""
        return (
            isinstance(data, dict)
            and "role" in data
            and "content" in data
            and data["role"] in ("system", "user", "assistant", "tool")
        )

    def _is_indicator_result(self, data: Any) -> bool:
        """Check if dict represents an IndicatorResult."""
        return isinstance(data, dict) and "indicator_type" in data and "values" in data

    def _format_ohlcv_bar(self, bar: dict[str, Any]) -> str:
        """Format a single OHLCVBar."""
        timestamp = bar.get("timestamp", "N/A")
        if isinstance(timestamp, int | float) and timestamp > 1e10:
            dt = datetime.fromtimestamp(timestamp / 1000)
            timestamp = dt.strftime("%Y-%m-%d %H:%M:%S")
        return (
            f"{timestamp} | O:{bar.get('open', 'N/A')} "
            f"H:{bar.get('high', 'N/A')} L:{bar.get('low', 'N/A')} "
            f"C:{bar.get('close', 'N/A')} V:{bar.get('volume', 'N/A')}"
        )

    def _format_chat_message(self, msg: dict[str, Any]) -> str:
        """Format an LLMChatMessage."""
        role = msg.get("role", "unknown")
        content = msg.get("content", "")
        if isinstance(content, dict):
            content = json.dumps(content, indent=2)
        parts = [f"Role: {role}"]
        if "thinking" in msg:
            parts.append(f"Thinking: {msg['thinking']}")
        if "tool_calls" in msg:
            parts.append(f"Tool calls: {len(msg['tool_calls'])}")
        parts.append(f"Content: {content}")
        return "\n".join(parts)

    def _format_indicator_result(self, result: dict[str, Any]) -> str:
        """Format an IndicatorResult."""
        indicator_type = result.get("indicator_type", "unknown")
        values = result.get("values", {})
        lines = [f"Indicator: {indicator_type}"]
        if isinstance(values, dict):
            if "single" in values:
                lines.append(f"Value: {values['single']}")
            if "lines" in values:
                lines.append(f"Lines: {values['lines']}")
        return "\n".join(lines)

    def _format_ohlcv_data(self, ohlcv_list: list[dict[str, Any]]) -> str:
        """Special formatting for OHLCV data."""
        if not ohlcv_list:
            return "No OHLCV data available"

        lines = ["OHLCV Data:"]
        for i, bar in enumerate(ohlcv_list[:20]):  # Limit to first 20 bars
            lines.append(f"  {i + 1}. {self._format_ohlcv_bar(bar)}")

        if len(ohlcv_list) > 20:
            lines.append(f"  ... and {len(ohlcv_list) - 20} more bars")

        return "\n".join(lines)

    def _format_dict_item(self, item: dict[str, Any]) -> str:
        """Format a single dict item for readable display."""
        if not item:
            return "{}"

        # For other dicts, show first few key-value pairs
        pairs: list[str] = []
        for key, value in list(item.items())[:3]:  # First 3 items
            if isinstance(value, str | int | float) and len(str(value)) < 50:
                pairs.append(f"{key}={value}")
            else:
                pairs.append(f"{key}=({type(value).__name__})")

        result = ", ".join(pairs)
        if len(item) > 3:
            result += f" (+{len(item) - 3} more)"
        return result

    def _format_data(self, data: Any, format_type: str) -> str:
        """Convert various data types to string representation."""
        if data is None:
            return ""

        if isinstance(data, str):
            return data

        if isinstance(data, int | float | bool):
            return str(data)

        # JSON and compact formats don't need type-specific handling
        if format_type == "json":
            return self._format_as_json(data, indent=2)
        if format_type == "compact":
            return self._format_as_json(data, separators=(",", ":"))

        # Readable format - handle based on data structure
        if isinstance(data, dict):
            return self._format_dict_readable(cast(dict[str, Any], data))
        if isinstance(data, list):
            return self._format_list_readable(cast(list[Any], data))

        return str(data)

    def _format_as_json(self, data: Any, **kwargs: Any) -> str:
        """Format data as JSON with error handling."""
        try:
            return json.dumps(data, default=str, **kwargs)
        except Exception:
            return str(data)

    def _format_dict_readable(self, data: dict[str, Any]) -> str:
        """Format a dictionary in readable format with structural type detection."""
        # Check for known TypedDict types first
        if self._is_ohlcv_bar(data):
            return self._format_ohlcv_bar(data)
        if self._is_chat_message(data):
            return self._format_chat_message(data)
        if self._is_indicator_result(data):
            return self._format_indicator_result(data)

        # Special case: dict containing ohlcv list (Polygon API format)
        if "ohlcv" in data and isinstance(data["ohlcv"], list):
            return self._format_ohlcv_data(cast(list[dict[str, Any]], data["ohlcv"]))

        # Generic dict formatting
        return self._format_generic_dict(data)

    def _format_list_readable(self, data: list[Any]) -> str:
        """Format a list in readable format with structural type detection."""
        if not data:
            return "[]"

        # Check first item to determine list structure
        if isinstance(data[0], dict):
            if self._is_ohlcv_bar(data[0]):
                return self._format_ohlcv_list(data)
            if len(data) <= 10:
                return self._format_dict_list(data)

        # Default to JSON for other lists
        return self._format_as_json(data, indent=2)

    def _format_ohlcv_list(self, data: list[dict[str, Any]]) -> str:
        """Format a list of OHLCV bars."""
        lines: list[str] = []
        for i, bar in enumerate(data[:20]):
            lines.append(f"{i + 1}. {self._format_ohlcv_bar(bar)}")
        if len(data) > 20:
            lines.append(f"... and {len(data) - 20} more")
        return "\n".join(lines)

    def _format_dict_list(self, data: list[dict[str, Any]]) -> str:
        """Format a list of generic dictionaries."""
        lines: list[str] = []
        for i, item in enumerate(data):
            lines.append(f"{i + 1}. {self._format_dict_item(item)}")
        return "\n".join(lines)

    def _format_generic_dict(self, data: dict[str, Any]) -> str:
        """Format a generic dictionary with nested value handling."""
        lines: list[str] = []
        for key, value in data.items():
            if isinstance(value, list) and value:
                # Check if this is a list of dicts
                is_list_of_dicts = isinstance(value[0], dict)
                if is_list_of_dicts:
                    # Nested list of dicts
                    lines.append(f"{key}:")
                    count = 0
                    # Explicitly iterate and type-check each item
                    list_value: list[Any] = value
                    for item_raw in list_value:
                        if count >= 100:
                            break
                        if isinstance(item_raw, dict):
                            item: dict[str, Any] = item_raw
                            lines.append(f"  {count + 1}. {self._format_dict_item(item)}")
                            count += 1
                    if len(list_value) > 100:
                        lines.append(f"  ... and {len(list_value) - 100} more items")
                else:
                    lines.append(f"{key}: {value}")
            else:
                lines.append(f"{key}: {value}")
        return "\n".join(lines)

    async def _execute_impl(self, inputs: NodeInputs) -> dict[str, Any]:
        data = inputs.get("data")
        role = str(self.params.get("role") or "user").lower()
        format_type = str(self.params.get("format") or "readable").lower()

        if role not in {"user", "assistant", "system", "tool"}:
            role = "user"

        if format_type not in {"json", "readable", "compact"}:
            format_type = "readable"

        # Convert data to string representation
        content = self._format_data(data, format_type)

        msg = {"role": role, "content": content}
        return {
            "message": msg,
        }
