import asyncio
import base64
import json
import logging
import random
from datetime import datetime
from typing import Any, Literal, NotRequired, TypedDict, TypeGuard

import aiohttp
from pydantic import BaseModel, ValidationError

from core.api_key_vault import APIKeyVault
from core.types_registry import ConfigDict, NodeCategory, NodeExecutionError, OHLCVBundle, get_type
from nodes.base.base_node import Base

logger = logging.getLogger(__name__)


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
    thinking: str | None = None  # Some models return thinking/reasoning


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


class SvensOpenRouterChat(Base):
    """
    Node that connects to the OpenRouter API and allows for chat with LLMs. Web search is always enabled by default.
    Supports multimodal inputs with images for vision-capable models.

    Inputs:
    - message_0 to message_3: LLMChatMessage (optional individual messages to include in chat history)
    - prompt: str (optional prompt to add to the chat as user message)
    - system: str or LLMChatMessage (optional system message to add to the chat)
    - images: ConfigDict (optional dict of label to base64 data URL for images to attach to the user prompt)
    - hurst_data: ConfigDict (optional Hurst spectral analysis data from HurstPlot node)
    - ohlcv_bundle: OHLCVBundle (optional OHLCV bars bundle from HurstPlot node)
    - mesa_data: ConfigDict (optional MESA Stochastic data from HurstPlot node)
    - cco_data: ConfigDict (optional Cycle Channel Oscillator data from HurstPlot node)

    Outputs:
    - message: Dict[str, Any] (assistant message with role, content, etc.)
    - metrics: Dict[str, Any] (generation stats like durations and token counts)
    - thinking_history: List[Dict[str, Any]] (thinking/reasoning from models that support it, empty list if not available)

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
        "hurst_data": ConfigDict | None,
        "ohlcv_bundle": OHLCVBundle | None,
        "mesa_data": ConfigDict | None,
        "cco_data": ConfigDict | None,
        **{f"message_{i}": dict[str, Any] | None for i in range(4)},
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
        "enable_thinking": "false",  # Enable thinking/reasoning mode (adds /think for Qwen, works for other models that support it)
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
            "precision": 2,
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
        {
            "name": "enable_thinking",
            "type": "combo",
            "default": "false",
            "options": ["true", "false"],
            "description": "Enable thinking/reasoning mode - shows model's reasoning process (slower but more transparent). Works with Qwen (/think) and other models that support thinking.",
        },
    ]

    def __init__(
        self, id: int, params: dict[str, Any], graph_context: dict[str, Any] | None = None
    ):
        super().__init__(id, params, graph_context)
        self.optional_inputs = ["prompt", "system", "images", "hurst_data", "ohlcv_bundle", "mesa_data", "cco_data"] + [f"message_{i}" for i in range(4)]
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
                # Use model_dump with exclude_none=False to include all fields
                message_dict = first_choice.message.model_dump(exclude_none=False)
                return message_dict
        return self._DEFAULT_ASSISTANT_MESSAGE.copy()

    def _create_error_response(self, error_msg: str) -> dict[str, Any]:
        """Create standardized error response."""
        return {
            "message": self._DEFAULT_ASSISTANT_MESSAGE.copy(),
            "metrics": {"error": error_msg},
            "thinking_history": [],
        }

    @staticmethod
    def _estimate_payload_size(messages: list[dict[str, Any]]) -> int:
        """Estimate payload size in bytes by serializing to JSON."""
        try:
            return len(json.dumps(messages, ensure_ascii=False).encode('utf-8'))
        except Exception:
            # Fallback: rough estimate based on string length
            return len(str(messages).encode('utf-8'))
    
    @staticmethod
    def _compress_image_data_url(data_url: str, max_size_bytes: int = 500_000) -> str:
        """Compress a base64 image data URL by reducing quality if needed.
        
        Returns the original data URL if it's already small enough, or a compressed version.
        For now, we'll just check size and warn - actual compression would require re-encoding.
        """
        if not isinstance(data_url, str) or not data_url.startswith("data:image/"):
            return data_url
        
        # Extract base64 part (after the comma)
        if "," not in data_url:
            return data_url
        
        header, base64_data = data_url.split(",", 1)
        # Base64 encoding increases size by ~33%, so actual image size is smaller
        # But for payload estimation, we use the base64 size
        base64_size = len(base64_data.encode('utf-8'))
        
        if base64_size <= max_size_bytes:
            return data_url
        
        # For now, return original but log warning
        # TODO: Implement actual compression (reduce DPI, convert to JPEG, etc.)
        return data_url
    
    @staticmethod
    def _build_messages(
        existing_messages: list[dict[str, Any]] | None,
        prompt: str | None,
        system_input: dict[str, Any] | str | None,
        images: ConfigDict | None = None,
        max_payload_size: int = 5_000_000,  # 5MB default limit
    ) -> tuple[list[dict[str, Any]], int]:
        """Build messages list and return it along with estimated payload size in bytes."""
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
                # Compress images if needed to stay within payload limits
                image_count = 0
                total_image_size = 0
                for data_url in images.values():
                    if isinstance(data_url, str) and data_url.startswith("data:image/"):
                        # Estimate image size (base64 part only)
                        if "," in data_url:
                            _, base64_part = data_url.split(",", 1)
                            img_size = len(base64_part.encode('utf-8'))
                            total_image_size += img_size
                            image_count += 1
                        
                        user_content.append(
                            {
                                "type": "image_url",
                                "image_url": {"url": data_url},  # Direct base64 data URL
                            }
                        )
                
                if image_count > 0:
                    avg_image_size = total_image_size / image_count
                    print(f"📊 SvensOpenRouterChat: {image_count} images, avg size: {avg_image_size/1024:.1f}KB, total: {total_image_size/1024/1024:.2f}MB")
            
            result.append({"role": "user", "content": user_content})
        
        # Estimate total payload size
        payload_size = SvensOpenRouterChat._estimate_payload_size(result)
        return result, payload_size

    def _prepare_generation_options(self) -> dict[str, Any]:
        options: dict[str, Any] = {}
        temperature_raw = self.params.get("temperature")
        if temperature_raw is not None:
            try:
                temp_value: float
                if isinstance(temperature_raw, str):
                    temp_value = float(temperature_raw)
                elif isinstance(temperature_raw, (int, float)):
                    temp_value = float(temperature_raw)
                else:
                    temp_value = 0.7  # default fallback
                
                # Ensure temperature is within valid range
                if temp_value < 0.0:
                    options["temperature"] = 0.0
                elif temp_value > 2.0:
                    options["temperature"] = 2.0
                else:
                    options["temperature"] = temp_value
            except (ValueError, TypeError):
                options["temperature"] = 0.7  # default fallback
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
            # Check if the model already supports vision (Qwen VL models, Gemini, GPT-4o, etc.)
            vision_capable_models = [
                "qwen/qwen-vl",  # Qwen VL models
                "qwen/vl",  # Alternative Qwen VL naming
                "google/gemini",  # Gemini models
                "openai/gpt-4o",  # GPT-4o
                "anthropic/claude",  # Claude models (some support vision)
            ]
            # Check if the base model already supports vision
            is_vision_capable = any(vm.lower() in model.lower() for vm in vision_capable_models)
            
            if not is_vision_capable:
                # Map to a vision-capable model if the base isn't
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

        # Enable reasoning for models that support it if thinking mode is enabled
        enable_thinking = self._parse_bool_param("enable_thinking", False)
        if enable_thinking:
            model_lower = base_model.lower()
            # Claude Sonnet 4.5 requires explicit reasoning parameter
            if "claude" in model_lower:
                if "reasoning" not in options:
                    options["reasoning"] = True
                    print(f"💭 Enabled reasoning parameter for Claude model")
            # Note: Qwen models enable thinking via /think prefix in prompt (handled elsewhere)
            # Qwen models may only return thinking in streaming mode, which is not currently supported
            # Do NOT add reasoning/thinking_mode parameters for Qwen as OpenRouter API rejects them
        
        # Final payload size check before sending
        request_body = {
            "model": model_with_web_search,
            "messages": messages,
            "stream": False,
            **options,
        }
        
        # Estimate final request size (including model name, options, etc.)
        try:
            final_payload_size = len(json.dumps(request_body, ensure_ascii=False).encode('utf-8'))
            final_payload_mb = final_payload_size / 1024 / 1024
            if final_payload_mb > 5.0:
                print(f"⚠️ Final request payload: {final_payload_mb:.2f}MB (may exceed API limits)")
        except Exception:
            pass  # Don't fail if we can't estimate

        if self._is_stopped:
            raise asyncio.CancelledError("Node stopped before HTTP request")

        session = await self._get_session()
        try:
            # Debug: Log key request details
            num_images = sum(1 for msg in messages if isinstance(msg.get("content"), list) and any(
                item.get("type") == "image_url" for item in msg.get("content", []) if isinstance(item, dict)
            ))
            print(f"🔵 SvensOpenRouterChat Node {self.id}: Sending request to OpenRouter API...")
            print(f"   Model: {model_with_web_search}")
            print(f"   Messages: {len(messages)}")
            print(f"   Images in request: {num_images}")
            print(f"   Options: temperature={options.get('temperature')}, max_tokens={options.get('max_tokens')}, seed={options.get('seed')}")
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

                print(f"🔵 SvensOpenRouterChat Node {self.id}: Received response status: {response.status}")
                
                # Read response body (we need to read it before raising for status to see error details)
                resp_data_raw = await response.json()
                
                if response.status >= 400:
                    # Log the error response details
                    error_details = resp_data_raw if isinstance(resp_data_raw, dict) else str(resp_data_raw)
                    print(f"❌ SvensOpenRouterChat Node {self.id}: API Error Response: {error_details}")
                    # Extract error message if available
                    if isinstance(resp_data_raw, dict):
                        error_info = resp_data_raw.get("error", {})
                        if isinstance(error_info, dict):
                            error_message = error_info.get("message", "Unknown error")
                            # Also log the full error structure for debugging
                            print(f"❌ SvensOpenRouterChat Node {self.id}: Error details: {error_info}")
                        else:
                            error_message = str(error_info)
                    else:
                        error_message = f"Bad Request (status {response.status})"
                    
                    # Create a ClientResponseError-like exception for consistency
                    from aiohttp import ClientResponseError
                    client_error = ClientResponseError(
                        request_info=response.request_info,
                        history=response.history,
                        status=response.status,
                        message=error_message,
                    )
                    
                    raise NodeExecutionError(
                        self.id,
                        f"OpenRouter API error ({response.status}): {error_message}",
                        original_exc=client_error,
                    )
                
                print(f"🔵 SvensOpenRouterChat Node {self.id}: Response parsed successfully")
                
                # Check for error in response (some APIs return 200 OK with error payload)
                if isinstance(resp_data_raw, dict) and "error" in resp_data_raw:
                    error_info = resp_data_raw.get("error", {})
                    error_message = error_info.get("message", "Unknown error") if isinstance(error_info, dict) else str(error_info)
                    raise NodeExecutionError(
                        self.id,
                        f"OpenRouter API returned error: {error_message}",
                        original_exc=ValueError(f"API error response: {resp_data_raw}"),
                    )
                
                # Store raw response for thinking extraction (before Pydantic validation)
                # Pydantic might drop fields not in the model
                raw_response_for_thinking = resp_data_raw.copy() if isinstance(resp_data_raw, dict) else None
                
                try:
                    validated_model = OpenRouterChatResponseModel.model_validate(resp_data_raw)
                    # Attach raw response for thinking extraction
                    validated_model._raw_response = raw_response_for_thinking  # type: ignore
                    return validated_model
                except ValidationError as ve:
                    # If validation fails, it might be an unexpected error response format
                    raise NodeExecutionError(
                        self.id,
                        f"Failed to parse OpenRouter API response: {ve}",
                        original_exc=ve,
                    ) from ve
        except asyncio.CancelledError:
            print(f"STOP_TRACE: HTTP request cancelled for node {self.id}")
            raise
        except NodeExecutionError:
            # Re-raise our custom errors
            raise
        except aiohttp.ClientResponseError as e:
            # Handle HTTP errors with specific messages for common status codes
            print(f"❌ SvensOpenRouterChat Node {self.id}: HTTP error {e.status}: {e.message}")
            if e.status == 400:
                raise NodeExecutionError(
                    self.id,
                    f"OpenRouter API bad request (400). Invalid request format or parameters. "
                    f"Check your prompt, images, or model selection.",
                    original_exc=e,
                ) from e
            elif e.status == 401:
                raise NodeExecutionError(
                    self.id,
                    f"OpenRouter API authentication failed (401 Unauthorized). "
                    f"Please check your API key in the API Key Vault.",
                    original_exc=e,
                ) from e
            elif e.status == 402:
                raise NodeExecutionError(
                    self.id,
                    f"OpenRouter API payment required (402). Your account or API key has insufficient credits. "
                    f"Please add credits to your OpenRouter account.",
                    original_exc=e,
                ) from e
            elif e.status == 403:
                raise NodeExecutionError(
                    self.id,
                    f"OpenRouter API forbidden (403). Your input may be flagged by moderation, "
                    f"or your API key may not have permission for this model or operation.",
                    original_exc=e,
                ) from e
            elif e.status == 404:
                raise NodeExecutionError(
                    self.id,
                    f"OpenRouter API endpoint not found (404). The model or endpoint may not exist.",
                    original_exc=e,
                ) from e
            elif e.status == 408:
                raise NodeExecutionError(
                    self.id,
                    f"OpenRouter API request timeout (408). Your request took too long to process. "
                    f"Consider reducing payload size or number of images.",
                    original_exc=e,
                ) from e
            elif e.status == 429:
                raise NodeExecutionError(
                    self.id,
                    f"OpenRouter API rate limit exceeded (429 Too Many Requests). "
                    f"Please wait before retrying. Consider reducing the number of images or request frequency.",
                    original_exc=e,
                ) from e
            elif e.status == 500:
                raise NodeExecutionError(
                    self.id,
                    f"OpenRouter API internal server error (500). This is a server-side issue. Please try again later.",
                    original_exc=e,
                ) from e
            elif e.status == 502:
                raise NodeExecutionError(
                    self.id,
                    f"OpenRouter API bad gateway (502). The API gateway is experiencing issues. Please try again later.",
                    original_exc=e,
                ) from e
            elif e.status == 503:
                raise NodeExecutionError(
                    self.id,
                    f"OpenRouter API service temporarily unavailable (503). Please try again later.",
                    original_exc=e,
                ) from e
            elif e.status == 504:
                raise NodeExecutionError(
                    self.id,
                    f"OpenRouter API gateway timeout (504). The request took too long. Consider reducing payload size or retrying.",
                    original_exc=e,
                ) from e
            else:
                raise NodeExecutionError(
                    self.id,
                    f"OpenRouter API call failed with HTTP {e.status}: {e.message}",
                    original_exc=e,
                ) from e
        except Exception as e:
            # Catch any other exceptions (network issues, etc.)
            print(f"❌ SvensOpenRouterChat Node {self.id}: Unexpected exception: {type(e).__name__}: {str(e)}")
            import traceback
            print(f"   Traceback: {traceback.format_exc()}")
            raise NodeExecutionError(
                self.id,
                f"OpenRouter API call failed: {str(e)}",
                original_exc=e,
            ) from e

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

    def _format_hurst_data(self, hurst_data: ConfigDict) -> str:
        """Format Hurst spectral analysis data into readable text for LLM analysis."""
        if not hurst_data:
            return ""
        
        lines: list[str] = []
        lines.append("\n=== HURST SPECTRAL ANALYSIS DATA ===\n")
        
        for symbol, data in hurst_data.items():
            if not isinstance(data, dict):
                continue
                
            lines.append(f"\n--- {symbol} ---")
            
            # Metadata
            metadata = data.get("metadata", {})
            if metadata:
                lines.append(f"Analysis Parameters:")
                lines.append(f"  Source: {metadata.get('source', 'N/A')}")
                lines.append(f"  Bandwidth: {metadata.get('bandwidth', 'N/A')}")
                lines.append(f"  Periods: {metadata.get('periods', 'N/A')}")
                lines.append(f"  Total Bars: {metadata.get('total_bars', 'N/A')}")
                lines.append(f"  Display Bars: {metadata.get('display_bars', 'N/A')}")
            
            # Composite oscillator
            composite = data.get("composite", [])
            if composite:
                # Show last 20 values and summary stats
                valid_composite = [v for v in composite if v is not None]
                if valid_composite:
                    recent_composite = valid_composite[-20:] if len(valid_composite) > 20 else valid_composite
                    lines.append(f"\nComposite Oscillator (last {len(recent_composite)} values):")
                    for i, val in enumerate(recent_composite):
                        lines.append(f"  [{len(valid_composite) - len(recent_composite) + i}]: {val:.6f}")
                    if len(valid_composite) > 20:
                        lines.append(f"  ... ({len(valid_composite) - 20} more values)")
                    lines.append(f"  Current: {valid_composite[-1]:.6f}")
                    lines.append(f"  Min: {min(valid_composite):.6f}, Max: {max(valid_composite):.6f}")
            
            # Bandpasses
            bandpasses = data.get("bandpasses", {})
            if bandpasses:
                lines.append(f"\nBandpass Waves:")
                for period_name, values in bandpasses.items():
                    if isinstance(values, list):
                        valid_values = [v for v in values if v is not None]
                        if valid_values:
                            recent_values = valid_values[-10:] if len(valid_values) > 10 else valid_values
                            lines.append(f"  {period_name} (last {len(recent_values)} values):")
                            for i, val in enumerate(recent_values):
                                lines.append(f"    [{len(valid_values) - len(recent_values) + i}]: {val:.6f}")
                            if len(valid_values) > 10:
                                lines.append(f"    ... ({len(valid_values) - 10} more values)")
                            lines.append(f"    Current: {valid_values[-1]:.6f}")
            
            # Peaks and troughs
            peaks = data.get("peaks", [])
            troughs = data.get("troughs", [])
            if peaks:
                lines.append(f"\nRecent Peaks: {len(peaks)} total")
                for peak in peaks[-5:]:  # Last 5 peaks
                    if isinstance(peak, dict):
                        idx = peak.get("index", "N/A")
                        val = peak.get("value", "N/A")
                        lines.append(f"  Peak at index {idx}: {val}")
            if troughs:
                lines.append(f"\nRecent Troughs: {len(troughs)} total")
                for trough in troughs[-5:]:  # Last 5 troughs
                    if isinstance(trough, dict):
                        idx = trough.get("index", "N/A")
                        val = trough.get("value", "N/A")
                        lines.append(f"  Trough at index {idx}: {val}")
            
            # Wavelength and amplitude
            wavelength = data.get("wavelength")
            amplitude = data.get("amplitude")
            if wavelength is not None:
                lines.append(f"\nWavelength: {wavelength}")
            if amplitude is not None:
                lines.append(f"Amplitude: {amplitude}")
        
        return "\n".join(lines)

    def _format_mesa_data(self, mesa_data: ConfigDict) -> str:
        """Format MESA Stochastic data into readable text for LLM analysis."""
        if not mesa_data:
            return ""
        
        lines: list[str] = []
        lines.append("\n=== MESA STOCHASTIC MULTI LENGTH DATA ===\n")
        
        for symbol, data in mesa_data.items():
            if not isinstance(data, dict):
                continue
                
            lines.append(f"\n--- {symbol} ---")
            
            # Metadata
            metadata = data.get("metadata", {})
            if metadata:
                lines.append(f"MESA Stochastic Parameters:")
                lines.append(f"  Length 1: {metadata.get('length1', 'N/A')}")
                lines.append(f"  Length 2: {metadata.get('length2', 'N/A')}")
                lines.append(f"  Length 3: {metadata.get('length3', 'N/A')}")
                lines.append(f"  Length 4: {metadata.get('length4', 'N/A')}")
                lines.append(f"  Trigger Length: {metadata.get('trigger_length', 'N/A')}")
                lines.append(f"  Total Bars: {metadata.get('total_bars', 'N/A')}")
                lines.append(f"  Display Bars: {metadata.get('display_bars', 'N/A')}")
            
            # MESA Stochastic values (mesa1, mesa2, mesa3, mesa4)
            for mesa_key in ["mesa1", "mesa2", "mesa3", "mesa4"]:
                mesa_values = data.get(mesa_key, [])
                if isinstance(mesa_values, list) and mesa_values:
                    valid_values = [v for v in mesa_values if v is not None and isinstance(v, (int, float))]
                    if valid_values:
                        recent_values = valid_values[-20:] if len(valid_values) > 20 else valid_values
                        lines.append(f"\n{mesa_key.upper()} (last {len(recent_values)} values):")
                        for i, val in enumerate(recent_values):
                            lines.append(f"  [{len(valid_values) - len(recent_values) + i}]: {val:.6f}")
                        if len(valid_values) > 20:
                            lines.append(f"  ... ({len(valid_values) - 20} more values)")
                        lines.append(f"  Current: {valid_values[-1]:.6f}")
                        lines.append(f"  Min: {min(valid_values):.6f}, Max: {max(valid_values):.6f}")
                        lines.append(f"  Mean: {sum(valid_values) / len(valid_values):.6f}")
        
        return "\n".join(lines)

    def _format_ohlcv_bundle(self, ohlcv_bundle: ConfigDict) -> str:
        """Format OHLCV bars bundle into readable text for LLM analysis."""
        if not ohlcv_bundle:
            return ""
        
        lines: list[str] = []
        lines.append("\n=== OHLCV PRICE DATA ===\n")
        
        for symbol, bars in ohlcv_bundle.items():
            if not isinstance(bars, list):
                continue
            
            lines.append(f"\n--- {symbol} ---")
            lines.append(f"Total Bars: {len(bars)}")
            
            if not bars:
                continue
            
            # Show first and last few bars
            preview_count = min(5, len(bars))
            lines.append(f"\nFirst {preview_count} bars:")
            for i, bar in enumerate(bars[:preview_count]):
                if isinstance(bar, dict) and all(k in bar for k in ("timestamp", "open", "high", "low", "close", "volume")):
                    ts = bar["timestamp"]
                    dt = datetime.fromtimestamp(ts / 1000) if isinstance(ts, (int, float)) else "N/A"
                    lines.append(
                        f"  [{i}] {dt}: O={bar['open']:.4f} H={bar['high']:.4f} "
                        f"L={bar['low']:.4f} C={bar['close']:.4f} V={bar['volume']:.2f}"
                    )
            
            if len(bars) > preview_count * 2:
                lines.append(f"\n... ({len(bars) - preview_count * 2} bars) ...\n")
            
            # Show last few bars
            if len(bars) > preview_count:
                lines.append(f"Last {preview_count} bars:")
                for i, bar in enumerate(bars[-preview_count:]):
                    if isinstance(bar, dict) and all(k in bar for k in ("timestamp", "open", "high", "low", "close", "volume")):
                        ts = bar["timestamp"]
                        dt = datetime.fromtimestamp(ts / 1000) if isinstance(ts, (int, float)) else "N/A"
                        idx = len(bars) - preview_count + i
                        lines.append(
                            f"  [{idx}] {dt}: O={bar['open']:.4f} H={bar['high']:.4f} "
                            f"L={bar['low']:.4f} C={bar['close']:.4f} V={bar['volume']:.2f}"
                        )
            
            # Summary stats
            if bars:
                closes = [float(bar["close"]) for bar in bars if isinstance(bar, dict) and "close" in bar]
                if closes:
                    lines.append(f"\nPrice Summary:")
                    lines.append(f"  First Close: ${closes[0]:.4f}")
                    lines.append(f"  Last Close: ${closes[-1]:.4f}")
                    lines.append(f"  Min: ${min(closes):.4f}, Max: ${max(closes):.4f}")
                    if len(closes) > 1:
                        change_pct = ((closes[-1] - closes[0]) / closes[0]) * 100
                        lines.append(f"  Change: {change_pct:+.2f}%")
        
        return "\n".join(lines)

    def _format_cco_data(self, cco_data: ConfigDict) -> str:
        """Format Cycle Channel Oscillator (CCO) data into readable text for LLM analysis."""
        if not cco_data:
            return ""
        
        lines: list[str] = []
        lines.append("\n=== CYCLE CHANNEL OSCILLATOR (CCO) DATA ===\n")
        
        for symbol, data in cco_data.items():
            if not isinstance(data, dict):
                continue
                
            lines.append(f"\n--- {symbol} ---")
            
            # Metadata
            metadata = data.get("metadata", {})
            if metadata:
                lines.append(f"CCO Parameters:")
                lines.append(f"  Short Cycle Length: {metadata.get('short_cycle_length', 'N/A')}")
                lines.append(f"  Medium Cycle Length: {metadata.get('medium_cycle_length', 'N/A')}")
                lines.append(f"  Short Cycle Multiplier: {metadata.get('short_cycle_multiplier', 'N/A')}")
                lines.append(f"  Medium Cycle Multiplier: {metadata.get('medium_cycle_multiplier', 'N/A')}")
                lines.append(f"  Total Bars: {metadata.get('total_bars', 'N/A')}")
                lines.append(f"  Display Bars: {metadata.get('display_bars', 'N/A')}")
            
            # Fast oscillator (oshort)
            fast_osc = data.get("fast_osc", [])
            if isinstance(fast_osc, list) and fast_osc:
                valid_fast = [v for v in fast_osc if v is not None and isinstance(v, (int, float))]
                if valid_fast:
                    recent_fast = valid_fast[-20:] if len(valid_fast) > 20 else valid_fast
                    lines.append(f"\nFast Oscillator (FastOsc) - Price location within medium-term channel (last {len(recent_fast)} values):")
                    for i, val in enumerate(recent_fast):
                        lines.append(f"  [{len(valid_fast) - len(recent_fast) + i}]: {val:.6f}")
                    if len(valid_fast) > 20:
                        lines.append(f"  ... ({len(valid_fast) - 20} more values)")
                    lines.append(f"  Current: {valid_fast[-1]:.6f}")
                    lines.append(f"  Min: {min(valid_fast):.6f}, Max: {max(valid_fast):.6f}")
                    lines.append(f"  Mean: {sum(valid_fast) / len(valid_fast):.6f}")
            
            # Slow oscillator (omed)
            slow_osc = data.get("slow_osc", [])
            valid_slow: list[float] = []
            if isinstance(slow_osc, list) and slow_osc:
                valid_slow = [v for v in slow_osc if v is not None and isinstance(v, (int, float))]
                if valid_slow:
                    recent_slow = valid_slow[-20:] if len(valid_slow) > 20 else valid_slow
                    lines.append(f"\nSlow Oscillator (SlowOsc) - Short-term midline location within medium-term channel (last {len(recent_slow)} values):")
                    for i, val in enumerate(recent_slow):
                        lines.append(f"  [{len(valid_slow) - len(recent_slow) + i}]: {val:.6f}")
                    if len(valid_slow) > 20:
                        lines.append(f"  ... ({len(valid_slow) - 20} more values)")
                    lines.append(f"  Current: {valid_slow[-1]:.6f}")
                    lines.append(f"  Min: {min(valid_slow):.6f}, Max: {max(valid_slow):.6f}")
                    lines.append(f"  Mean: {sum(valid_slow) / len(valid_slow):.6f}")
            
            # Interpretation notes
            valid_fast: list[float] = []
            if isinstance(fast_osc, list) and fast_osc:
                valid_fast = [v for v in fast_osc if v is not None and isinstance(v, (int, float))]
            
            if valid_fast and valid_slow:
                current_fast = valid_fast[-1]
                current_slow = valid_slow[-1]
                lines.append(f"\nInterpretation:")
                if current_fast >= 1.0:
                    lines.append(f"  Fast Oscillator >= 1.0: Price is above medium-term channel (overbought)")
                elif current_fast <= 0.0:
                    lines.append(f"  Fast Oscillator <= 0.0: Price is below medium-term channel (oversold)")
                else:
                    lines.append(f"  Fast Oscillator: {current_fast:.2%} of way through medium-term channel")
                
                if current_slow >= 1.0:
                    lines.append(f"  Slow Oscillator >= 1.0: Short-term midline is above medium-term channel")
                elif current_slow <= 0.0:
                    lines.append(f"  Slow Oscillator <= 0.0: Short-term midline is below medium-term channel")
                else:
                    lines.append(f"  Slow Oscillator: {current_slow:.2%} of way through medium-term channel")
        
        return "\n".join(lines)

    async def _execute_impl(self, inputs: dict[str, Any]) -> dict[str, Any]:
        prompt_text: str | None = inputs.get("prompt")
        system_input: str | dict[str, Any] | None = inputs.get("system")
        images: ConfigDict | None = inputs.get("images")
        hurst_data: ConfigDict | None = inputs.get("hurst_data")
        ohlcv_bundle: ConfigDict | None = inputs.get("ohlcv_bundle")
        mesa_data: ConfigDict | None = inputs.get("mesa_data")
        cco_data: ConfigDict | None = inputs.get("cco_data")

        # Combine prompt with formatted Hurst data, MESA data, CCO data, and OHLCV bars
        combined_prompt_parts: list[str] = []
        if prompt_text:
            combined_prompt_parts.append(prompt_text)
        
        if hurst_data:
            hurst_text = self._format_hurst_data(hurst_data)
            if hurst_text:
                combined_prompt_parts.append(hurst_text)
        
        if mesa_data:
            mesa_text = self._format_mesa_data(mesa_data)
            if mesa_text:
                combined_prompt_parts.append(mesa_text)
        
        if cco_data:
            cco_text = self._format_cco_data(cco_data)
            if cco_text:
                combined_prompt_parts.append(cco_text)
        
        if ohlcv_bundle:
            ohlcv_text = self._format_ohlcv_bundle(ohlcv_bundle)
            if ohlcv_text:
                combined_prompt_parts.append(ohlcv_text)
        
        # Use combined prompt if we have any content
        final_prompt: str | None = "\n".join(combined_prompt_parts) if combined_prompt_parts else None

        # Enable thinking mode if requested
        enable_thinking = self._parse_bool_param("enable_thinking", False)
        if enable_thinking:
            model = str(self.params.get("model") or "")
            # Check if /think is already in prompt or system
            prompt_has_think = final_prompt and "/think" in final_prompt.lower()
            system_has_think = False
            if isinstance(system_input, str):
                system_has_think = "/think" in system_input.lower()
            elif isinstance(system_input, dict) and "content" in system_input:
                system_has_think = "/think" in str(system_input.get("content", "")).lower()
            
            if not prompt_has_think and not system_has_think:
                # Prepend /think to prompt (works for Qwen and other models that support it)
                if final_prompt:
                    final_prompt = f"/think\n\n{final_prompt}"
                elif system_input:
                    if isinstance(system_input, str):
                        system_input = f"/think\n\n{system_input}"
                    elif isinstance(system_input, dict):
                        modified_system = system_input.copy()
                        current_content = str(modified_system.get("content", ""))
                        modified_system["content"] = f"/think\n\n{current_content}"
                        system_input = modified_system
                else:
                    # If neither exists, add /think as prompt
                    final_prompt = "/think"
                print(f"💭 Thinking mode enabled for model: {model}")

        merged: list[dict[str, Any]] = []
        for i in range(4):
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

        messages, payload_size = self._build_messages(filtered_messages, final_prompt, system_input, images)

        if not messages:
            return self._create_error_response(
                "No valid messages, prompt, or system provided to SvensOpenRouterChatNode"
            )
        
        # Check payload size and warn if too large
        payload_size_mb = payload_size / 1024 / 1024
        max_payload_mb = 5.0  # OpenRouter typically allows up to 5MB, but can vary
        
        if payload_size_mb > max_payload_mb:
            warning_msg = (
                f"⚠️ Payload size ({payload_size_mb:.2f}MB) exceeds recommended limit ({max_payload_mb}MB). "
                f"This may cause API errors. Consider reducing the number of images or their resolution."
            )
            print(warning_msg)
            # Still try to send, but warn the user
        else:
            print(f"✅ Payload size: {payload_size_mb:.2f}MB (within limits)")

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
        try:
            resp_data_model = await self._call_llm(messages, options, api_key)
        except NodeExecutionError as e:
            # Re-raise NodeExecutionError as-is (it already has good error messages)
            print(f"❌ SvensOpenRouterChat Node {self.id}: NodeExecutionError: {str(e)}")
            if hasattr(e, 'original_exc') and e.original_exc:
                print(f"   Original exception: {type(e.original_exc).__name__}: {str(e.original_exc)}")
            raise
        except Exception as e:
            # Wrap any other exceptions in NodeExecutionError with details
            error_msg = f"Failed to call OpenRouter API: {type(e).__name__}: {str(e)}"
            print(f"❌ SvensOpenRouterChat Node {self.id}: Unexpected error: {error_msg}")
            logger.error(f"SvensOpenRouterChat Node {self.id}: {error_msg}", exc_info=True)
            raise NodeExecutionError(self.id, error_msg, original_exc=e) from e

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

        # Extract thinking history from final_message if present
        thinking_history: list[dict[str, Any]] = []
        thinking = final_message.get("thinking")
        
        enable_thinking = self._parse_bool_param("enable_thinking", False)
        model_name = str(self.params.get("model") or "unknown")
        
        # Debug: Check what's actually in final_message
        if enable_thinking:
            print(f"🔍 Debug: final_message keys: {list(final_message.keys())}")
            if "thinking" in final_message:
                thinking_val = final_message.get("thinking")
                print(f"🔍 Debug: Found 'thinking' in final_message! Value type: {type(thinking_val)}, Is None: {thinking_val is None}, Is empty str: {thinking_val == ''}, Value preview: {str(thinking_val)[:200] if thinking_val else 'None/Empty'}")
                # If thinking exists but is None or empty, try to get it from raw response
                if not thinking_val or (isinstance(thinking_val, str) and not thinking_val.strip()):
                    thinking = None  # Reset to None so we check raw response
            else:
                print(f"🔍 Debug: 'thinking' NOT in final_message keys")
        
        # Check raw response first (before Pydantic validation might drop fields)
        raw_response = getattr(resp_data_model, "_raw_response", None) if resp_data_model else None
        if not thinking and raw_response and isinstance(raw_response, dict):
            try:
                # Debug: Print top-level keys in raw response
                if enable_thinking:
                    print(f"🔍 Debug: Raw response top-level keys: {list(raw_response.keys())}")
                # Check raw response structure
                if "choices" in raw_response and isinstance(raw_response["choices"], list) and len(raw_response["choices"]) > 0:
                    first_choice_raw = raw_response["choices"][0]
                    if isinstance(first_choice_raw, dict):
                        # Debug: Print choice-level keys
                        if enable_thinking:
                            print(f"🔍 Debug: Raw choice keys: {list(first_choice_raw.keys())}")
                        # Check message field in raw response
                        if "message" in first_choice_raw:
                            msg_raw = first_choice_raw["message"]
                            if isinstance(msg_raw, dict):
                                # Debug: Print what's in raw message
                                if enable_thinking:
                                    print(f"🔍 Debug: Raw message keys: {list(msg_raw.keys())}")
                                    # Check annotations field (Claude might put reasoning there)
                                    if "annotations" in msg_raw:
                                        annotations_val = msg_raw.get("annotations")
                                        print(f"🔍 Debug: Found 'annotations' field! Type: {type(annotations_val)}, Value: {str(annotations_val)[:200] if annotations_val else 'None/Empty'}")
                                        # Annotations might be a list or dict containing reasoning
                                        if isinstance(annotations_val, list) and len(annotations_val) > 0:
                                            print(f"🔍 Debug: Annotations is a list with {len(annotations_val)} items")
                                            for idx, ann in enumerate(annotations_val):
                                                if isinstance(ann, dict):
                                                    print(f"🔍 Debug: Annotation {idx} keys: {list(ann.keys())}")
                                        elif isinstance(annotations_val, dict):
                                            print(f"🔍 Debug: Annotations is a dict with keys: {list(annotations_val.keys())}")
                                    # Check each potential field
                                    for check_key in ["thinking", "reasoning", "thought", "chain_of_thought", "reasoning_content"]:
                                        if check_key in msg_raw:
                                            check_val = msg_raw.get(check_key)
                                            print(f"🔍 Debug: Found '{check_key}' in raw message! Type: {type(check_val)}, Is None: {check_val is None}, Is empty: {check_val == '' if isinstance(check_val, str) else 'N/A'}, Value preview: {str(check_val)[:200] if check_val else 'None/Empty'}")
                                
                                # Check annotations field first (Claude Sonnet 4.5 might put reasoning here)
                                if "annotations" in msg_raw:
                                    annotations_val = msg_raw.get("annotations")
                                    if annotations_val:
                                        # Try to extract reasoning from annotations
                                        if isinstance(annotations_val, list):
                                            for ann in annotations_val:
                                                if isinstance(ann, dict):
                                                    # Look for reasoning-related fields in annotation
                                                    for ann_key in ["reasoning", "thinking", "content", "text"]:
                                                        if ann_key in ann and ann[ann_key]:
                                                            thinking = ann[ann_key]
                                                            if isinstance(thinking, str) and thinking.strip():
                                                                print(f"✅ Extracted thinking from annotations[{ann_key}]")
                                                                break
                                                    if thinking:
                                                        break
                                        elif isinstance(annotations_val, dict):
                                            # Direct dict with reasoning
                                            for ann_key in ["reasoning", "thinking", "content"]:
                                                if ann_key in annotations_val and annotations_val[ann_key]:
                                                    thinking = annotations_val[ann_key]
                                                    if isinstance(thinking, str) and thinking.strip():
                                                        print(f"✅ Extracted thinking from annotations.{ann_key}")
                                                        break
                                
                                # Check all possible thinking field names
                                for key in ["thinking", "reasoning", "thought", "chain_of_thought", "reasoning_content"]:
                                    if key in msg_raw:
                                        raw_value = msg_raw.get(key)
                                        # Debug the value
                                        if enable_thinking:
                                            print(f"🔍 Debug: Checking field '{key}': type={type(raw_value)}, value={str(raw_value)[:100] if raw_value else 'None/Empty'}")
                                        # Accept any non-None value (we'll validate string content later)
                                        if raw_value is not None:
                                            thinking = raw_value
                                            print(f"✅ Extracted thinking from raw response field '{key}' (type: {type(thinking)}, length: {len(str(thinking)) if isinstance(thinking, str) else 'N/A'})")
                                            break
                                        elif enable_thinking:
                                            print(f"🔍 Debug: Field '{key}' exists but value is None")
                        # Check choice-level thinking fields
                        if not thinking:
                            for key in ["thinking", "reasoning", "thought", "chain_of_thought"]:
                                if key in first_choice_raw:
                                    thinking = first_choice_raw.get(key)
                                    if thinking:
                                        print(f"✅ Extracted thinking from raw choice field '{key}'")
                                        break
            except Exception as e:
                if enable_thinking:
                    print(f"🔍 Debug: Error checking raw response: {e}")
        
        # Check if thinking might be in the validated response choice or other fields
        if not thinking:
            if resp_data_model and resp_data_model.choices:
                first_choice = resp_data_model.choices[0]
                # Try to get raw dict from choice to see all fields
                try:
                    choice_dict = first_choice.model_dump(exclude_none=False)
                    # Check message field
                    if "message" in choice_dict:
                        msg_dict = choice_dict["message"]
                        if isinstance(msg_dict, dict):
                            if "thinking" in msg_dict:
                                thinking = msg_dict.get("thinking")
                            # Check for other possible thinking fields
                            for key in ["reasoning", "thought", "chain_of_thought"]:
                                if key in msg_dict:
                                    thinking = msg_dict.get(key)
                                    break
                    # Check choice-level thinking fields
                    for key in ["thinking", "reasoning", "thought", "chain_of_thought"]:
                        if key in choice_dict:
                            thinking = choice_dict.get(key)
                            break
                except Exception:
                    pass
        
        # Check if thinking is embedded in content (some models return it as XML tags)
        if not thinking and enable_thinking:
            content_raw = final_message.get("content", "")
            # Handle content that might be a list (some APIs return content as array)
            if isinstance(content_raw, list):
                # Join list items into a single string
                content = "\n".join(str(item) for item in content_raw if item)
                if enable_thinking:
                    print(f"🔍 Debug: Content is a list with {len(content_raw)} items, joined length: {len(content)}")
            elif isinstance(content_raw, str):
                content = content_raw
            else:
                content = str(content_raw) if content_raw else ""
            
            if content:
                import re
                # Debug: Check content length and show a sample
                if enable_thinking:
                    print(f"🔍 Debug: Checking content for embedded reasoning (content length: {len(content)})")
                    # Look for any XML-like tags that might contain reasoning
                    xml_tag_pattern = r'<(?:think|thinking|reasoning|redacted_reasoning|thought)[^>]*>(.*?)</(?:think|thinking|reasoning|redacted_reasoning|thought)>'
                    xml_matches = re.findall(xml_tag_pattern, content, re.DOTALL | re.IGNORECASE)
                    if xml_matches:
                        print(f"🔍 Debug: Found {len(xml_matches)} XML reasoning tag(s) in content")
                    else:
                        # Check if content starts with thinking-like patterns
                        thinking_starters = [r'^<think>', r'^<thinking>', r'^<reasoning>', r'^thinking:', r'^reasoning:']
                        for pattern in thinking_starters:
                            if re.search(pattern, content, re.IGNORECASE | re.MULTILINE):
                                print(f"🔍 Debug: Content appears to start with thinking pattern: {pattern}")
                                break
                
                # Check for <think>...</think> tags (common format, case-insensitive)
                think_matches = re.findall(r'<think>(.*?)</think>', content, re.DOTALL | re.IGNORECASE)
                if think_matches:
                    thinking = "\n\n".join(think_matches).strip()
                    if enable_thinking:
                        print(f"✅ Found reasoning in <think> tags (length: {len(thinking)})")
                
                # Check for <thinking>...</thinking> tags
                if not thinking:
                    think_matches = re.findall(r'<thinking>(.*?)</thinking>', content, re.DOTALL | re.IGNORECASE)
                    if think_matches:
                        thinking = "\n\n".join(think_matches).strip()
                        if enable_thinking:
                            print(f"✅ Found reasoning in <thinking> tags (length: {len(thinking)})")
                
                # Check for <think>...</think> tags
                if not thinking:
                    think_matches = re.findall(r'<think>(.*?)</think>', content, re.DOTALL | re.IGNORECASE)
                    if think_matches:
                        thinking = "\n\n".join(think_matches).strip()
                        if enable_thinking:
                            print(f"✅ Found reasoning in <think> tags (length: {len(thinking)})")
                
                # Check for ```thinking blocks
                if not thinking:
                    think_code_blocks = re.findall(r'```thinking\s*\n(.*?)```', content, re.DOTALL)
                    if think_code_blocks:
                        thinking = "\n\n".join(think_code_blocks).strip()
                        if enable_thinking:
                            print(f"✅ Found reasoning in ```thinking code blocks (length: {len(thinking)})")
                
                # Check for ```think blocks
                if not thinking:
                    think_code_blocks = re.findall(r'```think\s*\n(.*?)```', content, re.DOTALL)
                    if think_code_blocks:
                        thinking = "\n\n".join(think_code_blocks).strip()
                        if enable_thinking:
                            print(f"✅ Found reasoning in ```think code blocks (length: {len(thinking)})")
                
                # If still no thinking found, check if entire content might be thinking (for some models)
                if not thinking and enable_thinking:
                    # Some models might return thinking as the entire content if it's structured differently
                    # This is a fallback - we'll check if content looks like reasoning
                    if len(content) > 100 and any(keyword in content.lower()[:500] for keyword in ['reasoning', 'thinking', 'analyze', 'consider', 'evaluate']):
                        print(f"🔍 Debug: Content might contain reasoning but no tags found. First 500 chars: {content[:500]}")
        
        # Final check: if we found thinking/reasoning, add it to history
        if thinking:
            # Handle both string and other types
            if isinstance(thinking, str):
                thinking_str = thinking.strip()
                if thinking_str:
                    thinking_history.append({"thinking": thinking_str, "iteration": 0})
                    if enable_thinking:
                        print(f"✅ Added thinking to history (length: {len(thinking_str)})")
            else:
                # Non-string thinking (shouldn't happen, but handle it)
                thinking_str = str(thinking).strip()
                if thinking_str:
                    thinking_history.append({"thinking": thinking_str, "iteration": 0})
                    if enable_thinking:
                        print(f"✅ Added thinking to history (non-string, length: {len(thinking_str)})")
        elif enable_thinking and not thinking_history:
            # Debug output to help diagnose - print what fields we actually have
            if resp_data_model and resp_data_model.choices:
                first_choice = resp_data_model.choices[0]
                try:
                    choice_dict = first_choice.model_dump(exclude_none=False)
                    available_fields = list(choice_dict.keys())
                    print(f"🔍 Debug: Available fields in response choice: {available_fields}")
                    if "message" in choice_dict:
                        msg_dict = choice_dict["message"]
                        if isinstance(msg_dict, dict):
                            msg_fields = list(msg_dict.keys())
                            print(f"🔍 Debug: Available fields in message: {msg_fields}")
                            content_preview = str(msg_dict.get("content", ""))[:200] if "content" in msg_dict else None
                            if content_preview:
                                print(f"🔍 Debug: Content preview (first 200 chars): {content_preview}")
                except Exception as e:
                    print(f"🔍 Debug: Error inspecting response: {e}")
            
            if "qwen" in model_name.lower():
                print(f"💡 Thinking mode enabled but no thinking history found. Model: {model_name}")
                print(f"💡 Qwen models may return thinking in content as <think> tags, or may require streaming mode.")
            else:
                print(f"💡 Thinking mode enabled but no thinking history found. Model: {model_name}")

        return {
            "message": final_message,
            "metrics": metrics,
            "thinking_history": thinking_history,
        }
