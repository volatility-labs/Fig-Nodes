from typing import Dict, Any, List, Optional, AsyncGenerator
import os
import json
import asyncio
from nodes.base.streaming_node import StreamingNode


from core.types_registry import get_type


class OllamaChatNode(StreamingNode):
    """
    Streaming chat node backed by a local Ollama server.

    Constraints:
    - Does not pull/download models. Users manage models with the Ollama CLI.

    Inputs:
    - model: str (e.g., "llama3.2:latest")
    - messages: List[Dict[str, Any]] (chat history objects with keys: role, content, images?)
    - tools (optional): List[Dict[str, Any]] (tool schemas for tool-calling)

    Outputs per tick:
    - delta: str (streamed text chunk if streaming)
    - assistant_message: Dict[str, Any] (final assistant message once available)
    - metrics: Dict[str, Any] (token counts/durations when provided)
    """

    inputs = {
        "host": str,
        "model": str,
        "messages": get_type("LLMChatMessageList"),
        "prompt": str,
        "system": str,
        "tools": get_type("LLMToolSpecList"),
    }

    outputs = {
        "delta": str,
        "assistant_message": get_type("LLMChatMessage"),
        "metrics": get_type("LLMChatMetrics"),
    }

    # Mark as data_source category so default Base UI does not display inline output
    CATEGORY = 'data_source'

    default_params = {
        "stream": True,
        "format": "",  # "" | "json"
        "options": "",  # JSON string of options, passthrough
        "keep_alive": "5m",
        "think": False,
    }

    params_meta = [
        {"name": "stream", "type": "combo", "default": True, "options": [True, False]},
        {"name": "format", "type": "combo", "default": "", "options": ["", "json"]},
        {"name": "options", "type": "textarea", "default": ""},
        {"name": "keep_alive", "type": "text", "default": "5m"},
        {"name": "think", "type": "combo", "default": False, "options": [False, True]},
    ]

    ui_module = "OllamaChatNodeUI"

    def __init__(self, id: int, params: Dict[str, Any] = None):
        super().__init__(id, params)
        self._cancel_event = asyncio.Event()
        # Mark optional inputs at runtime for validation layer
        self.optional_inputs = ["tools", "messages", "prompt", "system"]

    @staticmethod
    def _build_messages(existing_messages: Optional[List[Dict[str, Any]]], prompt: Optional[str], system_prompt: Optional[str]) -> List[Dict[str, Any]]:
        """
        Construct a messages array compliant with Ollama chat API from either:
        - existing structured messages
        - a plain-text prompt (as a user role message)
        - both (prompt appended to existing)
        """
        result: List[Dict[str, Any]] = []
        if existing_messages:
            # Shallow copy to avoid mutating caller-provided list
            result.extend(existing_messages)
        # Prepend/ensure a system message if provided and not already present
        if isinstance(system_prompt, str) and system_prompt.strip():
            has_system = any(isinstance(m, dict) and m.get("role") == "system" for m in result)
            if not has_system:
                result.insert(0, {"role": "system", "content": system_prompt})
        if isinstance(prompt, str) and prompt.strip():
            result.append({"role": "user", "content": prompt})
        return result

    def stop(self):
        self._cancel_event.set()

    def _parse_options(self) -> Optional[Dict[str, Any]]:
        raw = self.params.get("options")
        if not raw:
            return None
        if isinstance(raw, dict):
            return raw
        try:
            parsed = json.loads(raw)
            if isinstance(parsed, dict):
                return parsed
            return None
        except Exception:
            return None

    async def start(self, inputs: Dict[str, Any]) -> AsyncGenerator[Dict[str, Any], None]:
        try:
            model: str = inputs.get("model")
            raw_messages: Optional[List[Dict[str, Any]]] = inputs.get("messages")
            prompt_text: Optional[str] = inputs.get("prompt")
            system_prompt: Optional[str] = inputs.get("system")
            messages: List[Dict[str, Any]] = self._build_messages(raw_messages, prompt_text, system_prompt)
            tools: Optional[List[Dict[str, Any]]] = inputs.get("tools")

            if not model:
                return

            host: str = inputs.get("host") or os.getenv("OLLAMA_HOST", "http://localhost:11434")
            use_stream: bool = bool(self.params.get("stream", True))
            fmt: str = (self.params.get("format") or "").strip() or None
            keep_alive = self.params.get("keep_alive") or None
            think = bool(self.params.get("think", False))
            options = self._parse_options()

            # Lazy import to keep dependency local to node
            from ollama import AsyncClient

            client = AsyncClient(host=host)

            accumulated_content: List[str] = []
            final_message: Dict[str, Any] = {}
            metrics: Dict[str, Any] = {}

            if use_stream:
                async for part in await client.chat(
                    model=model,
                    messages=messages,
                    tools=tools,
                    stream=True,
                    format=fmt,
                    options=options,
                    keep_alive=keep_alive,
                    think=think,
                ):
                    if self._cancel_event.is_set():
                        break
                    msg = (part or {}).get("message") or {}
                    content_piece = msg.get("content")
                    if content_piece:
                        accumulated_content.append(content_piece)
                        yield {"delta": content_piece}
                # Get final response (non-stream call with history appended)
                resp = await client.chat(
                    model=model,
                    messages=messages,
                    tools=tools,
                    stream=False,
                    format=fmt,
                    options=options,
                    keep_alive=keep_alive,
                    think=think,
                )
                final_message = (resp or {}).get("message") or {}
                # Collect metrics when available
                for k in ("total_duration", "load_duration", "prompt_eval_count", "prompt_eval_duration", "eval_count", "eval_duration"):
                    if k in resp:
                        metrics[k] = resp[k]
                if accumulated_content and not final_message.get("content"):
                    final_message["content"] = "".join(accumulated_content)
                yield {"assistant_message": final_message, "metrics": metrics}
            else:
                resp = await client.chat(
                    model=model,
                    messages=messages,
                    tools=tools,
                    stream=False,
                    format=fmt,
                    options=options,
                    keep_alive=keep_alive,
                    think=think,
                )
                final_message = (resp or {}).get("message") or {}
                for k in ("total_duration", "load_duration", "prompt_eval_count", "prompt_eval_duration", "eval_count", "eval_duration"):
                    if k in resp:
                        metrics[k] = resp[k]
                yield {"assistant_message": final_message, "metrics": metrics}
        except Exception as e:
            # Surface error to UI via metrics field
            yield {"metrics": {"error": str(e)}}


