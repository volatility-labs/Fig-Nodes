from typing import Dict, Any, List, Optional, AsyncGenerator
import os
import json
import asyncio
import random
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
    - assistant_text: str (progressive accumulated assistant text when streaming; final text when done)
    - assistant_message: Dict[str, Any] (final assistant message once available)
    - thinking: str (final thinking content if provided by model)
    - assistant_done: bool (False while streaming partials; True on final)
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
        "assistant_text": str,
        "assistant_message": get_type("LLMChatMessage"),
        "thinking": str,
        "assistant_done": bool,
        "metrics": get_type("LLMChatMetrics"),
    }

    # Mark as data_source category so default Base UI does not display inline output
    CATEGORY = 'data_source'

    default_params = {
        "stream": True,
        "format": "",  # "" | "json"
        "options": "",  # JSON string of options, passthrough (hidden from UI)
        "keep_alive": "1h",
        "think": False,
        # Exposed controls
        "temperature": 0.7,
        "seed": 0,
        "seed_mode": "fixed",  # fixed | random | increment
    }

    params_meta = [
        {"name": "stream", "type": "combo", "default": True, "options": [True, False]},
        {"name": "format", "type": "combo", "default": "", "options": ["", "json"]},
        # Hidden from UI: options and keep_alive are supported internally but not user-facing
        {"name": "temperature", "type": "number", "default": 0.7},
        {"name": "seed_mode", "type": "combo", "default": "fixed", "options": ["fixed", "random", "increment"]},
        {"name": "seed", "type": "number", "default": 0},
        {"name": "think", "type": "combo", "default": False, "options": [False, True]},
    ]

    ui_module = "OllamaChatNodeUI"

    def __init__(self, id: int, params: Dict[str, Any] = None):
        super().__init__(id, params)
        self._cancel_event = asyncio.Event()
        # Mark optional inputs at runtime for validation layer
        self.optional_inputs = ["tools", "messages", "prompt", "system"]
        # Maintain seed state when using increment mode across runs
        self._seed_state: Optional[int] = None

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
            options = self._parse_options() or {}

            # Apply temperature
            try:
                temperature_raw = self.params.get("temperature")
                if temperature_raw is not None:
                    options["temperature"] = float(temperature_raw)
            except Exception:
                pass

            # Determine effective seed according to seed_mode
            seed_mode = str(self.params.get("seed_mode") or "fixed").strip().lower()
            seed_raw = self.params.get("seed")
            effective_seed: Optional[int] = None
            try:
                base_seed = int(seed_raw) if seed_raw is not None else 0
            except Exception:
                base_seed = 0

            if seed_mode == "random":
                effective_seed = random.randint(0, 2**31 - 1)
            elif seed_mode == "increment":
                if self._seed_state is None:
                    self._seed_state = base_seed
                effective_seed = self._seed_state
                self._seed_state += 1
            else:  # fixed
                effective_seed = base_seed

            options["seed"] = int(effective_seed)

            # Lazy import to keep dependency local to node
            from ollama import AsyncClient

            client = AsyncClient(host=host)

            accumulated_content: List[str] = []
            accumulated_thinking: List[str] = []
            final_message: Dict[str, Any] = {}
            metrics: Dict[str, Any] = {}

            if use_stream:
                last_resp: Dict[str, Any] = {}
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
                    last_resp = part or {}
                    msg = last_resp.get("message") or {}
                    content_piece = msg.get("content")
                    if content_piece:
                        accumulated_content.append(content_piece)
                    thinking_piece = msg.get("thinking")
                    if isinstance(thinking_piece, str) and thinking_piece:
                        accumulated_thinking.append(thinking_piece)
                    # Emit progressive accumulated assistant_text only
                    if accumulated_content:
                        yield {"assistant_text": "".join(accumulated_content), "assistant_done": False}
                # Build final message and metrics from the streamed parts
                final_message = (last_resp.get("message") if isinstance(last_resp, dict) else {}) or {}
                # Collect metrics when available from the last streamed object
                for k in ("total_duration", "load_duration", "prompt_eval_count", "prompt_eval_duration", "eval_count", "eval_duration"):
                    if isinstance(last_resp, dict) and k in last_resp:
                        metrics[k] = last_resp[k]
                # Surface generation parameters used
                metrics["seed"] = int(effective_seed) if effective_seed is not None else None
                if "temperature" in options:
                    metrics["temperature"] = options["temperature"]
                # Ensure final content is the concatenation of all streamed content
                final_content = "".join(accumulated_content)
                if not isinstance(final_message, dict):
                    final_message = {}
                if final_content:
                    final_message["content"] = final_content
                # Prefer final thinking from message; otherwise join accumulated
                thinking_final: str = ""
                if isinstance(final_message.get("thinking"), str):
                    thinking_final = final_message.get("thinking") or ""
                elif accumulated_thinking:
                    thinking_final = "".join(accumulated_thinking)
                yield {
                    "assistant_text": final_content,
                    "assistant_message": final_message,
                    "thinking": thinking_final,
                    "assistant_done": True,
                    "metrics": metrics,
                }
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
                # Surface generation parameters used
                metrics["seed"] = int(effective_seed) if effective_seed is not None else None
                if "temperature" in options:
                    metrics["temperature"] = options["temperature"]
                thinking_final: str = ""
                if isinstance(final_message.get("thinking"), str):
                    thinking_final = final_message.get("thinking") or ""
                yield {
                    "assistant_text": final_message.get("content") or "",
                    "assistant_message": final_message,
                    "thinking": thinking_final,
                    "assistant_done": True,
                    "metrics": metrics,
                }
        except Exception as e:
            # Surface error to UI via metrics field
            yield {"metrics": {"error": str(e)}}


