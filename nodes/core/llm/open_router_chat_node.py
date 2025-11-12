import asyncio
import random
from typing import Any, Literal, NotRequired, TypedDict, TypeGuard

import aiohttp
from pydantic import BaseModel

from core.api_key_vault import APIKeyVault
from core.types_registry import ConfigDict, NodeCategory, get_type
from nodes.base.base_node import Base


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
class OpenRouterChatMessageModel(BaseModel):
    role: str
    content: str | None = None


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
    """
    Node that connects to the OpenRouter API and allows for chat with LLMs. Web search is always enabled by default.
    Supports multimodal inputs with images for vision-capable models.

    Inputs:
    - message_0 to message_4: LLMChatMessage (optional individual messages to include in chat history)
    - prompt: str (optional prompt to add to the chat as user message)
    - system: str or LLMChatMessage (optional system message to add to the chat)
    - images: ConfigDict (optional dict of label to base64 data URL for images to attach to the user prompt)

    Outputs:
    - message: Dict[str, Any] (assistant message with role, content, etc.)
    - metrics: Dict[str, Any] (generation stats like durations and token counts)
    - thinking_history: List[Dict[str, Any]] (always empty list, kept for API compatibility)

    Properties:
    - model: str (model to use for the chat)
    - temperature: float (temperature for the chat)
    - max_tokens: int (maximum number of tokens to generate)
    - seed: int (seed for the chat)
    - seed_mode: str (mode for the seed)
    - use_vision: str (combo: "true" or "false" - automatically select vision-capable model if images provided)
    """

    inputs = {
        "prompt": str | None,
        "system": str | dict[str, Any] | None,
        "images": ConfigDict | None,
        **{f"message_{i}": dict[str, Any] | None for i in range(5)},
    }

    outputs = {
        "message": dict[str, Any],
        "metrics": get_type("LLMChatMetrics"),
        "thinking_history": get_type("LLMThinkingHistory"),
    }

    CATEGORY = NodeCategory.LLM

    # Need open router API key
    required_keys = ["OPENROUTER_API_KEY"]

    # Constants
    _DEFAULT_ASSISTANT_MESSAGE = {"role": "assistant", "content": ""}

    default_params = {
        "model": "z-ai/glm-4.6",  # Default model (text-capable; will switch if use_vision)
        "temperature": 0.7,
        "max_tokens": 2048,
        "seed": 0,
        "seed_mode": "fixed",  # fixed | random | increment
        "use_vision": "false",
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
            "default": 20000,
            "min": 1,
            "step": 1,
            "precision": 0,
        },
        {"name": "seed", "type": "number", "default": 0, "min": 0, "step": 1, "precision": 0},
        {
            "name": "seed_mode",
            "type": "combo",
            "default": "fixed",
            "options": ["fixed", "random", "increment"],
        },
        {
            "name": "use_vision",
            "type": "combo",
            "default": "false",
            "options": ["true", "false"],
            "description": "Enable vision mode for image inputs (auto-switches to vision-capable model)",
        },
    ]

    def __init__(
        self, id: int, params: dict[str, Any], graph_context: dict[str, Any] | None = None
    ):
        super().__init__(id, params, graph_context)
        self.optional_inputs = ["prompt", "system", "images"] + [f"message_{i}" for i in range(5)]
        # Maintain seed state for increment mode
        self._seed_state: int | None = None
        self.vault = APIKeyVault()
        self._session: aiohttp.ClientSession | None = None

    def force_stop(self):
        """Override to close aiohttp session and cancel inflight requests immediately."""
        super().force_stop()  # Call base implementation
        if self._session and not self._session.closed:
            print(f"STOP_TRACE: Closing aiohttp session for node {self.id}")
            # Schedule session close in event loop
            asyncio.create_task(self._session.close())

    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create aiohttp session."""
        if self._session is None or self._session.closed:
            timeout = aiohttp.ClientTimeout(total=120)
            self._session = aiohttp.ClientSession(timeout=timeout)
        return self._session

    def _extract_message_from_response(
        self, response_model: OpenRouterChatResponseModel | None
    ) -> dict[str, Any]:
        """Extract message from response model."""
        if response_model and response_model.choices:
            first_choice = response_model.choices[0]
            if first_choice.message:
                return first_choice.message.model_dump()
        return self._DEFAULT_ASSISTANT_MESSAGE.copy()

    def _create_error_response(self, error_msg: str) -> dict[str, Any]:
        """Create standardized error response."""
        return {
            "message": self._DEFAULT_ASSISTANT_MESSAGE.copy(),
            "metrics": {"error": error_msg},
            "thinking_history": [],
        }

    @staticmethod
    def _build_messages(
        existing_messages: list[dict[str, Any]] | None,
        prompt: str | None,
        system_input: dict[str, Any] | str | None,
        images: ConfigDict | None = None,
    ) -> list[dict[str, Any]]:
        result: list[dict[str, Any]] = list(existing_messages or []) if existing_messages else []
        if system_input and not any(m.get("role") == "system" for m in result):
            if isinstance(system_input, str):
                result.insert(0, {"role": "system", "content": system_input})
            else:
                result.insert(0, system_input)

        # Build final user message with images if provided
        text_content = prompt or ""
        if text_content.strip() or images:
            user_content: list[dict[str, Any]] = []
            if text_content.strip():
                user_content.append({"type": "text", "text": text_content})
            else:
                user_content.append({"type": "text", "text": ""})

            if images:
                # Append image parts (order: text first, then images)
                for data_url in images.values():
                    if isinstance(data_url, str) and data_url.startswith("data:image/"):
                        user_content.append(
                            {
                                "type": "image_url",
                                "image_url": {"url": data_url},  # Direct base64 data URL
                            }
                        )
            result.append({"role": "user", "content": user_content})
        return result

    def _prepare_generation_options(self) -> dict[str, Any]:
        options: dict[str, Any] = {}
        temperature_raw = self.params.get("temperature")
        if temperature_raw is not None:
            options["temperature"] = (
                float(temperature_raw) if isinstance(temperature_raw, str) else temperature_raw
            )
        # Inline parsing for max_tokens with type check
        max_tokens_raw = self.params.get("max_tokens")
        if max_tokens_raw is not None and isinstance(max_tokens_raw, int | float | str):
            try:
                options["max_tokens"] = int(max_tokens_raw)
            except (ValueError, TypeError):
                options["max_tokens"] = 1024  # default
        else:
            options["max_tokens"] = 1024

        seed_mode = str(self.params.get("seed_mode") or "fixed").strip().lower()
        seed_raw = self.params.get("seed")
        effective_seed: int | None = None
        # Inline parsing for seed with type check
        if seed_raw is not None and isinstance(seed_raw, int | float | str):
            try:
                base_seed = int(seed_raw)
            except (ValueError, TypeError):
                base_seed = 0
        else:
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
        return options

    def _get_model_with_web_search(self, base_model: str, use_vision: bool = False) -> str:
        """Get model name with web search suffix (always enabled). Switch to vision model if needed."""
        model = base_model
        if use_vision:
            # Map to a vision-capable model if the base isn't (customize as needed)
            vision_models = ["google/gemini-2.0-flash-001", "openai/gpt-4o"]  # Examples
            if not any(vm in model for vm in vision_models):
                model = "google/gemini-2.0-flash-001"  # Default vision fallback
        # Add :online suffix to enable web search
        if not model.endswith(":online"):
            model = f"{model}:online"
        return model

    async def _call_llm(
        self,
        messages: list[dict[str, Any]],
        options: dict[str, Any],
        api_key: str,
    ) -> OpenRouterChatResponseModel:
        """Single entry point for LLM API calls."""
        use_vision_param = self._parse_bool_param("use_vision", False)
        base_model = str(self.params.get("model", "z-ai/glm-4.6"))
        model_with_web_search = self._get_model_with_web_search(base_model, use_vision_param)

        request_body = {
            "model": model_with_web_search,
            "messages": messages,
            "stream": False,
            **options,
        }

        if self._is_stopped:
            raise asyncio.CancelledError("Node stopped before HTTP request")

        session = await self._get_session()
        try:
            async with session.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json=request_body,
            ) as response:
                if self._is_stopped:
                    raise asyncio.CancelledError("Node stopped during HTTP request")

                response.raise_for_status()
                resp_data_raw = await response.json()
                return OpenRouterChatResponseModel.model_validate(resp_data_raw)
        except asyncio.CancelledError:
            print(f"STOP_TRACE: HTTP request cancelled for node {self.id}")
            raise

    def _parse_bool_param(self, param_name: str, default: bool = False) -> bool:
        """Parse a combo boolean parameter that can be string 'true'/'false' or actual bool."""
        value = self.params.get(param_name, default)
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            return value.lower() == "true"
        return bool(value)

    def _ensure_assistant_role_inplace(self, message: dict[str, Any]) -> None:
        if "role" not in message:
            message["role"] = "assistant"

    def _is_llm_chat_message(self, msg: Any) -> TypeGuard[dict[str, Any]]:
        """Type guard to validate LLMChatMessage structure."""
        return (
            isinstance(msg, dict)
            and "role" in msg
            and "content" in msg
            and isinstance(msg["role"], str)
            and msg["role"] in ("system", "user", "assistant", "tool")
        )

    async def _execute_impl(self, inputs: dict[str, Any]) -> dict[str, Any]:
        prompt_text: str | None = inputs.get("prompt")
        system_input: str | dict[str, Any] | None = inputs.get("system")
        images: ConfigDict | None = inputs.get("images")

        merged: list[dict[str, Any]] = []
        for i in range(5):
            msg = inputs.get(f"message_{i}")
            if msg:
                if self._is_llm_chat_message(msg):
                    merged.append(msg)
                else:
                    raise TypeError(f"Expected LLMChatMessage for message_{i}, got {type(msg)}")

        # Filter out empty messages
        filtered_messages: list[dict[str, Any]] = [
            m for m in merged if m and str(m.get("content") or "").strip()
        ]

        messages = self._build_messages(filtered_messages, prompt_text, system_input, images)

        if not messages:
            return self._create_error_response(
                "No valid messages, prompt, or system provided to OpenRouterChatNode"
            )

        # Early explicit API key check so the graph surfaces a clear failure without silent fallthrough
        api_key = self.vault.get("OPENROUTER_API_KEY")
        if not api_key:
            error_resp = self._create_error_response("OPENROUTER_API_KEY not found in vault")
            error_resp["message"]["content"] = "OpenRouter API key missing. Set OPENROUTER_API_KEY."
            return error_resp

        options = self._prepare_generation_options()

        # Enable vision if images present or param set
        use_vision = self._parse_bool_param("use_vision", False) or bool(images and images)

        # Single LLM call with web search enabled via :online suffix
        resp_data_model = await self._call_llm(messages, options, api_key)

        if not resp_data_model.choices:
            return self._create_error_response("No choices in response")

        final_message = self._extract_message_from_response(resp_data_model)

        # Process final message
        if not final_message:
            final_message = self._DEFAULT_ASSISTANT_MESSAGE.copy()

        self._ensure_assistant_role_inplace(final_message)

        # Extract metrics from response
        metrics: dict[str, Any] = {
            "temperature": options.get("temperature"),
            "seed": options.get("seed"),
            "use_vision": use_vision,
        }

        if resp_data_model:
            first_choice = resp_data_model.choices[0] if resp_data_model.choices else None
            finish_reason = first_choice.finish_reason if first_choice else None

            if finish_reason == "error":
                error_resp = self._create_error_response("finish_reason: error")
                error_resp["message"]["content"] = "API returned error"
                error_resp["metrics"].update(metrics)
                return error_resp

            usage_dict = resp_data_model.usage.model_dump() if resp_data_model.usage else {}
            metrics.update(
                {
                    "prompt_tokens": usage_dict.get("prompt_tokens", 0),
                    "completion_tokens": usage_dict.get("completion_tokens", 0),
                    "total_tokens": usage_dict.get("total_tokens", 0),
                    "finish_reason": finish_reason,
                }
            )

            if first_choice and first_choice.native_finish_reason:
                metrics["native_finish_reason"] = first_choice.native_finish_reason

            # Query detailed generation stats if available
            generation_id: str | None = resp_data_model.id
            if generation_id and api_key:
                try:
                    if not self._is_stopped:
                        session = await self._get_session()
                        async with session.get(
                            f"https://openrouter.ai/api/v1/generation?id={generation_id}",
                            headers={"Authorization": f"Bearer {api_key}"},
                        ) as gen_response:
                            gen_response.raise_for_status()
                            gen_data: OpenRouterGenerationResponse = await gen_response.json()
                            if gen_data.get("data"):
                                gen_metrics = gen_data["data"]
                                for key in [
                                    "total_cost",
                                    "native_tokens_prompt",
                                    "native_tokens_completion",
                                    "latency",
                                    "generation_time",
                                    "num_media_prompt",  # NEW: Include image count from generation stats
                                ]:
                                    if key in gen_metrics:
                                        metrics[key] = gen_metrics[key]
                except (Exception, asyncio.CancelledError):
                    pass

        return {
            "message": final_message,
            "metrics": metrics,
            "thinking_history": [],
        }
