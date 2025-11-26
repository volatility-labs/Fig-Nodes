import asyncio
import random
from typing import Any, Literal, TypeGuard

import aiohttp
from pydantic import BaseModel

from core.api_key_vault import APIKeyVault
from core.types_registry import ConfigDict, NodeCategory, ProgressState, get_type
from nodes.base.base_node import Base


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
    - response: Dict[str, Any] (assistant message with role, content, etc.)
    - thinking_history: List[Dict[str, Any]] (always empty list, kept for API compatibility)

    Properties:
    - model: str (model to use for the chat)
    - temperature: float (temperature for the chat)
    - max_tokens: int (maximum number of tokens to generate)
    - seed: int (seed for the chat)
    - seed_mode: str (mode for the seed)
    - use_vision: str (combo: "true" or "false" - automatically select vision-capable model if images provided)
    - inject_graph_context: str (combo: "true" or "false" - inject graph structure into first user message)
    """

    inputs = {
        "prompt": str | None,
        "system": str | dict[str, Any] | None,
        "images": ConfigDict | None,
        **{f"message_{i}": get_type("LLMChatMessage") | None for i in range(5)},
    }

    outputs = {
        "response": dict[str, Any],
        "thinking_history": get_type("LLMThinkingHistory"),
    }

    CATEGORY = NodeCategory.LLM

    # Need open router API key
    required_keys = ["OPENROUTER_API_KEY"]

    # Constants
    _DEFAULT_ASSISTANT_MESSAGE = {"role": "assistant", "content": ""}

    default_params = {
        "model": "z-ai/glm-4.6",  # Default model (text-capable; will switch if use_vision)
        "temperature": 0.2,
        "max_tokens": 20000,
        "seed": 0,
        "seed_mode": "fixed",  # fixed | random | increment
        "use_vision": "false",
        "inject_graph_context": "false",
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
        {
            "name": "inject_graph_context",
            "type": "combo",
            "default": "false",
            "options": ["true", "false"],
            "description": "Inject graph context (nodes and data flow) into the first user message",
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
        error_message = self._DEFAULT_ASSISTANT_MESSAGE.copy()
        error_message["content"] = error_msg
        return {
            "response": error_message,
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

    def _format_graph_context_for_llm(self) -> str:
        """Format graph context into a concise, LLM-friendly text representation."""
        if not self.graph_context:
            return ""

        nodes = self.graph_context.get("nodes", [])
        links = self.graph_context.get("links", [])
        current_node_id = self.graph_context.get("current_node_id")

        if not nodes:
            return ""

        lines: list[str] = []
        lines.append("=== Graph Context ===")
        lines.append(f"This node (ID: {current_node_id}) is part of a data processing pipeline.")
        lines.append("")

        # Build node lookup for easier reference
        node_lookup: dict[int, dict[str, Any]] = {
            node.get("id"): node for node in nodes if node.get("id") is not None
        }

        # Build a concise node summary with inputs/outputs
        lines.append("Workflow Nodes:")
        for node in nodes:
            node_id = node.get("id")
            node_type = node.get("type", "Unknown")
            properties = node.get("properties", {})
            inputs_raw = node.get("inputs", [])
            outputs_raw = node.get("outputs", [])
            inputs: list[Any] = inputs_raw if isinstance(inputs_raw, list) else []
            outputs: list[Any] = outputs_raw if isinstance(outputs_raw, list) else []

            # Extract key properties (filter out None values and UI-specific fields)
            key_props: dict[str, Any] = {}
            for key, value in properties.items():
                if value is not None and key not in ("pos", "size", "flags", "order", "mode"):
                    # Truncate long values
                    if isinstance(value, str) and len(value) > 80:
                        key_props[key] = value[:80] + "..."
                    else:
                        key_props[key] = value

            # Build node description
            node_desc = f"[{node_id}] {node_type}"
            if node_id == current_node_id:
                node_desc += " ⭐ (current node)"

            if key_props:
                props_str = ", ".join(f"{k}={v}" for k, v in list(key_props.items())[:5])
                if len(key_props) > 5:
                    props_str += f" ... (+{len(key_props) - 5} more)"
                node_desc += f"\n    Config: {props_str}"

            # Show simplified I/O
            input_names: list[str] = []
            for inp_raw in inputs:
                if isinstance(inp_raw, dict):
                    inp: dict[str, Any] = inp_raw
                    name = inp.get("name")
                    if isinstance(name, str):
                        input_names.append(name)

            output_names: list[str] = []
            for out_raw in outputs:
                if isinstance(out_raw, dict):
                    out: dict[str, Any] = out_raw
                    name = out.get("name")
                    if isinstance(name, str):
                        output_names.append(name)

            if input_names:
                node_desc += f"\n    Inputs: {', '.join(input_names[:3])}"
                if len(input_names) > 3:
                    node_desc += f" ... (+{len(input_names) - 3} more)"
            if output_names:
                node_desc += f"\n    Outputs: {', '.join(output_names[:3])}"
                if len(output_names) > 3:
                    node_desc += f" ... (+{len(output_names) - 3} more)"

            lines.append(f"  {node_desc}")

        lines.append("")

        # Build data flow representation with type information
        if links:
            lines.append("Data Flow (connections):")
            # Group links by origin node
            links_by_origin: dict[int, list[dict[str, Any]]] = {}
            for link in links:
                origin_id = link.get("origin_id")
                if origin_id is not None:
                    if origin_id not in links_by_origin:
                        links_by_origin[origin_id] = []
                    links_by_origin[origin_id].append(link)

            for origin_id in sorted(links_by_origin.keys()):
                origin_node = node_lookup.get(origin_id, {})
                origin_type = origin_node.get("type", "Unknown")
                origin_links = links_by_origin[origin_id]

                for link in origin_links:
                    target_id = link.get("target_id")
                    target_node = node_lookup.get(target_id, {}) if target_id is not None else {}
                    target_type = target_node.get("type", "Unknown")
                    data_type = link.get("type", "data")

                    lines.append(
                        f"  [{origin_id}] {origin_type} → [{target_id}] {target_type} ({data_type})"
                    )

        lines.append("")
        lines.append(
            "Use this context to understand the workflow structure and provide relevant responses."
        )
        lines.append("===")
        return "\n".join(lines)

    def _inject_graph_context_into_prompt(self, prompt: str | None) -> str:
        """Inject graph context into prompt if enabled."""
        inject_enabled = self._parse_bool_param("inject_graph_context", False)

        if not inject_enabled:
            return prompt or ""

        context_text = self._format_graph_context_for_llm()
        if not context_text:
            return prompt or ""

        if prompt:
            return f"{context_text}\n\n{prompt}"
        else:
            return context_text

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

        # Inject graph context into prompt if enabled
        prompt_text = self._inject_graph_context_into_prompt(prompt_text)

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

        # Log what's being sent to OpenRouter for debugging
        # Count text and images in messages
        total_text_length = 0
        image_count = 0
        for msg in messages:
            content = msg.get("content", "")
            if isinstance(content, list):
                # Multimodal content (text + images)
                for item in content:
                    if item.get("type") == "text":
                        text = item.get("text", "")
                        total_text_length += len(text)
                    elif item.get("type") == "image_url":
                        image_count += 1
            elif isinstance(content, str):
                # Text-only content
                total_text_length += len(content)
        
        # Extract text preview (first 200 chars) for confirmation
        text_preview = ""
        for msg in messages:
            content = msg.get("content", "")
            if isinstance(content, list):
                for item in content:
                    if item.get("type") == "text":
                        text_preview = item.get("text", "")[:200]
                        break
            elif isinstance(content, str):
                text_preview = content[:200]
                break
        
        print(
            f"🔵 OpenRouterChat Node {self.id}: Sending to API - "
            f"{len(messages)} message(s), {total_text_length:,} chars of text (~{total_text_length // 4:,} tokens), "
            f"{image_count} image(s), {len(filtered_messages)} message input(s)"
        )
        if text_preview:
            print(f"   📝 Text preview (first 300 chars): {text_preview[:300]}...")
            
        # Log more detail about what's being sent
        if total_text_length > 0:
            # Count lines to see if it's structured data
            text_content = ""
            for msg in messages:
                content = msg.get("content", "")
                if isinstance(content, list):
                    for item in content:
                        if isinstance(item, dict) and item.get("type") == "text":
                            text_content = str(item.get("text", ""))
                            break
                elif isinstance(content, str):
                    text_content = content
                    break
            
            if text_content:
                line_count = len(text_content.split('\n'))
                # Check if it contains actual data (numbers, indicators, symbols)
                sample = text_content[:1000] if len(text_content) > 1000 else text_content
                has_numbers = any(char.isdigit() for char in sample)
                sample_lines = text_content.split('\n')[:50]
                has_symbols = any('USD' in str(line) or '===' in str(line) for line in sample_lines)
                
                print(
                    f"   📊 Data details: {line_count:,} lines of text, "
                    f"contains {'numeric data' if has_numbers else 'text only'}, "
                    f"{'includes symbol/indicator data' if has_symbols else 'no symbol data detected'}"
                )

        # Early explicit API key check so the graph surfaces a clear failure without silent fallthrough
        api_key = self.vault.get("OPENROUTER_API_KEY")
        if not api_key:
            return self._create_error_response(
                "OpenRouter API key missing. Set OPENROUTER_API_KEY."
            )

        options = self._prepare_generation_options()

        # Emit progress update before LLM call
        self._emit_progress(ProgressState.UPDATE, 50.0, "Calling LLM...")

        # Single LLM call with web search enabled via :online suffix
        resp_data_model = await self._call_llm(messages, options, api_key)

        # Emit progress update after receiving response
        self._emit_progress(ProgressState.UPDATE, 90.0, "Received...")

        if not resp_data_model.choices:
            return self._create_error_response("No choices in response")

        final_message = self._extract_message_from_response(resp_data_model)

        # Process final message
        if not final_message:
            final_message = self._DEFAULT_ASSISTANT_MESSAGE.copy()

        self._ensure_assistant_role_inplace(final_message)

        # Check for error finish reason
        if resp_data_model and resp_data_model.choices:
            first_choice = resp_data_model.choices[0]
            if first_choice.finish_reason == "error":
                return self._create_error_response("API returned error")

        return {
            "response": final_message,
            "thinking_history": [],
        }
