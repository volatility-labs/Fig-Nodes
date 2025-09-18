from typing import Dict, Any, List, Optional, AsyncGenerator
import os
import json
import asyncio
import random
from nodes.base.streaming_node import StreamingNode
import multiprocessing as mp
import signal


from core.types_registry import get_type
from services.tools.registry import get_tool_handler


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
    }

    params_meta = [
        {"name": "stream", "type": "combo", "default": True, "options": [True, False]},
        # Hidden from UI: options and keep_alive are supported internally but not user-facing
        {"name": "temperature", "type": "number", "default": 0.7},
        {"name": "seed_mode", "type": "combo", "default": "fixed", "options": ["fixed", "random", "increment"]},
        {"name": "seed", "type": "number", "default": 0},
        {"name": "think", "type": "combo", "default": False, "options": [False, True]},
        {"name": "max_tool_iters", "type": "number", "default": 2},
        {"name": "tool_timeout_s", "type": "number", "default": 10},
    ]

    ui_module = "OllamaChatNodeUI"

    def __init__(self, id: int, params: Dict[str, Any] = None):
        super().__init__(id, params)
        self._cancel_event = asyncio.Event()
        # Mark optional inputs at runtime for validation layer
        self.optional_inputs = ["tools", "messages", "prompt", "system"]
        # Maintain seed state when using increment mode across runs
        self._seed_state: Optional[int] = None
        # Track active stream iterator for cooperative shutdown
        self._active_stream = None
        # Track client to allow explicit close on stop
        self._client = None
        # Child-process based hard-stop support
        self._proc: Optional[mp.Process] = None
        self._ipc_parent = None

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
        # Best-effort cooperative close of active stream
        stream = getattr(self, "_active_stream", None)
        if stream is not None:
            try:
                aclose = getattr(stream, "aclose", None)
                if aclose is not None:
                    try:
                        coro = aclose()
                        if asyncio.iscoroutine(coro):
                            asyncio.create_task(coro)
                    except TypeError:
                        # aclose may be sync; just call it
                        try:
                            aclose()
                        except Exception:
                            pass
            except Exception:
                pass
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
        # Hard-stop: kill child process if running
        proc = getattr(self, "_proc", None)
        if proc is not None and proc.is_alive():
            try:
                proc.kill()
            except Exception:
                try:
                    os.kill(proc.pid, signal.SIGKILL)
                except Exception:
                    pass
            try:
                proc.join(timeout=0.5)
            except Exception:
                pass
        self._proc = None
        # Close IPC
        ipc = getattr(self, "_ipc_parent", None)
        if ipc is not None:
            try:
                ipc.close()
            except Exception:
                pass
        self._ipc_parent = None

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

    async def _maybe_execute_tools_and_augment_messages(self, host: str, model: str, base_messages: List[Dict[str, Any]], tools: Optional[List[Dict[str, Any]]], fmt: Optional[str], options: Dict[str, Any], keep_alive: Optional[Any], think: bool, client_factory=None) -> Dict[str, Any]:
        """
        Orchestrate tool-calling rounds until no tool_calls are present or max iterations reached.
        Returns a dict with keys: messages (final history), last_response (last non-streaming chat response), metrics (aggregated).
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
            tool_calls = message.get("tool_calls") if isinstance(message, dict) else None
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
                        ctx = {"model": model, "host": host}
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
                except Exception as _e_outer:
                    # Append an error tool message to allow model to recover
                    messages.append({
                        "role": "tool",
                        "tool_name": str((call or {}).get("function", {}).get("name", "unknown")),
                        "content": json.dumps({"error": "handler_failure", "message": str(_e_outer)}),
                    })

            # After appending tool outputs, continue loop to call chat again

        return {"messages": messages, "last_response": last_resp, "metrics": combined_metrics}

    async def start(self, inputs: Dict[str, Any]) -> AsyncGenerator[Dict[str, Any], None]:
        try:
            model: str = inputs.get("model")
            raw_messages: Optional[List[Dict[str, Any]]] = inputs.get("messages")
            prompt_text: Optional[str] = inputs.get("prompt")
            system_prompt: Optional[str] = inputs.get("system")
            messages: List[Dict[str, Any]] = self._build_messages(raw_messages, prompt_text, system_prompt)
            tools: Optional[List[Dict[str, Any]]] = inputs.get("tools")

            print(f"OllamaChatNode: Received inputs - model='{model}', prompt='{prompt_text}', messages_count={len(raw_messages) if raw_messages else 0}")

            if not model:
                error_msg = "No model provided to OllamaChatNode. Check model selector connection."
                print(f"OllamaChatNode: ERROR - {error_msg}")
                yield {"metrics": {"error": error_msg}, "assistant_text": "", "assistant_done": True}
                return

            host: str = inputs.get("host") or os.getenv("OLLAMA_HOST", "http://localhost:11434")
            use_stream: bool = bool(self.params.get("stream", True))
            # Derive Ollama format from json_mode toggle (True -> "json", False -> None)
            fmt: str = "json" if bool(self.params.get("json_mode", False)) else None
            # Preserve explicit 0 (unload immediately) and duration strings; only None/"" -> None
            _keep_alive_param = self.params.get("keep_alive")
            keep_alive = _keep_alive_param if (_keep_alive_param is not None and _keep_alive_param != "") else None
            think = bool(self.params.get("think", False))
            options = self._parse_options() or {}

            print(f"OllamaChatNode: Using host={host}, stream={use_stream}, messages={len(messages)}")

            # Validate we have something to send
            if not messages and not prompt_text:
                error_msg = "No messages or prompt provided to OllamaChatNode"
                print(f"OllamaChatNode: ERROR - {error_msg}")
                yield {"metrics": {"error": error_msg}, "assistant_text": "", "assistant_done": True}
                return

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

            accumulated_content: List[str] = []
            accumulated_thinking: List[str] = []
            final_message: Dict[str, Any] = {}
            metrics: Dict[str, Any] = {}

            try:
                # If tools are provided, first orchestrate non-streaming rounds until no tool calls
                tool_rounds_info = {"messages": messages, "last_response": None, "metrics": {}}
                if tools:
                    tool_rounds_info = await self._maybe_execute_tools_and_augment_messages(
                        host, model, messages, tools, fmt, options, keep_alive, think
                    )
                    messages = tool_rounds_info.get("messages", messages)
                    # Carry over metrics if available
                    t_metrics = tool_rounds_info.get("metrics") or {}
                    if isinstance(t_metrics, dict):
                        metrics.update(t_metrics)

                if use_stream:
                    print(f"OllamaChatNode: Starting streaming chat with model={model}")
                    # Child-process based streaming for hard kill capability
                    parent_conn, child_conn = mp.Pipe(duplex=False)
                    self._ipc_parent = parent_conn

                    def _worker(conn, w_host, w_model, w_messages, w_tools, w_format, w_options, w_keep_alive, w_think):
                        import asyncio as _a
                        try:
                            from ollama import AsyncClient as _Client
                        except Exception:
                            try:
                                conn.send({"type": "error", "error": "Ollama client import failed"})
                            except Exception:
                                pass
                            return

                        async def _run():
                            client = _Client(host=w_host)
                            last = {}
                            try:
                                stream = await client.chat(
                                    model=w_model,
                                    messages=w_messages,
                                    tools=w_tools,
                                    stream=True,
                                    format=w_format,
                                    options=w_options,
                                    keep_alive=w_keep_alive,
                                    think=w_think,
                                )
                                try:
                                    async for part in stream:
                                        last = part or {}
                                        try:
                                            conn.send({"type": "part", "data": last})
                                        except Exception:
                                            break
                                finally:
                                    try:
                                        if hasattr(stream, "aclose"):
                                            await stream.aclose()
                                    except Exception:
                                        pass
                                try:
                                    conn.send({"type": "done", "last": last})
                                except Exception:
                                    pass
                            except Exception as _e:
                                try:
                                    conn.send({"type": "error", "error": str(_e)})
                                except Exception:
                                    pass
                            finally:
                                try:
                                    await client.close()
                                except Exception:
                                    pass

                        try:
                            _a.run(_run())
                        finally:
                            try:
                                conn.close()
                            except Exception:
                                pass

                    proc = mp.Process(
                        target=_worker,
                        args=(child_conn, host, model, messages, tools, fmt, options, keep_alive, think),
                        daemon=True,
                    )
                    proc.start()
                    self._proc = proc

                    try:
                        last_resp: Dict[str, Any] = {}
                        was_cancelled: bool = False
                        while proc.is_alive() or parent_conn.poll(0.05):
                            if self._cancel_event.is_set():
                                was_cancelled = True
                                break
                            if parent_conn.poll(0.1):
                                try:
                                    msg = parent_conn.recv()
                                except EOFError:
                                    break
                                if not isinstance(msg, dict):
                                    continue
                                mtype = msg.get("type")
                                if mtype == "part":
                                    last_resp = (msg.get("data") or {})
                                    rmsg = (last_resp.get("message") or {}) if isinstance(last_resp, dict) else {}
                                    content_piece = rmsg.get("content")
                                    if content_piece:
                                        accumulated_content.append(content_piece)
                                    thinking_piece = rmsg.get("thinking")
                                    if isinstance(thinking_piece, str) and thinking_piece:
                                        accumulated_thinking.append(thinking_piece)
                                    if accumulated_content:
                                        yield {"assistant_text": "".join(accumulated_content), "assistant_done": False}
                                elif mtype == "done":
                                    last_resp = (msg.get("last") or {})
                                    break
                                elif mtype == "error":
                                    err = str(msg.get("error") or "unknown error")
                                    yield {"metrics": {"error": err}, "assistant_text": "", "assistant_done": True}
                                    return
                        # If cancelled, exit without emitting a final message
                        if was_cancelled:
                            return

                        # Build final message and metrics from the streamed parts
                        final_message = (last_resp.get("message") if isinstance(last_resp, dict) else {}) or {}
                        for k in ("total_duration", "load_duration", "prompt_eval_count", "prompt_eval_duration", "eval_count", "eval_duration"):
                            if isinstance(last_resp, dict) and k in last_resp:
                                metrics[k] = last_resp[k]
                        metrics["seed"] = int(effective_seed) if effective_seed is not None else None
                        if "temperature" in options:
                            metrics["temperature"] = options["temperature"]
                        final_content = "".join(accumulated_content)
                        if not isinstance(final_message, dict):
                            final_message = {}
                        if final_content:
                            final_message["content"] = final_content
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
                    finally:
                        # Cleanup child and IPC
                        try:
                            parent_conn.close()
                        except Exception:
                            pass
                        self._ipc_parent = None
                        if proc.is_alive():
                            try:
                                proc.join(timeout=0.2)
                            except Exception:
                                pass
                            if proc.is_alive():
                                try:
                                    proc.kill()
                                except Exception:
                                    try:
                                        os.kill(proc.pid, signal.SIGKILL)
                                    except Exception:
                                        pass
                                try:
                                    proc.join(timeout=0.2)
                                except Exception:
                                    pass
                        self._proc = None
                else:
                    from ollama import AsyncClient
                    print(f"OllamaChatNode: Creating Ollama client for {host}")
                    client = AsyncClient(host=host)
                    self._client = client
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
            finally:
                client = getattr(self, "_client", None)
                if client is not None:
                    try:
                        await client.close()
                    except Exception:
                        pass
                self._client = None
        except asyncio.CancelledError:
            # Cooperative cancellation; do not emit error on cancel
            return
        except Exception as e:
            # Surface error to UI via metrics field
            yield {"metrics": {"error": str(e)}}
        finally:
            # Reset cancel flag for next run
            self._cancel_event.clear()



    async def execute(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        try:
            model: str = inputs.get("model")
            raw_messages: Optional[List[Dict[str, Any]]] = inputs.get("messages")
            prompt_text: Optional[str] = inputs.get("prompt")
            system_prompt: Optional[str] = inputs.get("system")
            messages: List[Dict[str, Any]] = self._build_messages(raw_messages, prompt_text, system_prompt)
            tools: Optional[List[Dict[str, Any]]] = inputs.get("tools")

            if not model:
                error_msg = "No model provided to OllamaChatNode. Check model selector connection."
                return {"metrics": {"error": error_msg}, "assistant_text": "", "assistant_done": True}

            host: str = inputs.get("host") or os.getenv("OLLAMA_HOST", "http://localhost:11434")
            # Force non-streaming for execute()
            fmt: str = "json" if bool(self.params.get("json_mode", False)) else None
            _keep_alive_param = self.params.get("keep_alive")
            keep_alive = _keep_alive_param if (_keep_alive_param is not None and _keep_alive_param != "") else None
            think = bool(self.params.get("think", False))
            options = self._parse_options() or {}

            # Validate we have something to send
            if not messages and not prompt_text:
                error_msg = "No messages or prompt provided to OllamaChatNode"
                return {"metrics": {"error": error_msg}, "assistant_text": "", "assistant_done": True}

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

            from ollama import AsyncClient

            client = AsyncClient(host=host)
            self._client = client
            try:
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
                metrics: Dict[str, Any] = {}
                for k in ("total_duration", "load_duration", "prompt_eval_count", "prompt_eval_duration", "eval_count", "eval_duration"):
                    if k in resp:
                        metrics[k] = resp[k]
                metrics["seed"] = int(effective_seed) if effective_seed is not None else None
                if "temperature" in options:
                    metrics["temperature"] = options["temperature"]
                thinking_final: str = ""
                if isinstance(final_message.get("thinking"), str):
                    thinking_final = final_message.get("thinking") or ""
                return {
                    "assistant_text": final_message.get("content") or "",
                    "assistant_message": final_message,
                    "thinking": thinking_final,
                    "assistant_done": True,
                    "metrics": metrics,
                }
            finally:
                try:
                    await client.close()
                except Exception:
                    pass
                self._client = None
        except Exception as e:
            return {"metrics": {"error": str(e)}}
