from typing import Dict, Any, List, Optional, Union, Tuple
import os
import json
import asyncio
import random
import httpx

from nodes.base.base_node import BaseNode

from core.types_registry import get_type
from services.tools.registry import get_tool_handler, get_all_credential_providers
from core.api_key_vault import APIKeyVault

class OpenRouterChatNode(BaseNode):
    """
    Chat node backed by OpenRouter API for multi-provider LLM access.

    Constraints:
    - Requires OPENROUTER_API_KEY in the vault.

    Inputs:
    - messages: List[Dict[str, Any]] (chat history with role, content, etc.)
    - prompt: str
    - system: str or LLMChatMessage
    - tools: List[LLMToolSpec] (optional tool schema)

    Outputs:
    - message: Dict[str, Any] (assistant message with role, content, tool_calls, etc.)
    - metrics: Dict[str, Any] (generation stats like token counts, cost)
    - tool_history: List[Dict[str, Any]] (history of tool calls and results)
    - thinking_history: List[Dict[str, Any]] (history of thinking steps)
    """

    inputs = {
        "messages": get_type("LLMChatMessageList"),
        "prompt": str,
        "system": Union[str, get_type("LLMChatMessage")],
        "tools": get_type("LLMToolSpecList"),
    }

    outputs = {
        "message": Dict[str, Any],
        "metrics": get_type("LLMChatMetrics"),
        "tool_history": get_type("LLMToolHistory"),
        "thinking_history": get_type("LLMThinkingHistory"),
    }

    CATEGORY = 'data_source'
    # Keys required for this node to function
    required_keys = ["OPENROUTER_API_KEY"]

    default_params = {
        "model": "z-ai/glm-4.6",  # Default model
        "temperature": 0.7,
        "max_tokens": 1024,
        "seed": 0,
        "seed_mode": "fixed",  # fixed | random | increment
        # Tool orchestration controls
        "max_tool_iters": 2,
        "tool_timeout_s": 10,
        "tool_choice": "auto",  # auto | none | required
        "json_mode": False,
        # Web search controls
        "web_search_enabled": True,
        "web_search_engine": "exa",  # exa | native
        "web_search_max_results": 5,
        "web_search_context_size": "medium",  # low | medium | high
    }

    params_meta = [
        {"name": "model", "type": "combo", "default": "z-ai/glm-4.6", "options": []},
        {"name": "temperature", "type": "number", "default": 0.7, "min": 0.0, "max": 2.0, "step": 0.05},
        {"name": "max_tokens", "type": "number", "default": 1024, "min": 1, "step": 1, "precision": 0},
        {"name": "seed", "type": "number", "default": 0, "min": 0, "step": 1, "precision": 0},
        {"name": "max_tool_iters", "type": "number", "default": 2, "min": 0, "step": 1, "precision": 0},
        {"name": "tool_timeout_s", "type": "number", "default": 10, "min": 0, "step": 1, "precision": 0},
        {"name": "seed_mode", "type": "combo", "default": "fixed", "options": ["fixed", "random", "increment"]},
        {"name": "tool_choice", "type": "combo", "default": "auto", "options": ["auto", "none", "required"]},
        {"name": "json_mode", "type": "combo", "default": False, "options": [False, True]},
        {"name": "web_search_enabled", "type": "combo", "default": True, "options": [True, False]},
        {"name": "web_search_engine", "type": "combo", "default": "exa", "options": ["exa", "native"]},
        {"name": "web_search_max_results", "type": "number", "default": 5, "min": 1, "max": 10, "step": 1, "precision": 0},
        {"name": "web_search_context_size", "type": "combo", "default": "medium", "options": ["low", "medium", "high"]},
    ]

    ui_module = "llm/OpenRouterChatNodeUI"

    def __init__(self, id: int, params: Dict[str, Any] = None):
        super().__init__(id, params)
        self.optional_inputs = ["tools", "tool", "messages", "prompt", "system"]
        # Maintain seed state for increment mode
        self._seed_state: Optional[int] = None
        self.vault = APIKeyVault()

    @staticmethod
    def _build_messages(existing_messages: Optional[List[Dict[str, Any]]], prompt: Optional[str], system_input: Optional[Any]) -> List[Dict[str, Any]]:
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
        result: List[Dict[str, Any]] = []
        tools_list = inputs.get("tools")
        if tools_list and isinstance(tools_list, list):
            result.extend(tools_list)
        for tool_spec in self.collect_multi_input("tool", inputs):
            if isinstance(tool_spec, dict) and tool_spec.get("type") == "function":
                result.append(tool_spec)
        return result

    def _prepare_generation_options(self) -> Dict[str, Any]:
        options: Dict[str, Any] = {}
        temperature_raw = self.params.get("temperature")
        if temperature_raw is not None:
            options["temperature"] = float(temperature_raw)
        max_tokens_raw = self.params.get("max_tokens")
        if max_tokens_raw is not None:
            options["max_tokens"] = int(max_tokens_raw)
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
        if bool(self.params.get("json_mode", False)):
            options["response_format"] = {"type": "json_object"}
        return options

    def _prepare_web_search_options(self) -> Dict[str, Any]:
        """Prepare web search configuration based on node parameters."""
        web_search_enabled = bool(self.params.get("web_search_enabled", True))
        if not web_search_enabled:
            return {}
        
        # For models with :online suffix, web search is enabled automatically
        # No additional options needed for basic web search functionality
        return {}
    
    def _get_model_with_web_search(self, base_model: str) -> str:
        """Get model name with web search suffix if enabled."""
        web_search_enabled = bool(self.params.get("web_search_enabled", True))
        if not web_search_enabled:
            return base_model
        
        # Add :online suffix to enable web search
        if not base_model.endswith(":online"):
            return f"{base_model}:online"
        return base_model
    
    def _get_current_date(self) -> str:
        """Get current date string for web search prompt."""
        from datetime import datetime
        return datetime.now().strftime("%Y-%m-%d")

    async def _maybe_execute_tools_and_augment_messages(self, base_messages: List[Dict[str, Any]], tools: Optional[List[Dict[str, Any]]], options: Dict[str, Any]) -> Dict[str, Any]:
        if not tools or not isinstance(tools, list):
            return {"messages": base_messages, "tool_history": [], "thinking_history": []}

        max_iters = int(self.params.get("max_tool_iters", 2) or 0)
        timeout_s = int(self.params.get("tool_timeout_s", 10) or 10)

        messages = list(base_messages)
        tool_history: List[Dict[str, Any]] = []
        thinking_history: List[Dict[str, Any]] = []
        error_count = 0

        for _round in range(max(0, max_iters) + 1):
            api_key = self.vault.get("OPENROUTER_API_KEY")
            if not api_key:
                raise ValueError("OPENROUTER_API_KEY not found in vault")

            web_search_options = self._prepare_web_search_options()
            base_model = self.params.get("model", "z-ai/glm-4.6")
            model_with_web_search = self._get_model_with_web_search(base_model)
            
            request_body = {
                "model": model_with_web_search,
                "messages": messages,
                "tools": tools,
                "tool_choice": self.params.get("tool_choice") if tools else None,
                "stream": False,
                **options,
                **web_search_options
            }

            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    "https://openrouter.ai/api/v1/chat/completions",
                    headers={
                        "Authorization": f"Bearer {api_key}",
                        "Content-Type": "application/json",
                    },
                    json=request_body
                )
                response.raise_for_status()
                resp_data = response.json()

            message = (resp_data or {}).get("choices", [{}])[0].get("message", {"role": "assistant", "content": ""})
            tool_calls = message.get("tool_calls")
            if not tool_calls or not isinstance(tool_calls, list):
                break

            # Execute tools in parallel
            async def execute_tool(call: Dict[str, Any]) -> Tuple[Dict[str, Any], Dict[str, Any]]:
                try:
                    fn = (call or {}).get("function") or {}
                    tool_name = fn.get("name")
                    arguments = fn.get("arguments") or {}
                    # Normalize arguments to a dictionary; OpenRouter may return a JSON string
                    if isinstance(arguments, str):
                        try:
                            arguments = json.loads(arguments)
                        except Exception:
                            arguments = {}
                    if not isinstance(arguments, dict):
                        arguments = {}

                    handler = get_tool_handler(tool_name) if isinstance(tool_name, str) else None
                    result_obj: Any = None

                    async def _run_handler():
                        if handler is None:
                            return {"error": "unknown_tool", "message": f"No handler for tool '{tool_name}'"}
                        ctx = {
                            "model": self.params.get("model"),
                            "credentials": get_all_credential_providers()
                        }
                        return await handler(arguments, ctx)

                    try:
                        result_obj = await asyncio.wait_for(_run_handler(), timeout=timeout_s)
                    except asyncio.TimeoutError:
                        result_obj = {"error": "timeout", "message": f"Tool '{tool_name}' timed out after {timeout_s}s"}
                    except Exception as _e:
                        result_obj = {"error": "exception", "message": str(_e)}

                    # Sanitize the call object for output validation: ensure arguments is a dict
                    sanitized_call = {
                        "id": call.get("id"),
                        "function": {
                            "name": tool_name,
                            "arguments": arguments,
                        },
                    }
                    return sanitized_call, result_obj
                except Exception as _e_outer:
                    return call, {"error": "handler_failure", "message": str(_e_outer)}

            # Gather all tool executions
            tasks = [execute_tool(call) for call in tool_calls]
            results = await asyncio.gather(*tasks, return_exceptions=True)

            round_errors = 0
            for result in results:
                if isinstance(result, Exception):
                    # Handle unexpected exceptions
                    round_errors += 1
                    error_count += 1
                    continue
                call, result_obj = result

                # Check if tool execution had an error
                if isinstance(result_obj, dict) and result_obj.get("error"):
                    round_errors += 1
                    error_count += 1

                try:
                    content_str = json.dumps(result_obj, ensure_ascii=False)
                except Exception:
                    content_str = str(result_obj)

                messages.append({
                    "role": "tool",
                    "tool_call_id": call.get("id"),
                    "content": content_str,
                })

                tool_history.append({"call": call, "result": result_obj})

            # Break if too many errors in this round or overall
            if round_errors > len(tool_calls) // 2 or error_count > max_iters:
                break

        return {"messages": messages, "tool_history": tool_history, "thinking_history": thinking_history}

    def _ensure_assistant_role_inplace(self, message: Dict[str, Any]) -> None:
        if isinstance(message, dict) and "role" not in message:
            message["role"] = "assistant"

    def _parse_tool_calls_from_message(self, message: Dict[str, Any]):
        content = message.get("content", "")
        if isinstance(content, str):
            marker = "_TOOL_WEB_SEARCH_: "
            if marker in content:
                query_start = content.find(marker) + len(marker)
                query_end = content.find("_RESULT_:", query_start)
                if query_end == -1:
                    query_end = content.find("_TOOL_END_:", query_start)
                if query_end == -1:
                    query_end = len(content)
                query = content[query_start:query_end].strip()
                if query:
                    tool_call = {
                        "function": {
                            "name": "web_search",
                            "arguments": {"query": query}
                        }
                    }
                    if "tool_calls" not in message:
                        message["tool_calls"] = []
                    if tool_call not in message["tool_calls"]:
                        message["tool_calls"].append(tool_call)
        if message.get("tool_calls"):
            complete_calls = [call for call in message["tool_calls"] if self._is_complete_tool_call(call)]
            if complete_calls:
                message["tool_name"] = complete_calls[0]["function"]["name"]
            else:
                message["tool_name"] = None
        else:
            message["tool_name"] = None

    def _is_complete_tool_call(self, call: Dict[str, Any]) -> bool:
        return isinstance(call, dict) and call.get("function", {}).get("name") and call.get("function", {}).get("arguments")

    async def _execute_impl(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        raw_messages: Optional[List[Dict[str, Any]]] = inputs.get("messages")
        prompt_text: Optional[str] = inputs.get("prompt")
        system_input: Optional[Any] = inputs.get("system")
        messages: List[Dict[str, Any]] = self._build_messages(raw_messages, prompt_text, system_input)
        tools: List[Dict[str, Any]] = self._collect_tools(inputs)

        if not messages:
            error_msg = "No messages or prompt provided to OpenRouterChatNode"
            return {"message": {"role": "assistant", "content": ""}, "metrics": {"error": error_msg}, "tool_history": [], "thinking_history": []}

        # Early explicit API key check so the graph surfaces a clear failure without silent fallthrough
        api_key_early = self.vault.get("OPENROUTER_API_KEY")
        if not api_key_early:
            return {
                "message": {"role": "assistant", "content": "OpenRouter API key missing. Set OPENROUTER_API_KEY."},
                "metrics": {"error": "OPENROUTER_API_KEY not found in vault"},
                "tool_history": [],
                "thinking_history": []
            }

        options = self._prepare_generation_options()

        tool_choice = str(self.params.get("tool_choice", "auto")).strip().lower()

        tool_rounds_info = {"tool_history": [], "thinking_history": []}

        if tool_choice in ["auto", "required"] and tools:
            tool_rounds_info = await self._maybe_execute_tools_and_augment_messages(messages, tools, options)
            messages = tool_rounds_info.get("messages", messages)
            final_tools = None
            final_tool_choice = None
        else:
            messages = messages
            final_tools = tools
            final_tool_choice = tool_choice

        api_key = self.vault.get("OPENROUTER_API_KEY")
        if not api_key:
            raise ValueError("OPENROUTER_API_KEY not found in vault")

        web_search_options = self._prepare_web_search_options()
        base_model = self.params.get("model", "openai/gpt-4o-mini")
        model_with_web_search = self._get_model_with_web_search(base_model)
        
        request_body = {
            "model": model_with_web_search,
            "messages": messages,
            "tools": final_tools,
            "tool_choice": final_tool_choice if final_tools else None,
            "stream": False,
            **options,
            **web_search_options
        }

        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json=request_body
            )
            response.raise_for_status()
            resp_data = response.json()

        final_message = (resp_data or {}).get("choices", [{}])[0].get("message", {"role": "assistant", "content": ""})
        self._ensure_assistant_role_inplace(final_message)
        self._parse_tool_calls_from_message(final_message)

        # Parse JSON response if json_mode is enabled
        if bool(self.params.get("json_mode", False)) and isinstance(final_message.get("content"), str):
            try:
                final_message["content"] = json.loads(final_message["content"])
            except json.JSONDecodeError:
                pass  # Keep as string if parsing fails

        usage = (resp_data or {}).get("usage", {})
        metrics: Dict[str, Any] = {
            "prompt_tokens": usage.get("prompt_tokens", 0),
            "completion_tokens": usage.get("completion_tokens", 0),
            "total_tokens": usage.get("total_tokens", 0),
            "temperature": options.get("temperature"),
            "seed": options.get("seed"),
        }

        # Query detailed generation stats if available
        generation_id = (resp_data or {}).get("id")
        if generation_id and api_key:
            try:
                async with httpx.AsyncClient(timeout=10.0) as client:
                    gen_response = await client.get(
                        f"https://openrouter.ai/api/v1/generation?id={generation_id}",
                        headers={
                            "Authorization": f"Bearer {api_key}",
                        }
                    )
                    gen_response.raise_for_status()
                    gen_data = gen_response.json()
                    if gen_data.get("data"):
                        gen_metrics = gen_data["data"]
                        # Merge additional metrics like cost, native tokens, etc.
                        for key in ["total_cost", "native_tokens_prompt", "native_tokens_completion", "latency", "generation_time"]:
                            if key in gen_metrics:
                                metrics[key] = gen_metrics[key]
            except Exception as e:
                # Silently ignore generation API failures
                pass

        return {
            "message": final_message,
            "metrics": metrics,
            "tool_history": tool_rounds_info.get("tool_history", []),
            "thinking_history": tool_rounds_info.get("thinking_history", [])
        }
