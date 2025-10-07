from typing import Dict, Any, List, Optional, AsyncGenerator, Union
import os
import json
import asyncio
import random
import httpx
from nodes.base.streaming_node import StreamingNode
import subprocess as sp


from core.types_registry import get_type
from services.tools.registry import get_tool_handler, get_all_credential_providers


class OllamaChatNode(StreamingNode):
    """
    Streaming chat node backed by a local Ollama server.

    Constraints:
    - Does not pull/download models. Users manage models with the Ollama CLI.

    Inputs:
    - host: str
    - model: str (e.g., "llama3.2:latest")
    - messages: List[Dict[str, Any]] (chat history with role, content, etc.)
    - prompt: str
    - system: str
    - tools: Dict[str, Any] (optional tool schema, supports multi-input and list inputs)

    Outputs:
    - message: Dict[str, Any] (assistant message with role, content, thinking, tool_calls, etc.)
    - metrics: Dict[str, Any] (generation stats like durations and token counts)

    In streaming mode (default), start() yields progressive dicts:
    - Partial: {"message": dict (with accumulating content), "done": False}
    - Final: {"message": dict, "metrics": dict, "done": True}

    Note: Streaming mode is currently in beta and may be unstable.
    """

    inputs = {
        "messages": get_type("LLMChatMessageList"),
        "prompt": str,
        "system": Union[str, get_type("LLMChatMessage")],
        "tools": get_type("LLMToolSpec"),  # Tool schemas (supports multi-input and lists)
    }

    outputs = {
        "message": Dict[str, Any],
        "metrics": get_type("LLMChatMetrics"),
        "tool_history": get_type("LLMToolHistory"),
        "thinking_history": get_type("LLMThinkingHistory"),
    }

    # Common metric keys returned by Ollama responses/stream parts
    METRIC_KEYS = (
        "total_duration",
        "load_duration",
        "prompt_eval_count",
        "prompt_eval_duration",
        "eval_count",
        "eval_duration",
    )

    # Mark as data_source category so default Base UI does not display inline output
    CATEGORY = 'data_source'

    default_params = {
        "options": "",  # JSON string of options, passthrough (hidden from UI)
        "keep_alive": 0,
        "think": False,
        # Exposed controls
        "temperature": 0.7,
        "seed": 0,
        "seed_mode": "fixed",  # fixed | random | increment
        # Tool orchestration controls
        "max_tool_iters": 2,
        "tool_timeout_s": 10,
        "host": os.getenv("OLLAMA_HOST", "http://localhost:11434"),
        "selected_model": "",
    }

    # Update params_meta:
    params_meta = [
        {"name": "host", "type": "text", "default": os.getenv("OLLAMA_HOST", "http://localhost:11434")},
        {"name": "selected_model", "type": "combo", "default": "", "options": []},
        {"name": "temperature", "type": "number", "default": 0.7, "min": 0.0, "max": 1.5, "step": 0.05},
        {"name": "seed", "type": "number", "default": 0, "min": 0, "step": 1, "precision": 0},
        {"name": "max_tool_iters", "type": "number", "default": 2, "min": 0, "step": 1, "precision": 0},
        {"name": "tool_timeout_s", "type": "number", "default": 10, "min": 0, "step": 1, "precision": 0},
        {"name": "seed_mode", "type": "combo", "default": "fixed", "options": ["fixed", "random", "increment"]},
        {"name": "think", "type": "combo", "default": False, "options": [False, True]},
        {"name": "json_mode", "type": "combo", "default": False, "options": [False, True]},
 
    ]

    ui_module = "OllamaChatNodeUI"

    def __init__(self, id: int, params: Dict[str, Any] = None):
        super().__init__(id, params)
        self._cancel_event = asyncio.Event()
        # Mark optional inputs at runtime for validation layer
        self.optional_inputs = ["tools", "tool", "messages", "prompt", "system"]
        # Maintain seed state when using increment mode across runs
        self._seed_state: Optional[int] = None
        # Track client to allow explicit close on stop
        self._client = None
        # Track last used model/host for CLI stop/unload
        self._last_model: Optional[str] = None
        self._last_host: Optional[str] = None
        # Cache resolved model context windows per (host, model)
        self._model_ctx_cache: Dict[str, int] = {}

    async def _resolve_max_context(self, host: str, model: str) -> Optional[int]:
        """
        Query Ollama /api/show to determine model max context window.
        Returns None if unavailable. Caches per host+model string key.
        """
        if not isinstance(host, str) or not isinstance(model, str) or not host:
            return None
        cache_key = f"{host}::{model}"
        if cache_key in self._model_ctx_cache:
            try:
                cached = int(self._model_ctx_cache[cache_key])
                if cached > 0:
                    return cached
            except Exception:
                pass
        try:
            # Keep timeout small to avoid slowing tests/runs when server is absent
            async with httpx.AsyncClient(timeout=1.0) as client:
                _post_call = client.post(f"{host}/api/show", json={"model": model, "verbose": True})
                # Support both sync and async client methods
                if asyncio.iscoroutine(_post_call):
                    r = await _post_call
                else:
                    r = _post_call
                # Some tests mock httpx to return AsyncMocks; support both sync and async methods
                try:
                    _rs = r.raise_for_status()
                    if asyncio.iscoroutine(_rs):
                        await _rs
                except Exception:
                    pass
                _data = r.json()
                if asyncio.iscoroutine(_data):
                    _data = await _data
                data = _data or {}
            candidates: List[int] = []
            model_info = data.get("model_info") or {}
            if isinstance(model_info, dict):
                for k, v in model_info.items():
                    if isinstance(k, str) and "context_length" in k and isinstance(v, int):
                        candidates.append(v)
            # Fallback: parse parameters string for num_ctx
            params_txt = data.get("parameters")
            if isinstance(params_txt, str):
                for line in params_txt.splitlines():
                    line = line.strip()
                    if line.startswith("num_ctx"):
                        parts = line.split()
                        if len(parts) >= 2:
                            try:
                                candidates.append(int(parts[1]))
                            except Exception:
                                pass
            if candidates:
                max_ctx = max(candidates)
                if isinstance(max_ctx, int) and max_ctx > 0:
                    self._model_ctx_cache[cache_key] = int(max_ctx)
                    return int(max_ctx)
        except Exception as e:
            print(f"OllamaChatNode: Error resolving context for model '{model}': {e}")
        return None

    async def _apply_context_window(self, host: str, model: str, options: Dict[str, Any]) -> Dict[str, Any]:
        """
        Ensure options.num_ctx does not exceed the model's maximum context window.
        If user did not supply num_ctx, set it to the maximum.
        """
        if not isinstance(options, dict):
            return options
        max_ctx = await self._resolve_max_context(host, model)
        if isinstance(max_ctx, int) and max_ctx > 0:
            user_ctx = options.get("num_ctx")
            try:
                user_ctx_int = int(user_ctx) if user_ctx is not None else None
            except Exception:
                user_ctx_int = None
            if user_ctx_int is None or user_ctx_int <= 0:
                options["num_ctx"] = max_ctx
            else:
                options["num_ctx"] = min(user_ctx_int, max_ctx)
        return options

    @staticmethod
    def _build_messages(existing_messages: Optional[List[Dict[str, Any]]], prompt: Optional[str], system_input: Optional[Any]) -> List[Dict[str, Any]]:
        """
        Construct a messages array compliant with Ollama chat API from either:
        - existing structured messages
        - a plain-text prompt (as a user role message)
        - both (prompt appended to existing)
        """
        result = list(existing_messages or [])
        if system_input and not any(m.get("role") == "system" for m in result):
            if isinstance(system_input, str):
                result.insert(0, {"role": "system", "content": system_input})
            elif isinstance(system_input, dict):
                result.insert(0, system_input)
        if prompt:
            result.append({"role": "user", "content": prompt})
        return result

    def _collect_tools(self, inputs: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Collect and combine tools from both 'tools' (list) and 'tool' (single/multi) inputs.
        """
        result: List[Dict[str, Any]] = []

        # Add tools from the 'tools' input (list)
        tools_list = inputs.get("tools")
        if tools_list and isinstance(tools_list, list):
            result.extend(tools_list)

        # Add tools from the 'tool' multi-input
        for tool_spec in self.collect_multi_input("tool", inputs):
            if isinstance(tool_spec, dict) and tool_spec.get("type") == "function":
                result.append(tool_spec)

        return result

    def stop(self):
        self._cancel_event.set()
        # Proactively close client to abort pending requests
        client = getattr(self, "_client", None)
        if client is not None:
            try:
                close = getattr(client, "close", None)
                if close is not None:
                    try:
                        coro = close()
                        if asyncio.iscoroutine(coro):
                            asyncio.create_task(coro)
                    except TypeError:
                        try:
                            close()
                        except Exception:
                            pass
            except Exception:
                pass
        # Forcefully unload the model from Ollama via CLI to free VRAM
        try:
            self._unload_model_via_cli()
        except Exception:
            # Never raise on stop path
            pass

    def interrupt(self):
        # Only signal cancellation to break out of blocking operations.
        # Cleanup is handled by stop() which is invoked by force_stop.
        self._cancel_event.set()

    def _unload_model_via_cli(self) -> None:
        """Spawn a non-blocking CLI call to `ollama stop &lt;model&gt;` using last known host."""
        model = getattr(self, "_last_model", None)
        if not model or not isinstance(model, str):
            return
        host = getattr(self, "_last_host", None) or os.environ.get("OLLAMA_HOST")
        env = os.environ.copy()
        if host:
            env["OLLAMA_HOST"] = host
        try:
            # Fire-and-forget to avoid blocking stop() path
            sp.Popen(["ollama", "stop", model], env=env, stdout=sp.DEVNULL, stderr=sp.DEVNULL)
        except Exception:
            # Swallow any errors (e.g., CLI not installed)
            pass

        # Force kill the Ollama server process on Mac or Linux after a short delay
        import sys
        from urllib.parse import urlparse
        if sys.platform in ('darwin', 'linux'):
            port = '11434'
            if host and isinstance(host, str):
                try:
                    parsed = urlparse(host if host.startswith('http') else f'http://{host}')
                    if parsed.port:
                        port = str(parsed.port)
                except Exception:
                    pass
            try:
                cmd = f'sleep 2; pid=$(lsof -ti :{port}); [ -n "$pid" ] && kill -9 $pid'
                sp.Popen(['/bin/sh', '-c', cmd], stdout=sp.DEVNULL, stderr=sp.DEVNULL)
            except Exception:
                pass

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

    def _get_effective_host(self, inputs: Optional[Dict[str, Any]]) -> str:
        """Resolve host with precedence: inputs -> params -> env -> default."""
        return (
            (inputs.get("host") if isinstance(inputs, dict) else None)
            or self.params.get("host")
            or os.environ.get("OLLAMA_HOST", "http://localhost:11434")
        )

    def _get_keep_alive_value(self) -> Optional[Any]:
        """Preserve explicit 0 and duration strings; only None/empty -> None."""
        _keep_alive_param = self.params.get("keep_alive")
        return _keep_alive_param if (_keep_alive_param is not None and _keep_alive_param != "") else None

    def _get_format_value(self) -> Optional[str]:
        """Derive Ollama format from json_mode toggle."""
        return "json" if bool(self.params.get("json_mode", False)) else None

    def _prepare_generation_options(self) -> (Dict[str, Any], Optional[int]):
        """Build options dict including temperature and seed based on params.
        Returns (options, effective_seed).
        """
        options: Dict[str, Any] = self._parse_options() or {}

        # Temperature
        try:
            temperature_raw = self.params.get("temperature")
            if temperature_raw is not None:
                options["temperature"] = float(temperature_raw)
        except Exception:
            pass

        # Seed according to seed_mode
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
        return options, effective_seed

    def _ensure_assistant_role_inplace(self, message: Dict[str, Any]) -> None:
        if isinstance(message, dict) and "role" not in message:
            message["role"] = "assistant"

    def _update_metrics_from_source(self, metrics: Dict[str, Any], source: Dict[str, Any]) -> None:
        if not isinstance(metrics, dict) or not isinstance(source, dict):
            return
        for k in self.METRIC_KEYS:
            if k in source:
                metrics[k] = source[k]

    async def _get_model(self, host: str, model_from_input: Optional[str]) -> str:
        if model_from_input:
            return model_from_input

        print(f"OllamaChatNode: Querying models from {host}/api/tags")
        models_list: List[str] = []

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                _get_call = client.get(f"{host}/api/tags")
                # Support both sync and async client methods
                if asyncio.iscoroutine(_get_call):
                    r = await _get_call
                else:
                    r = _get_call
                try:
                    _rs = r.raise_for_status()
                    if asyncio.iscoroutine(_rs):
                        await _rs
                except Exception:
                    pass
                _data = r.json()
                if asyncio.iscoroutine(_data):
                    _data = await _data
                data = _data
                models_list = [m.get("name") for m in data.get("models", []) if m.get("name")]
            print(f"OllamaChatNode: Found {len(models_list)} models: {models_list}")
        except Exception as e:
            print(f"OllamaChatNode: Error querying Ollama models: {e}")

        # Update params_meta options dynamically for UI consumption via /nodes metadata
        for p in self.params_meta:
            if p["name"] == "selected_model":
                p["options"] = models_list
                break

        selected = self.params.get("selected_model") or ""

        if (not selected or selected not in models_list) and models_list:
            selected = models_list[0]
            print(f"OllamaChatNode: Auto-selected first model: {selected}")

        if not selected and not models_list:
            error_msg = "No local Ollama models found. Pull one via 'ollama pull <model>'"
            print(f"OllamaChatNode: ERROR - {error_msg}")
            raise ValueError(error_msg)
        elif selected and selected not in models_list:
            print(f"OllamaChatNode: WARNING - Selected model '{selected}' not in available models {models_list}")

        print(f"OllamaChatNode: Using model '{selected}'")
        return selected

    def _message_to_dict(self, message) -> Dict[str, Any]:
        """Convert Ollama Message object to dict format."""
        result = {
            "role": getattr(message, "role", "assistant"),
            "content": getattr(message, "content", ""),
        }
        # Handle optional attributes
        for attr in ["thinking", "images", "tool_calls", "tool_name"]:
            if hasattr(message, attr):
                value = getattr(message, attr)
                if value is not None:
                    if attr == "tool_calls" and isinstance(value, list):
                        # Convert ToolCall objects to dicts
                        result[attr] = [self._tool_call_to_dict(tc) for tc in value]
                    else:
                        result[attr] = value
        return result

    def _tool_call_to_dict(self, tool_call) -> Dict[str, Any]:
        """Convert Ollama ToolCall object to dict format."""
        if hasattr(tool_call, 'function'):
            func = tool_call.function
            return {
                "function": {
                    "name": getattr(func, 'name', ''),
                    "arguments": getattr(func, 'arguments', {}),
                }
            }
        return {}

    async def _maybe_execute_tools_and_augment_messages(self, host: str, model: str, base_messages: List[Dict[str, Any]], tools: Optional[List[Dict[str, Any]]], fmt: Optional[str], options: Dict[str, Any], keep_alive: Optional[Any], think: bool, client_factory=None) -> Dict[str, Any]:
        """
        Orchestrate tool-calling rounds until no tool_calls are present or max iterations reached.
        Returns a dict with keys: messages (final history), last_response (last non-streaming chat response), metrics (aggregated), tool_history (list of tool calls and results), thinking_history (list of thinking strings).
        """
        # No tools attached; nothing to orchestrate
        if not tools or not isinstance(tools, list):
            return {"messages": base_messages, "last_response": None, "metrics": {}}

        max_iters = int(self.params.get("max_tool_iters", 2) or 0)
        timeout_s = int(self.params.get("tool_timeout_s", 10) or 10)

        # Lazy import for client if not provided
        if client_factory is None:
            from ollama import AsyncClient
            client_factory = lambda: AsyncClient(host=host)

        messages = list(base_messages)
        combined_metrics: Dict[str, Any] = {}
        tool_history: List[Dict[str, Any]] = []
        thinking_history: List[Dict[str, Any]] = []

        async def _invoke_chat_nonstream(_client):
            return await _client.chat(
                model=model,
                messages=messages,
                tools=tools,
                stream=False,
                format=fmt,
                options=options,
                keep_alive=keep_alive,
                think=think,
            )

        # Iterate tool rounds
        last_resp: Optional[Dict[str, Any]] = None
        for _round in range(max(0, max_iters) + 1):
            client = client_factory()
            try:
                resp = await _invoke_chat_nonstream(client)
            finally:
                try:
                    await client.close()
                except Exception:
                    pass

            last_resp = resp or {}
            # Merge metrics if present
            for k in ("total_duration", "load_duration", "prompt_eval_count", "prompt_eval_duration", "eval_count", "eval_duration"):
                if k in (resp or {}):
                    combined_metrics[k] = (resp or {}).get(k)

            message = (resp or {}).get("message") or {}
            # Convert Message object to dict if needed
            if hasattr(message, 'role'):  # It's a Message object
                message = self._message_to_dict(message)
            # Handle both dict (from API) and Message object (from Ollama client)
            tool_calls = message.get("tool_calls") if isinstance(message, dict) else None

            # Collect thinking if present
            thinking = message.get("thinking")
            if thinking and isinstance(thinking, str):
                thinking_history.append({"thinking": thinking, "iteration": _round})

            # If no tool calls, stop and keep last response
            if not tool_calls or not isinstance(tool_calls, list):
                break

            # Execute tool calls and append tool results
            for call in tool_calls:
                try:
                    fn = (call or {}).get("function") or {}
                    tool_name = fn.get("name")
                    arguments = fn.get("arguments") or {}
                    if not isinstance(arguments, dict):
                        arguments = {}

                    handler = get_tool_handler(tool_name) if isinstance(tool_name, str) else None
                    result_obj: Any = None

                    async def _run_handler():
                        if handler is None:
                            return {"error": "unknown_tool", "message": f"No handler for tool '{tool_name}'"}
                        ctx = {
                            "model": model,
                            "host": host,
                            "credentials": get_all_credential_providers()
                        }
                        return await handler(arguments, ctx)

                    try:
                        result_obj = await asyncio.wait_for(_run_handler(), timeout=timeout_s)
                    except asyncio.TimeoutError:
                        result_obj = {"error": "timeout", "message": f"Tool '{tool_name}' timed out after {timeout_s}s"}
                    except Exception as _e:
                        result_obj = {"error": "exception", "message": str(_e)}

                    # Ensure JSON-serializable content; fallback to str
                    try:
                        content_str = json.dumps(result_obj, ensure_ascii=False)
                    except Exception:
                        content_str = str(result_obj)

                    messages.append({
                        "role": "tool",
                        "tool_name": tool_name,
                        "content": content_str,
                    })

                    # Collect tool history
                    tool_history.append({"call": call, "result": result_obj})
                except Exception as _e_outer:
                    # Append an error tool message to allow model to recover
                    messages.append({
                        "role": "tool",
                        "tool_name": str((call or {}).get("function", {}).get("name", "unknown")),
                        "content": json.dumps({"error": "handler_failure", "message": str(_e_outer)}),
                    })

            # After appending tool outputs, continue loop to call chat again

        return {"messages": messages, "last_response": last_resp, "metrics": combined_metrics, "tool_history": tool_history, "thinking_history": thinking_history}

    async def start(self, inputs: Dict[str, Any]) -> AsyncGenerator[Dict[str, Any], None]:
        try:
            # Prefer host/model from inputs when provided
            host = self._get_effective_host(inputs)
            input_model = (inputs.get("model") if isinstance(inputs, dict) else None)
            model: str = await self._get_model(host, input_model)
            self._last_host = host
            self._last_model = model
            raw_messages: Optional[List[Dict[str, Any]]] = inputs.get("messages")
            prompt_text: Optional[str] = inputs.get("prompt")
            system_input: Optional[Any] = inputs.get("system")
            messages: List[Dict[str, Any]] = self._build_messages(raw_messages, prompt_text, system_input)
            tools: List[Dict[str, Any]] = self._collect_tools(inputs)

            print(f"OllamaChatNode: Received inputs - model='{model}', host='{host}', prompt='{prompt_text}', messages_count={len(raw_messages) if raw_messages else 0}")

            # Derive format/keep-alive from helpers and build options/seed
            fmt: Optional[str] = self._get_format_value()
            keep_alive = self._get_keep_alive_value()
            think = bool(self.params.get("think", False))
            options, effective_seed = self._prepare_generation_options()

            print(f"OllamaChatNode: Using host={host}, messages={len(messages)}")
            # Validate we have something to send (model always set now)
            if not messages and not prompt_text:
                error_msg = "No messages or prompt provided to OllamaChatNode"
                print(f"OllamaChatNode: ERROR - {error_msg}")
                error_message = {"role": "assistant", "content": ""}
                yield {"message": error_message, "metrics": {"error": error_msg}}
                return

            # Lazy import to keep dependency local to node
            from ollama import AsyncClient

            # Auto-detect and apply model context window (clamp num_ctx)
            # Only perform network lookup when 'messages' are provided; skip for prompt-only inputs
            try:
                if isinstance(inputs, dict) and inputs.get("messages"):
                    options = await self._apply_context_window(host, model, options)
            except Exception:
                pass

            metrics: Dict[str, Any] = {}

            # Tool orchestration if needed
            tool_rounds_info = {"messages": messages, "last_response": None, "metrics": {}, "tool_history": [], "thinking_history": []}
            if tools:
                tool_rounds_info = await self._maybe_execute_tools_and_augment_messages(
                    host, model, messages, tools, fmt, options, keep_alive, think
                )
                messages = tool_rounds_info.get("messages", messages)
                # Update metrics
                t_metrics = tool_rounds_info.get("metrics") or {}
                if isinstance(t_metrics, dict):
                    metrics.update(t_metrics)

            # Final non-streaming call without tools (tool orchestration should have resolved them)
            print(f"OllamaChatNode: Creating Ollama client for {host}")
            client = AsyncClient(host=host)
            self._client = client
            # Cooperative cancellation for non-streaming call inside start()
            chat_task = asyncio.create_task(client.chat(
                model=model,
                messages=messages,
                tools=None,  # Don't pass tools to final call
                stream=False,
                format=fmt,
                options=options,
                keep_alive=keep_alive,
                think=think,
            ))
            cancel_wait = asyncio.create_task(self._cancel_event.wait())
            done, pending = await asyncio.wait({chat_task, cancel_wait}, return_when=asyncio.FIRST_COMPLETED)
            if cancel_wait in done and chat_task not in done:
                try:
                    chat_task.cancel()
                except Exception:
                    pass
                try:
                    await asyncio.wait({chat_task}, timeout=0.05)
                except Exception:
                    pass
                try:
                    await client.close()
                except Exception:
                    pass
                try:
                    self._unload_model_via_cli()
                except Exception:
                    pass
                partial_message = {"role": "assistant", "content": ""}
                yield {"message": partial_message, "metrics": {"error": "Cancelled"}, "done": True}
                return
            resp = await chat_task
            final_message = (resp or {}).get("message") or {"role": "assistant", "content": ""}
            self._parse_content_if_json_mode(final_message, metrics)
            self._parse_tool_calls_from_message(final_message)
            # Ensure role is set
            self._ensure_assistant_role_inplace(final_message)
            self._update_metrics_from_source(metrics, resp)
            metrics["seed"] = int(effective_seed) if effective_seed is not None else None
            if "temperature" in options:
                metrics["temperature"] = options["temperature"]
            # Merge tool_rounds_info metrics
            t_metrics = tool_rounds_info.get("metrics") or {}
            if isinstance(t_metrics, dict):
                metrics.update(t_metrics)

            # Collect thinking from final message if present
            thinking_history = tool_rounds_info.get("thinking_history", [])
            thinking = final_message.get("thinking")
            if thinking and isinstance(thinking, str):
                thinking_history.append({"thinking": thinking, "iteration": 0})

            yield {"message": final_message, "metrics": metrics, "tool_history": tool_rounds_info.get("tool_history", []), "thinking_history": thinking_history, "done": True}
        except asyncio.CancelledError:
            # Cooperative cancellation; do not emit error on cancel
            return
        except Exception as e:
            error_message = {"role": "assistant", "content": ""}
            yield {"message": error_message, "metrics": {"error": str(e)}, "done": True}
        finally:
            self._cancel_event.clear()

    def _parse_tool_calls_from_message(self, message: Dict[str, Any]):
        """
        Parse tool calls from message content if using custom format.
        Updates the message in-place.
        """
        content = message.get("content", "")
        if isinstance(content, str):
            # Look for the custom tool call marker
            marker = "_TOOL_WEB_SEARCH_: "
            if marker in content:
                # Extract everything after the marker as the query
                query_start = content.find(marker) + len(marker)
                # Find the end of the tool call (look for next marker or end of content)
                query_end = content.find("_RESULT_:", query_start)
                if query_end == -1:
                    query_end = content.find("_TOOL_END_:", query_start)
                if query_end == -1:
                    query_end = len(content)

                query = content[query_start:query_end].strip()

                if query:
                    # Create the tool call in standard format
                    tool_call = {
                        "function": {
                            "name": "web_search",
                            "arguments": {"query": query}
                        }
                    }

                    # Initialize tool_calls list if not present
                    if "tool_calls" not in message:
                        message["tool_calls"] = []
                    # Add if not already present
                    if tool_call not in message["tool_calls"]:
                        message["tool_calls"].append(tool_call)

        # Set tool_name for backward compatibility if there are tool_calls
        if message.get("tool_calls"):
            complete_calls = [call for call in message["tool_calls"] if self._is_complete_tool_call(call)]
            if complete_calls:
                message["tool_name"] = complete_calls[0]["function"]["name"]
            else:
                message["tool_name"] = None
        else:
            message["tool_name"] = None

    async def execute(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        try:
            # Prefer host/model from inputs when provided
            host = self._get_effective_host(inputs)
            input_model = (inputs.get("model") if isinstance(inputs, dict) else None)
            model: str = await self._get_model(host, input_model)
            self._last_host = host
            self._last_model = model
            raw_messages: Optional[List[Dict[str, Any]]] = inputs.get("messages")
            prompt_text: Optional[str] = inputs.get("prompt")
            system_input: Optional[Any] = inputs.get("system")
            messages: List[Dict[str, Any]] = self._build_messages(raw_messages, prompt_text, system_input)
            tools: List[Dict[str, Any]] = self._collect_tools(inputs)

            print(f"OllamaChatNode: Execute - model='{model}', host='{host}', prompt='{prompt_text}', messages_count={len(raw_messages) if raw_messages else 0}")
            # Re-affirm host using same precedence (inputs -> params -> env)
            host: str = self._get_effective_host(inputs)
            # Track last used model/host for stop/unload
            self._last_model = model
            self._last_host = host
            # Force non-streaming for execute()
            fmt: Optional[str] = self._get_format_value()
            keep_alive = self._get_keep_alive_value()
            think = bool(self.params.get("think", False))
            options, effective_seed = self._prepare_generation_options()

            # Validate we have something to send (model always set now)
            if not messages and not prompt_text:
                error_msg = "No messages or prompt provided to OllamaChatNode"
                error_message = {"role": "assistant", "content": ""}
                return {"message": error_message, "metrics": {"error": error_msg}, "tool_history": [], "thinking_history": []}

            # effective_seed produced by helper above

            from ollama import AsyncClient

            # Tool orchestration if needed
            tool_rounds_info = {"messages": messages, "last_response": None, "metrics": {}, "tool_history": [], "thinking_history": []}
            if tools:
                tool_rounds_info = await self._maybe_execute_tools_and_augment_messages(
                    host, model, messages, tools, fmt, options, keep_alive, think
                )
                messages = tool_rounds_info.get("messages", messages)

            client = AsyncClient(host=host)
            self._client = client
            try:
                # Auto-detect and apply model context window (clamp num_ctx) for execute()
                # Only perform network lookup when 'messages' are provided; skip for prompt-only inputs
                try:
                    if isinstance(inputs, dict) and inputs.get("messages"):
                        options = await self._apply_context_window(host, model, options)
                except Exception:
                    pass
                # Cooperative cancellation for non-streaming execute()
                chat_task = asyncio.create_task(client.chat(
                    model=model,
                    messages=messages,
                    tools=None,  # Tools already orchestrated
                    stream=False,
                    format=fmt,
                    options=options,
                    keep_alive=keep_alive,
                    think=think,
                ))
                cancel_wait = asyncio.create_task(self._cancel_event.wait())
                done, pending = await asyncio.wait({chat_task, cancel_wait}, return_when=asyncio.FIRST_COMPLETED)
                if cancel_wait in done and chat_task not in done:
                    try:
                        chat_task.cancel()
                    except Exception:
                        pass
                    try:
                        await asyncio.wait({chat_task}, timeout=0.05)
                    except Exception:
                        pass
                    try:
                        await client.close()
                    except Exception:
                        pass
                    try:
                        self._unload_model_via_cli()
                    except Exception:
                        pass
                    raise asyncio.CancelledError()
                resp = await chat_task
                final_message = (resp or {}).get("message") or {"role": "assistant", "content": ""}
                # Ensure role is set
                self._ensure_assistant_role_inplace(final_message)
                metrics: Dict[str, Any] = {}
                self._parse_content_if_json_mode(final_message, metrics)
                self._parse_tool_calls_from_message(final_message)

                self._update_metrics_from_source(metrics, resp)
                metrics["seed"] = int(effective_seed) if effective_seed is not None else None
                if "temperature" in options:
                    metrics["temperature"] = options["temperature"]
                # Merge tool_rounds_info metrics
                t_metrics = tool_rounds_info.get("metrics") or {}
                if isinstance(t_metrics, dict):
                    metrics.update(t_metrics)

                # Collect thinking from final message if present
                thinking_history = tool_rounds_info.get("thinking_history", [])
                thinking = final_message.get("thinking")
                if thinking and isinstance(thinking, str):
                    thinking_history.append({"thinking": thinking, "iteration": 0})

                return {
                    "message": final_message,
                    "metrics": metrics,
                    "tool_history": tool_rounds_info.get("tool_history", []),
                    "thinking_history": thinking_history
                }
            except asyncio.CancelledError:
                try:
                    await client.close()
                except Exception:
                    pass
                try:
                    self._unload_model_via_cli()
                except Exception:
                    pass
                self._client = None
                raise
            finally:
                try:
                    await client.close()
                except Exception:
                    pass
                self._client = None
        except asyncio.CancelledError:
            raise
        except ValueError:
            # Propagate model selection errors (e.g., no local models found)
            raise
        except Exception as e:
            error_message = {"role": "assistant", "content": ""}
            return {"message": error_message, "metrics": {"error": str(e)}, "tool_history": [], "thinking_history": []}

    def _parse_content_if_json_mode(self, message: Dict[str, Any], metrics: Dict[str, Any]) -> None:
        if bool(self.params.get("json_mode", False)):
            content_str = message.get("content", "")
            if isinstance(content_str, str):
                try:
                    parsed = json.loads(content_str)
                    message["content"] = parsed
                except json.JSONDecodeError as e:
                    metrics["parse_error"] = str(e)

    # _make_full_message no longer used for final outputs; kept for potential future use
    # def _make_full_message(self, base: Dict[str, Any]) -> Dict[str, Any]:
    #     return base
