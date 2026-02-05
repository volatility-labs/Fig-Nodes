import json
import logging
from typing import Any, TypeGuard

from core.types_registry import NodeCategory
from core.types_utils import detect_type, infer_data_type
from nodes.base.base_node import Base


def _is_dict_with_key(value: Any, key: str) -> TypeGuard[dict[str, Any]]:
    """Type guard to check if value is a dict with the specified key."""
    return isinstance(value, dict) and key in value


def _is_string(value: Any) -> TypeGuard[str]:
    """Type guard to check if value is a string."""
    return isinstance(value, str)


def _is_list_of_dicts(value: Any) -> TypeGuard[list[dict[str, Any]]]:
    """Type guard to check if value is a list of dicts."""
    if not isinstance(value, list):
        return False
    items: list[Any] = value
    return all(isinstance(item, dict) for item in items)


class Logging(Base):
    def __init__(
        self, id: int, params: dict[str, Any], graph_context: dict[str, Any] | None = None
    ):
        super().__init__(id, params, graph_context)
        self.last_content_length = 0
        self.logger = logging.getLogger(f"LoggingNode-{self.id}")

    CATEGORY = NodeCategory.IO
    inputs = {"input": Any | None}
    outputs = {"output": str}

    # Allow UI to select how to display/parse the output text
    default_params = {
        "format": "auto",  # one of: auto | plain | json | markdown
    }
    params_meta = [
        {
            "name": "format",
            "type": "combo",
            "default": "auto",
            "options": ["auto", "plain", "json", "markdown"],
        },
    ]

    async def _safe_print(self, message: str, end: str = "\n", flush: bool = False):
        """Non-blocking print that uses logging instead of stdout to avoid BlockingIOError."""
        try:
            # Use logging instead of print to avoid blocking on stdout
            self.logger.info(message.rstrip())
        except Exception:
            # Fallback to logging at root level if node-specific logger fails
            logging.getLogger().info(f"LoggingNode {self.id}: {message.rstrip()}")

    async def _execute_impl(self, inputs: dict[str, Any]) -> dict[str, Any]:
        value = inputs.get("input")

        # Handle missing or None input gracefully
        if value is None:
            await self._safe_print(f"LoggingNode {self.id}: (no input)")
            return {"output": "(no input)"}

        selected_format = str(self.params.get("format") or "auto").strip()

        # Use type detection utilities
        detected_type = detect_type(value)
        semantic_type = infer_data_type(value)

        # Handle LLMChatMessage - extract only the content
        if detected_type == "LLMChatMessage" and _is_dict_with_key(value, "content"):
            content = value["content"]
            if _is_string(content):
                text = content
                await self._safe_print(f"LoggingNode {self.id}: {text}")
            else:
                # Handle non-string content (e.g., tool calls)
                text = str(content)
                await self._safe_print(f"LoggingNode {self.id}: {text}")
        elif isinstance(value, dict) and "message" in value and isinstance(value["message"], dict):
            # Streaming message format
            streaming_value: dict[str, Any] = value
            message_dict: dict[str, Any] = streaming_value["message"]
            if (
                isinstance(message_dict.get("role"), str)
                and message_dict["role"] == "assistant"
                and isinstance(message_dict.get("content"), str)
            ):
                content: str = message_dict["content"]
                done_value: Any = streaming_value.get("done")
                is_partial = done_value is not True
                delta = content[self.last_content_length :]

                if delta:
                    await self._safe_print(delta, end="", flush=True)

                if not is_partial:
                    await self._safe_print("")  # Newline for final
                    if "thinking" in message_dict and isinstance(message_dict["thinking"], str):
                        await self._safe_print("Thinking:", message_dict["thinking"])
                    self.last_content_length = 0
                else:
                    self.last_content_length = len(content)

                text = content  # Full current text for output/UI
            else:
                text = str(streaming_value)
                await self._safe_print(f"LoggingNode {self.id}: {text}")
        elif semantic_type == "AssetSymbolList" and isinstance(value, list):
            symbol_list: list[Any] = value
            text = ", ".join(str(sym) for sym in symbol_list)
            await self._safe_print(text)
        elif semantic_type == "OHLCVBundle" and isinstance(value, dict):
            # OHLCVBundle data preview
            ohlcv_bundle: dict[str, Any] = value
            total_bars = 0
            for bundle_bars in ohlcv_bundle.values():
                if isinstance(bundle_bars, list):
                    typed_bars: list[Any] = bundle_bars
                    total_bars += len(typed_bars)
            symbol_count = len(ohlcv_bundle)
            text = f"OHLCVBundle data ({symbol_count} symbol(s), {total_bars} total bars):\n"
            preview_count = 0
            for sym, bars in list(ohlcv_bundle.items())[:3]:  # Show first 3 symbols
                if isinstance(bars, list) and bars:
                    bars_list: list[Any] = bars
                    preview_bars = min(3, len(bars_list))
                    text += f"  {sym} ({len(bars_list)} bars):\n"
                    for i, bar in enumerate(bars_list[:preview_bars]):
                        if isinstance(bar, dict) and all(
                            key in bar
                            for key in {"timestamp", "open", "high", "low", "close", "volume"}
                        ):
                            text += f"    Bar {i + 1}: {bar['timestamp']} O:{bar['open']} H:{bar['high']} L:{bar['low']} C:{bar['close']} V:{bar['volume']}\n"
                    if len(bars_list) > preview_bars:
                        text += f"    ... and {len(bars_list) - preview_bars} more bars\n"
                    preview_count += len(bars_list)
            if symbol_count > 3:
                text += f"  ... and {symbol_count - 3} more symbols"
            # Only print in debug mode to reduce log verbosity
            import os

            if os.getenv("DEBUG_LOGGING") == "1":
                await self._safe_print(f"LoggingNode {self.id}: {text}")
        elif semantic_type == "OHLCV" and _is_list_of_dicts(value):
            # Legacy OHLCV format (list) - should not happen but handle gracefully
            preview_count = min(10, len(value))
            text = f"OHLCV data ({len(value)} bars):\n"
            for i, bar in enumerate(value[:preview_count]):
                if all(
                    key in bar for key in {"timestamp", "open", "high", "low", "close", "volume"}
                ):
                    text += f"Bar {i + 1}: {bar['timestamp']} O:{bar['open']} H:{bar['high']} L:{bar['low']} C:{bar['close']} V:{bar['volume']}\n"
            if len(value) > preview_count:
                text += f"... and {len(value) - preview_count} more bars"
            # Only print in debug mode to reduce log verbosity
            import os

            if os.getenv("DEBUG_LOGGING") == "1":
                await self._safe_print(f"LoggingNode {self.id}: {text}")
        else:
            fallback_value: Any = value
            if selected_format == "json":
                # Produce a valid JSON string to enable UI pretty printing
                try:
                    if isinstance(fallback_value, str):
                        # If it's already a string, prefer parsing to validate; otherwise keep raw
                        try:
                            parsed = json.loads(fallback_value)
                            text = json.dumps(parsed, ensure_ascii=False)
                        except Exception:
                            # Fall back to serializing the original value if possible
                            text = json.dumps(fallback_value, ensure_ascii=False)
                    else:
                        text = json.dumps(fallback_value, ensure_ascii=False, default=str)
                except Exception:
                    text = str(fallback_value)
            else:
                # Prefer message.content if present to keep logging concise
                try:
                    if (
                        isinstance(fallback_value, dict)
                        and "message" in fallback_value
                        and isinstance(fallback_value["message"], dict)
                    ):
                        inner_dict: dict[str, Any] = fallback_value
                        inner: dict[str, Any] = inner_dict["message"]
                        content_value = inner.get("content")
                        if isinstance(content_value, str):
                            text = content_value
                        else:
                            text = str(inner_dict)
                    else:
                        original: Any = fallback_value
                        text = str(original)
                except Exception:
                    original_exc: Any = fallback_value
                    text = str(original_exc)
            await self._safe_print(f"LoggingNode {self.id}: {text}")

        return {"output": text}
