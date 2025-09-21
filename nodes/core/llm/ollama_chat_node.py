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
    - host: str
    - model: str (e.g., "llama3.2:latest")
    - messages: List[Dict[str, Any]] (chat history with role, content, etc.)
    - prompt: str
    - system: str
    - tools: List[Dict[str, Any]] (optional tool schemas)

    Outputs:
    - message: Dict[str, Any] (assistant message with role, content, thinking, tool_calls, etc.)
    - metrics: Dict[str, Any] (generation stats like durations and token counts)

    In streaming mode (default), start() yields progressive dicts:
    - Partial: {"message": dict (with accumulating content), "done": False}
    - Final: {"message": dict, "metrics": dict, "done": True}

    Note: Streaming mode is currently in beta and may be unstable.
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
        "message": get_type("LLMChatMessage"),
        "metrics": get_type("LLMChatMetrics"),
    }

    # Mark as data_source category so default Base UI does not display inline output
    CATEGORY = 'data_source'

    default_params = {
        "stream": False,
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

    # Update params_meta:
    params_meta = [
        {"name": "stream", "type": "combo", "default": False, "options": [True, False]},
        {"name": "temperature", "type": "number", "default": 0.7, "min": 0.0, "max": 1.5, "step": 0.05},
        {"name": "seed_mode", "type": "combo", "default": "fixed", "options": ["fixed", "random", "increment"]},
        {"name": "seed", "type": "number", "default": 0, "min": 0, "step": 1, "precision": 0},
        {"name": "think", "type": "combo", "default": False, "options": [False, True]},
        {"name": "max_tool_iters", "type": "number", "default": 2, "min": 0, "step": 1, "precision": 0},
        {"name": "tool_timeout_s", "type": "number", "default": 10, "min": 0, "step": 1, "precision": 0},
        {"name": "json_mode", "type": "combo", "default": False, "options": [False, True]},
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
        result = list(existing_messages or [])
        if system_prompt and not any(m.get("role") == "system" for m in result):
            result.insert(0, {"role": "system", "content": system_prompt})
        if prompt:
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
                yield {"message": {"role": "assistant", "content": ""}, "metrics": {"error": error_msg}}
                return

            host: str = inputs.get("host") or os.environ.get("OLLAMA_HOST", "http://localhost:11434")
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
                yield {"message": {"role": "assistant", "content": ""}, "metrics": {"error": error_msg}}
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

            # Buffer for reconstructing message fields
            message_buffer = {
                "role": "assistant",
                "content": [],
                "thinking": [],
                "tool_calls": [],  # List of complete tool calls
                "_partial_tool": None  # Temp for building partial tools
            }
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
                    # If running under pytest, avoid multiprocessing so mocks apply in-process
                    if os.environ.get("PYTEST_CURRENT_TEST"):
                        print("OllamaChatNode: In-process streaming (test mode)")
                        client = AsyncClient(host=host)
                        self._client = client
                        try:
                            stream = await client.chat(
                                model=model,
                                messages=messages,
                                tools=tools,
                                stream=True,
                                format=fmt,
                                options=options,
                                keep_alive=keep_alive,
                                think=think,
                            )
                            self._active_stream = stream
                            try:
                                async for part in stream:
                                    if self._cancel_event.is_set():
                                        return
                                    self._process_stream_part(part, message_buffer)
                                    snapshot = self._snapshot_buffer(message_buffer)
                                    if snapshot:  # Yield if meaningful update
                                        yield {"message": snapshot, "done": False}

                                    if part.get("done"):
                                        final_message = self._finalize_buffer(message_buffer)
                                        self._parse_content_if_json_mode(final_message, metrics)
                                        final_message = self._make_full_message(final_message)
                                        for k in ("total_duration", "load_duration", "prompt_eval_count", "prompt_eval_duration", "eval_count", "eval_duration"):
                                            if k in part:
                                                metrics[k] = part[k]
                                        metrics["seed"] = int(effective_seed) if effective_seed is not None else None
                                        if "temperature" in options:
                                            metrics["temperature"] = options["temperature"]
                                        yield {"message": final_message, "metrics": metrics, "done": True}
                                        return
                            finally:
                                try:
                                    if hasattr(stream, "aclose"):
                                        await stream.aclose()
                                except Exception:
                                    pass
                                self._active_stream = None
                        finally:
                            try:
                                await client.close()
                            except Exception:
                                pass
                            self._client = None
                        return
                    # Prefer child-process based streaming for hard kill capability.
                    # If multiprocessing fails (e.g., spawn pickling issues), fall back to in-process streaming.
                    try:
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
                                            try:
                                                conn.send({"type": "part", "data": part})
                                            except Exception:
                                                break
                                    finally:
                                        try:
                                            if hasattr(stream, "aclose"):
                                                await stream.aclose()
                                        except Exception:
                                            pass
                                    try:
                                        conn.send({"type": "done"})
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
                            except Exception as e:
                                try:
                                    conn.send({"type": "error", "error": f"asyncio.run failed: {str(e)}"})
                                except:
                                    pass
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
                            was_cancelled: bool = False
                            done_received: bool = False
                            error_received: bool = False

                            while not done_received and not error_received and not was_cancelled:
                                if self._cancel_event.is_set():
                                    was_cancelled = True
                                    break

                                # Block with timeout to allow cancel checks
                                if parent_conn.poll(1.0):
                                    try:
                                        msg = parent_conn.recv()
                                    except EOFError:
                                        break
                                    if not isinstance(msg, dict):
                                        continue
                                    mtype = msg.get("type")
                                    if mtype == "part":
                                        self._process_stream_part(msg.get("data", {}), message_buffer)
                                        snapshot = self._snapshot_buffer(message_buffer)
                                        if snapshot:
                                            yield {"message": snapshot, "done": False}
                                    elif mtype == "done":
                                        done_received = True
                                        final_message = self._finalize_buffer(message_buffer)
                                        # Note: Metrics might need to be accumulated from parts if available
                                        metrics["seed"] = int(effective_seed) if effective_seed is not None else None
                                        if "temperature" in options:
                                            metrics["temperature"] = options["temperature"]
                                        yield {"message": final_message, "metrics": metrics, "done": True}
                                    elif mtype == "error":
                                        err = str(msg.get("error") or "unknown error")
                                        yield {"message": {"role": "assistant", "content": ""}, "metrics": {"error": err}, "done": True}
                                        error_received = True
                                elif not proc.is_alive():
                                    # Child exited without sending done; drain any remaining messages
                                    while parent_conn.poll(0.1):
                                        try:
                                            msg = parent_conn.recv()
                                            # Process msg as above
                                            if not isinstance(msg, dict):
                                                continue
                                            mtype = msg.get("type")
                                            if mtype == "part":
                                                self._process_stream_part(msg.get("data", {}), message_buffer)
                                                snapshot = self._snapshot_buffer(message_buffer)
                                                if snapshot:
                                                    yield {"message": snapshot, "done": False}
                                            elif mtype == "done":
                                                last_resp = (msg.get("last") or {})
                                                # Append from done part
                                                rmsg = (last_resp.get("message") or {}) if isinstance(last_resp, dict) else {}
                                                content_piece = rmsg.get("content", "")
                                                if content_piece is not None:
                                                    accumulated_content.append(content_piece)
                                                thinking_piece = rmsg.get("thinking")
                                                if isinstance(thinking_piece, str) and thinking_piece:
                                                    accumulated_thinking.append(thinking_piece)
                                                done_received = True
                                                # Build and yield final
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
                                                if not isinstance(final_message.get("thinking"), str) and accumulated_thinking:
                                                    final_message["thinking"] = "".join(accumulated_thinking)
                                                yield {"message": final_message, "metrics": metrics, "done": True}
                                            elif mtype == "error":
                                                err = str(msg.get("error") or "unknown error")
                                                yield {"message": {"role": "assistant", "content": ""}, "metrics": {"error": err}}
                                                error_received = True
                                        except EOFError:
                                            break
                                    if not done_received and not error_received:
                                        # If still no done, assume completion with last_resp
                                        done_received = True

                            # If cancelled, exit without emitting a final message
                            if was_cancelled:
                                # Flush partial buffer on cancel
                                partial_message = self._finalize_buffer(message_buffer)
                                partial_message = self._make_full_message(partial_message)
                                yield {"message": partial_message, "metrics": {"error": "Stream cancelled"}, "done": True}
                                return
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
                    except Exception:
                        # Fallback to in-process, with buffer
                        print("OllamaChatNode: Falling back to in-process streaming")
                        client = AsyncClient(host=host)
                        self._client = client
                        try:
                            stream = await client.chat(
                                model=model,
                                messages=messages,
                                tools=tools,
                                stream=True,
                                format=fmt,
                                options=options,
                                keep_alive=keep_alive,
                                think=think,
                            )
                            self._active_stream = stream
                            try:
                                async for part in stream:
                                    if self._cancel_event.is_set():
                                        partial_message = self._finalize_buffer(message_buffer)
                                        partial_message = self._make_full_message(partial_message)
                                        yield {"message": partial_message, "metrics": {"error": "Stream cancelled"}, "done": True}
                                        return
                                    self._process_stream_part(part, message_buffer)
                                    snapshot = self._snapshot_buffer(message_buffer)
                                    if snapshot:
                                        yield {"message": snapshot, "done": False}

                                    if part.get("done"):
                                        final_message = self._finalize_buffer(message_buffer)
                                        self._parse_content_if_json_mode(final_message, metrics)
                                        final_message = self._make_full_message(final_message)
                                        for k in ("total_duration", "load_duration", "prompt_eval_count", "prompt_eval_duration", "eval_count", "eval_duration"):
                                            if k in part:
                                                metrics[k] = part[k]
                                        metrics["seed"] = int(effective_seed) if effective_seed is not None else None
                                        if "temperature" in options:
                                            metrics["temperature"] = options["temperature"]
                                        yield {"message": final_message, "metrics": metrics, "done": True}
                                        return
                            finally:
                                # ... existing
                                pass
                        finally:
                            # ... existing
                            pass
                else:
                    # Non-streaming mode (unchanged, but ensure output is LLMChatMessage)
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
                    final_message = (resp or {}).get("message") or {"role": "assistant", "content": ""}
                    self._parse_content_if_json_mode(final_message, metrics)
                    final_message = self._make_full_message(final_message)
                    metrics = {}
                    for k in ("total_duration", "load_duration", "prompt_eval_count", "prompt_eval_duration", "eval_count", "eval_duration"):
                        if k in resp:
                            metrics[k] = resp[k]
                    metrics["seed"] = int(effective_seed) if effective_seed is not None else None
                    if "temperature" in options:
                        metrics["temperature"] = options["temperature"]
                    yield {"message": final_message, "metrics": metrics, "done": True}
            finally:
                # ... existing client close
                pass
        except asyncio.CancelledError:
            # Cooperative cancellation; do not emit error on cancel
            return
        except Exception as e:
            yield {"message": {"role": "assistant", "content": ""}, "metrics": {"error": str(e)}, "done": True}
        finally:
            self._cancel_event.clear()

    def _process_stream_part(self, part: Dict[str, Any], buffer: Dict[str, Any]):
        rmsg = part.get("message", {}) if isinstance(part, dict) else {}
        if "content" in rmsg and rmsg["content"]:
            buffer["content"].append(rmsg["content"])
        if "thinking" in rmsg and rmsg["thinking"]:
            buffer["thinking"].append(rmsg["thinking"])
        if "tool_calls" in rmsg:
            for call in rmsg["tool_calls"]:
                if buffer["_partial_tool"] is None:
                    buffer["_partial_tool"] = call
                else:
                    # Deep merge function dict
                    if "function" in call and "function" in buffer["_partial_tool"]:
                        buffer["_partial_tool"]["function"].update(call["function"])
                    else:
                        buffer["_partial_tool"].update(call)
                if self._is_complete_tool_call(buffer["_partial_tool"]):
                    buffer["tool_calls"].append(buffer["_partial_tool"])
                    buffer["_partial_tool"] = None

    def _snapshot_buffer(self, buffer: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        thinking = "".join(buffer["thinking"])
        tool_calls = list(buffer["tool_calls"])
        snapshot = {
            "role": buffer["role"],
            "content": "".join(buffer["content"]),
        }
        if thinking:
            snapshot["thinking"] = thinking
        snapshot["tool_calls"] = tool_calls
        # Only return if there's meaningful data
        if snapshot.get("content") or snapshot.get("thinking") or tool_calls:
            return snapshot
        return None

    def _finalize_buffer(self, buffer: Dict[str, Any]) -> Dict[str, Any]:
        final = self._snapshot_buffer(buffer) or {"role": "assistant", "content": ""}
        # Discard any remaining partial tool
        buffer["_partial_tool"] = None
        # Optional: Reorder (e.g., thinking before content)
        return final

    def _is_complete_tool_call(self, call: Dict[str, Any]) -> bool:
        func = call.get("function")
        return bool(func and "name" in func and "arguments" in func)

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
                return {"metrics": {"error": error_msg}, "message": {"role": "assistant", "content": ""}, "thinking": None}

            host: str = inputs.get("host") or os.environ.get("OLLAMA_HOST", "http://localhost:11434")
            # Force non-streaming for execute()
            fmt: str = "json" if bool(self.params.get("json_mode", False)) else None
            _keep_alive_param = self.params.get("keep_alive")
            keep_alive = _keep_alive_param if (_keep_alive_param is not None and _keep_alive_param != "") else None
            think = bool(self.params.get("think", False))
            options = self._parse_options() or {}

            # Validate we have something to send
            if not messages and not prompt_text:
                error_msg = "No messages or prompt provided to OllamaChatNode"
                return {"metrics": {"error": error_msg}, "message": {"role": "assistant", "content": ""}, "thinking": None}

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
                self._parse_content_if_json_mode(final_message, metrics)
                final_message = self._make_full_message(final_message)
                for k in ("total_duration", "load_duration", "prompt_eval_count", "prompt_eval_duration", "eval_count", "eval_duration"):
                    if k in resp:
                        metrics[k] = resp[k]
                metrics["seed"] = int(effective_seed) if effective_seed is not None else None
                if "temperature" in options:
                    metrics["temperature"] = options["temperature"]
                return {
                    "message": final_message,
                    "metrics": metrics
                }
            finally:
                try:
                    await client.close()
                except Exception:
                    pass
                self._client = None
        except Exception as e:
            return {"message": {"role": "assistant", "content": ""}, "metrics": {"error": str(e)}}

    def _parse_content_if_json_mode(self, message: Dict[str, Any], metrics: Dict[str, Any]) -> None:
        if bool(self.params.get("json_mode", False)):
            content_str = message.get("content", "")
            if isinstance(content_str, str):
                try:
                    parsed = json.loads(content_str)
                    message["content"] = parsed
                except json.JSONDecodeError as e:
                    metrics["parse_error"] = str(e)

    def _make_full_message(self, base: Dict[str, Any]) -> Dict[str, Any]:
        full = {
            "role": base.get("role", "assistant"),
            "content": base.get("content", ""),
            "thinking": base.get("thinking", None),
            "images": base.get("images", None),
            "tool_calls": base.get("tool_calls", None),
            "tool_name": base.get("tool_name", None),
        }
        return full
