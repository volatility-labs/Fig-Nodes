import asyncio
import json
import random
from typing import Any, Literal, NotRequired, TypedDict, cast

import httpx
from pydantic import BaseModel

from core.api_key_vault import APIKeyVault
from core.types_registry import LLMChatMessage, LLMToolSpec, NodeCategory, get_type
from nodes.base.base_node import Base
from services.tools.registry import get_all_credential_providers, get_tool_handler


class OpenRouterFunctionCall(TypedDict):
    name: str
    arguments: str | dict[str, Any]


class OpenRouterToolCall(TypedDict):
    id: str
    type: Literal["function"]
    function: OpenRouterFunctionCall


class OpenRouterChatMessage(TypedDict):
    role: str
    content: str | None
    tool_calls: NotRequired[list[OpenRouterToolCall]]


class OpenRouterGenerationMetrics(TypedDict):
    total_cost: float
    native_tokens_prompt: NotRequired[int | None]
    native_tokens_completion: NotRequired[int | None]
    native_tokens_reasoning: NotRequired[int | None]
    latency: NotRequired[int | None]
    generation_time: NotRequired[int | None]
    tokens_prompt: NotRequired[int | None]
    tokens_completion: NotRequired[int | None]
    finish_reason: NotRequired[str | None]
    native_finish_reason: NotRequired[str | None]
    num_search_results: NotRequired[int | None]


class OpenRouterGenerationData(TypedDict):
    id: str
    model: str
    created_at: str
    streamed: NotRequired[bool | None]
    cancelled: NotRequired[bool | None]
    provider_name: NotRequired[str | None]
    origin: str
    usage: float
    is_byok: bool


class OpenRouterGenerationResponse(TypedDict):
    data: OpenRouterGenerationData


# Pydantic models for validation
class OpenRouterFunctionCallModel(BaseModel):
    name: str
    arguments: str | dict[str, Any]


class OpenRouterToolCallModel(BaseModel):
    id: str
    type: Literal["function"]
    function: OpenRouterFunctionCallModel


class OpenRouterChatMessageModel(BaseModel):
    role: str
    content: str | None = None
    tool_calls: list[OpenRouterToolCallModel] | None = None


class OpenRouterNonStreamingChoiceModel(BaseModel):
    finish_reason: str | None = None
    native_finish_reason: str | None = None
    message: OpenRouterChatMessageModel


class OpenRouterResponseUsageModel(BaseModel):
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int


class OpenRouterChatResponseModel(BaseModel):
    id: str
    choices: list[OpenRouterNonStreamingChoiceModel]
    created: int
    model: str
    object: Literal["chat.completion", "chat.completion.chunk"]
    usage: OpenRouterResponseUsageModel | None = None
    system_fingerprint: str | None = None


class OpenRouterChat(Base):
    inputs = {
        "messages": get_type("LLMChatMessageList") | None,
        "prompt": str,
        "system": str | get_type("LLMChatMessage") | None,
        "tools": str | get_type("LLMToolSpecList") | None,
    }

    outputs = {
        "message": dict[str, Any],
        "metrics": get_type("LLMChatMetrics"),
        "tool_history": get_type("LLMToolHistory"),
        "thinking_history": get_type("LLMThinkingHistory"),
    }

    CATEGORY = NodeCategory.LLM
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
        {
            "name": "temperature",
            "type": "number",
            "default": 0.7,
            "min": 0.0,
            "max": 2.0,
            "step": 0.05,
        },
        {
            "name": "max_tokens",
            "type": "number",
            "default": 1024,
            "min": 1,
            "step": 1,
            "precision": 0,
        },
        {"name": "seed", "type": "number", "default": 0, "min": 0, "step": 1, "precision": 0},
        {
            "name": "max_tool_iters",
            "type": "number",
            "default": 2,
            "min": 0,
            "step": 1,
            "precision": 0,
        },
        {
            "name": "tool_timeout_s",
            "type": "number",
            "default": 10,
            "min": 0,
            "step": 1,
            "precision": 0,
        },
        {
            "name": "seed_mode",
            "type": "combo",
            "default": "fixed",
            "options": ["fixed", "random", "increment"],
        },
        {
            "name": "tool_choice",
            "type": "combo",
            "default": "auto",
            "options": ["auto", "none", "required"],
        },
        {"name": "json_mode", "type": "combo", "default": False, "options": [False, True]},
        {"name": "web_search_enabled", "type": "combo", "default": True, "options": [True, False]},
        {
            "name": "web_search_engine",
            "type": "combo",
            "default": "exa",
            "options": ["exa", "native"],
        },
        {
            "name": "web_search_max_results",
            "type": "number",
            "default": 5,
            "min": 1,
            "max": 10,
            "step": 1,
            "precision": 0,
        },
        {
            "name": "web_search_context_size",
            "type": "combo",
            "default": "medium",
            "options": ["low", "medium", "high"],
        },
    ]

    def __init__(self, id: int, params: dict[str, Any]):
        super().__init__(id, params)
        self.optional_inputs = ["tools", "tool", "messages", "prompt", "system"]
        # Maintain seed state for increment mode
        self._seed_state: int | None = None
        self.vault = APIKeyVault()

    @staticmethod
    def _build_messages(
        existing_messages: list[LLMChatMessage] | None,
        prompt: str | None,
        system_input: LLMChatMessage | str | None,
    ) -> list[LLMChatMessage]:
        result = list(existing_messages or [])
        if system_input and not any(m.get("role") == "system" for m in result):
            if isinstance(system_input, str):
                result.insert(0, {"role": "system", "content": system_input})
            else:
                result.insert(0, system_input)
        if prompt:
            result.append({"role": "user", "content": prompt})
        return result

    def _collect_tools(self, inputs: dict[str, Any]) -> list[LLMToolSpec]:
        result: list[LLMToolSpec] = []
        tools_list: list[LLMToolSpec] | None = inputs.get("tools")
        if tools_list:
            result.extend(tools_list)
        for tool_spec in self.collect_multi_input("tool", inputs):
            if tool_spec["type"] == "function" and "function" in tool_spec:
                result.append(tool_spec)
        return result

    def _prepare_generation_options(self) -> dict[str, Any]:
        options: dict[str, Any] = {}
        temperature_raw = self.params.get("temperature")
        if temperature_raw is not None:
            options["temperature"] = (
                float(temperature_raw) if isinstance(temperature_raw, str) else temperature_raw
            )
        max_tokens_raw = self.params.get("max_tokens")
        if max_tokens_raw is not None:
            options["max_tokens"] = (
                int(max_tokens_raw) if isinstance(max_tokens_raw, str) else max_tokens_raw
            )
        seed_mode = str(self.params.get("seed_mode") or "fixed").strip().lower()
        seed_raw = self.params.get("seed")
        effective_seed: int | None = None
        base_seed = (
            int(seed_raw) if seed_raw is not None and isinstance(seed_raw, (int, float, str)) else 0
        )

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

    def _prepare_web_search_options(self) -> dict[str, Any]:
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

    async def _execute_single_tool(
        self, call: OpenRouterToolCall, timeout_s: int
    ) -> tuple[OpenRouterToolCall, dict[str, Any]]:
        """Execute a single tool call with error handling and timeout."""
        try:
            fn = call.get("function", OpenRouterFunctionCall(name="", arguments={}))
            tool_name = fn.get("name")
            arguments = fn.get("arguments") or {}

            # Normalize arguments to dictionary (OpenRouter may return JSON string)
            if isinstance(arguments, str):
                try:
                    arguments = json.loads(arguments)
                except Exception:
                    arguments = {}
            if not isinstance(arguments, dict):
                arguments = {}

            # Get tool handler
            handler = get_tool_handler(tool_name) if tool_name else None

            # Execute handler with timeout
            result_obj: Any = None
            if handler is None:
                result_obj = {
                    "error": "unknown_tool",
                    "message": f"No handler for tool '{tool_name}'",
                }
            else:
                try:
                    ctx = {
                        "model": self.params.get("model"),
                        "credentials": get_all_credential_providers(),
                    }
                    result_obj = await asyncio.wait_for(handler(arguments, ctx), timeout=timeout_s)
                except TimeoutError:
                    result_obj = {
                        "error": "timeout",
                        "message": f"Tool '{tool_name}' timed out after {timeout_s}s",
                    }
                except Exception as e:
                    result_obj = {"error": "exception", "message": str(e)}

            # Sanitize call for output validation
            sanitized_call: OpenRouterToolCall = OpenRouterToolCall(
                id=call.get("id", ""),
                type="function",
                function=OpenRouterFunctionCall(name=tool_name or "", arguments=arguments),
            )
            return sanitized_call, result_obj

        except Exception as e:
            return call, {"error": "handler_failure", "message": str(e)}

    async def _maybe_execute_tools_and_augment_messages(
        self,
        base_messages: list[LLMChatMessage],
        tools: list[LLMToolSpec] | None,
        options: dict[str, Any],
    ) -> dict[str, Any]:
        """Execute multiple rounds of tool calls, augmenting messages with results."""
        if not tools:
            return {"messages": base_messages, "tool_history": [], "thinking_history": []}

        # Parse configuration
        max_iters_raw = self.params.get("max_tool_iters", 2)
        max_iters = (
            int(max_iters_raw)
            if max_iters_raw is not None and isinstance(max_iters_raw, (int, float, str))
            else 2
        )
        timeout_s_raw = self.params.get("tool_timeout_s", 10)
        timeout_s = (
            int(timeout_s_raw)
            if timeout_s_raw is not None and isinstance(timeout_s_raw, (int, float, str))
            else 10
        )

        # Initialize state
        messages = list(base_messages)
        tool_history: list[dict[str, Any]] = []
        thinking_history: list[dict[str, Any]] = []
        error_count = 0

        # Execute up to max_iters + 1 rounds
        for _round in range(max(0, max_iters) + 1):
            # Get API key
            api_key = self.vault.get("OPENROUTER_API_KEY")
            if not api_key:
                raise ValueError("OPENROUTER_API_KEY not found in vault")

            # Prepare model and options
            web_search_options = self._prepare_web_search_options()
            base_model = str(self.params.get("model", "z-ai/glm-4.6"))
            model_with_web_search = self._get_model_with_web_search(base_model)

            # Call LLM to get tool calls
            request_body = {
                "model": model_with_web_search,
                "messages": messages,
                "tools": tools,
                "tool_choice": self.params.get("tool_choice") if tools else None,
                "stream": False,
                **options,
                **web_search_options,
            }

            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    "https://openrouter.ai/api/v1/chat/completions",
                    headers={
                        "Authorization": f"Bearer {api_key}",
                        "Content-Type": "application/json",
                    },
                    json=request_body,
                )
                response.raise_for_status()
                resp_data_raw = response.json()

                # Validate and parse response using Pydantic
                resp_data_model = OpenRouterChatResponseModel.model_validate(resp_data_raw)
            # Extract message and tool calls
            if not resp_data_model.choices:
                break
            first_choice = resp_data_model.choices[0]
            if first_choice.message:
                message: dict[str, Any] = first_choice.message.model_dump()
            else:
                message = {"role": "assistant", "content": ""}
            tool_calls_raw: Any = message.get("tool_calls")
            tool_calls: list[OpenRouterToolCall] | None = (
                tool_calls_raw if isinstance(tool_calls_raw, list) else None
            )

            # No tool calls means we're done
            if not tool_calls:
                break

            # Execute all tools in parallel
            tasks = [self._execute_single_tool(call, timeout_s) for call in tool_calls]
            results = await asyncio.gather(*tasks, return_exceptions=True)

            # Process results and append to messages
            round_errors = 0
            for result in results:
                if isinstance(result, Exception):
                    round_errors += 1
                    error_count += 1
                    continue

                call, result_obj = cast(tuple[OpenRouterToolCall, dict[str, Any]], result)

                # Track errors
                if result_obj.get("error"):
                    round_errors += 1
                    error_count += 1

                # Serialize result to JSON string
                try:
                    content_str = json.dumps(result_obj, ensure_ascii=False)
                except Exception:
                    content_str = str(result_obj)

                # Append tool result to messages
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": call.get("id"),
                        "content": content_str,
                    }
                )

                # Track in history
                tool_history.append({"call": call, "result": result_obj})

            # Stop if too many errors (either this round or overall)
            tool_calls_count = len(tool_calls) if tool_calls else 0
            if round_errors > tool_calls_count // 2 or error_count > max_iters:
                break

        return {
            "messages": messages,
            "tool_history": tool_history,
            "thinking_history": thinking_history,
        }

    def _ensure_assistant_role_inplace(self, message: dict[str, Any]) -> None:
        if "role" not in message:
            message["role"] = "assistant"

    def _parse_tool_calls_from_message(self, message: dict[str, Any]):
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
                    tool_call: dict[str, Any] = {
                        "function": {"name": "web_search", "arguments": {"query": query}}
                    }
                    if "tool_calls" not in message:
                        message["tool_calls"] = []
                    tool_calls_list: list[dict[str, Any]] = cast(
                        list[dict[str, Any]], message["tool_calls"]
                    )
                    if tool_call not in tool_calls_list:
                        tool_calls_list.append(tool_call)
                        message["tool_calls"] = tool_calls_list
        if message.get("tool_calls"):
            complete_calls: list[dict[str, Any]] = [
                cast(dict[str, Any], call)
                for call in message["tool_calls"]
                if self._is_complete_tool_call(cast(dict[str, Any], call))
            ]
            if complete_calls:
                message["tool_name"] = complete_calls[0]["function"]["name"]
            else:
                message["tool_name"] = None
        else:
            message["tool_name"] = None

    def _is_complete_tool_call(self, call: dict[str, Any]) -> bool:
        return call.get("function", {}).get("name") and call.get("function", {}).get("arguments")

    # Main Execute Implementation
    async def _execute_impl(self, inputs: dict[str, Any]) -> dict[str, Any]:
        raw_messages: list[LLMChatMessage] | None = inputs.get("messages")
        prompt_text: str | None = inputs.get("prompt")
        system_input: LLMChatMessage | None = inputs.get("system")

        messages: list[LLMChatMessage] = self._build_messages(
            raw_messages, prompt_text, system_input
        )
        tools: list[LLMToolSpec] = self._collect_tools(inputs)

        if not messages:
            error_msg = "No messages or prompt provided to OpenRouterChatNode"
            return {
                "message": {"role": "assistant", "content": ""},
                "metrics": {"error": error_msg},
                "tool_history": [],
                "thinking_history": [],
            }

        # Early explicit API key check so the graph surfaces a clear failure without silent fallthrough
        api_key_early = self.vault.get("OPENROUTER_API_KEY")
        if not api_key_early:
            return {
                "message": {
                    "role": "assistant",
                    "content": "OpenRouter API key missing. Set OPENROUTER_API_KEY.",
                },
                "metrics": {"error": "OPENROUTER_API_KEY not found in vault"},
                "tool_history": [],
                "thinking_history": [],
            }

        options = self._prepare_generation_options()

        tool_choice = str(self.params.get("tool_choice", "auto")).strip().lower()

        tool_rounds_info: dict[str, Any] = {"tool_history": [], "thinking_history": []}

        if tool_choice in ["auto", "required"] and tools:
            tool_rounds_info = await self._maybe_execute_tools_and_augment_messages(
                messages, tools, options
            )
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
        base_model = str(self.params.get("model", "z-ai/glm-4.6"))
        model_with_web_search = self._get_model_with_web_search(base_model)

        request_body = {
            "model": model_with_web_search,
            "messages": messages,
            "tools": final_tools,
            "tool_choice": final_tool_choice if final_tools else None,
            "stream": False,
            **options,
            **web_search_options,
        }

        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json=request_body,
            )
            response.raise_for_status()
            resp_data_raw = response.json()

            # Validate and parse response using Pydantic
            resp_data_model = OpenRouterChatResponseModel.model_validate(resp_data_raw)

        final_message: dict[str, Any] = (
            resp_data_model.choices[0].message.model_dump()
            if resp_data_model.choices
            else {"role": "assistant", "content": ""}
        )
        self._ensure_assistant_role_inplace(final_message)
        self._parse_tool_calls_from_message(final_message)

        # Parse JSON response if json_mode is enabled
        content = final_message.get("content")
        if bool(self.params.get("json_mode", False)) and isinstance(content, str):
            try:
                final_message["content"] = json.loads(content)
            except json.JSONDecodeError:
                pass  # Keep as string if parsing fails

        usage_dict = resp_data_model.usage.model_dump() if resp_data_model.usage else {}
        metrics: dict[str, Any] = {
            "prompt_tokens": usage_dict.get("prompt_tokens", 0),
            "completion_tokens": usage_dict.get("completion_tokens", 0),
            "total_tokens": usage_dict.get("total_tokens", 0),
            "temperature": options.get("temperature"),
            "seed": options.get("seed"),
        }

        # Query detailed generation stats if available
        generation_id: str | None = resp_data_model.id
        if generation_id and api_key:
            try:
                async with httpx.AsyncClient(timeout=10.0) as client:
                    gen_response = await client.get(
                        f"https://openrouter.ai/api/v1/generation?id={generation_id}",
                        headers={
                            "Authorization": f"Bearer {api_key}",
                        },
                    )
                    gen_response.raise_for_status()
                    gen_data: OpenRouterGenerationResponse = gen_response.json()
                    if gen_data.get("data"):
                        gen_metrics = gen_data["data"]
                        # Merge additional metrics like cost, native tokens, etc.
                        for key in [
                            "total_cost",
                            "native_tokens_prompt",
                            "native_tokens_completion",
                            "latency",
                            "generation_time",
                        ]:
                            if key in gen_metrics:
                                metrics[key] = gen_metrics[key]
            except Exception:
                # Silently ignore generation API failures
                pass

        return {
            "message": final_message,
            "metrics": metrics,
            "tool_history": tool_rounds_info.get("tool_history", []),
            "thinking_history": tool_rounds_info.get("thinking_history", []),
        }
