import asyncio
import base64
import json
import random
from datetime import datetime
from typing import Any, Literal, NotRequired, TypedDict, TypeGuard

import aiohttp
from pydantic import BaseModel, ValidationError

from core.api_key_vault import APIKeyVault
from core.types_registry import ConfigDict, NodeCategory, NodeExecutionError, OHLCVBundle, get_type
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
        max_payload_size: int = 2_000_000,  # 2MB default limit
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
                    print(f"📊 OpenRouterChat: {image_count} images, avg size: {avg_image_size/1024:.1f}KB, total: {total_image_size/1024/1024:.2f}MB")
            
            result.append({"role": "user", "content": user_content})
        
        # Estimate total payload size
        payload_size = OpenRouterChat._estimate_payload_size(result)
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
            if final_payload_mb > 2.0:
                print(f"⚠️ Final request payload: {final_payload_mb:.2f}MB (may exceed API limits)")
        except Exception:
            pass  # Don't fail if we can't estimate

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
                
                # Check for error in response (some APIs return 200 OK with error payload)
                if isinstance(resp_data_raw, dict) and "error" in resp_data_raw:
                    error_info = resp_data_raw.get("error", {})
                    error_message = error_info.get("message", "Unknown error") if isinstance(error_info, dict) else str(error_info)
                    raise NodeExecutionError(
                        self.id,
                        f"OpenRouter API returned error: {error_message}",
                        original_exc=ValueError(f"API error response: {resp_data_raw}"),
                    )
                
                try:
                    return OpenRouterChatResponseModel.model_validate(resp_data_raw)
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
                "No valid messages, prompt, or system provided to OpenRouterChatNode"
            )
        
        # Check payload size and warn if too large
        payload_size_mb = payload_size / 1024 / 1024
        max_payload_mb = 2.0  # OpenRouter typically allows up to 2MB, but can vary
        
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
