from typing import Dict, Any, List, Optional
import os
import json
import asyncio
import random
import httpx
import sys
import re
from nodes.base.base_node import Base
import subprocess as sp

from core.types_registry import LLMToolSpec, LLMToolSpecList, NodeCategory, ConfigDict, get_type
from services.tools.registry import get_tool_handler, get_all_credential_providers
import logging

logger = logging.getLogger(__name__)

class OllamaChat(Base):
    """
    Non-streaming chat node backed by a local Ollama server.

    Note: Streaming mode is not implemented for this node. Use execute() for synchronous calls.

    Constraints:
    - Does not pull/download models. Users manage models with the Ollama CLI.

    Inputs:
    - host: str
    - model: str (e.g., "llama3.2:latest")
    - messages: List[Dict[str, Any]] (chat history with role, content, etc.)
    - prompt: str
    - system: str
    - images: ConfigDict (optional dict of label to base64 data URL for images to attach to the user prompt)
    - tools: Dict[str, Any] (optional tool schema, supports multi-input and list inputs)

    Outputs:
    - message: Dict[str, Any] (assistant message with role, content, thinking, tool_calls, etc.)
    - metrics: Dict[str, Any] (generation stats like durations and token counts)

    """

    inputs = {
        "messages": get_type("LLMChatMessageList") | None,
        "prompt": str | None,
        "system": Any | None,
        "images": ConfigDict | None,
        "tools": get_type("LLMToolSpecList") | None,  
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

    CATEGORY = NodeCategory.LLM

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
        # Trading analysis ranking
        "ranking_mode": "bullish",  # bullish | bearish
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
        {"name": "ranking_mode", "type": "combo", "default": "bullish", "options": ["bullish", "bearish"], "label": "Ranking Mode", "description": "For trading analysis: rank by bullish (most bullish first) or bearish (most bearish first)"},
 
    ]


    def __init__(self, id: int, params: Dict[str, Any] | None = None, graph_context: dict[str, Any] | None = None):
        super().__init__(id, params or {}, graph_context)
        self._cancel_event = asyncio.Event()
        # Mark optional inputs at runtime for validation layer
        self.optional_inputs = ["tools", "tool", "messages", "prompt", "system", "images"]
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
    def _build_messages(existing_messages: Optional[List[Dict[str, Any]]], prompt: Optional[str], system_input: Optional[Any], images: Optional[ConfigDict] = None) -> List[Dict[str, Any]]:
        """
        Construct a messages array compliant with Ollama chat API from either:
        - existing structured messages
        - a plain-text prompt (as a user role message)
        - both (prompt appended to existing)
        - images (as base64 data URLs) attached to the user message
        
        Ollama expects images as a list of base64 strings (without the data:image/... prefix).
        """
        result = list(existing_messages or [])
        if system_input and not any(m.get("role") == "system" for m in result):
            if isinstance(system_input, str):
                result.insert(0, {"role": "system", "content": system_input})
            elif isinstance(system_input, dict):
                result.insert(0, system_input)
        
        # Build user message with prompt and/or images
        if prompt or images:
            # Ensure at least a default prompt when images are present but no usable prompt provided
            # Trim the prompt so strings with only whitespace also trigger the default.
            content_text = (prompt or "")
            if isinstance(content_text, str):
                content_text = content_text.strip()

            # Normalize images input: accept dict (preferred) or list/tuple of base64/data URLs
            normalized_images: Dict[str, Any] = {}
            if isinstance(images, dict):
                normalized_images = images
            elif isinstance(images, (list, tuple)):
                normalized_images = {f"img_{i}": v for i, v in enumerate(images)}

            # Count valid images
            image_count = len(normalized_images) if normalized_images else 0

            if normalized_images and not content_text:
                # Provide a default prompt for vision models when none is given
                content_text = "What do you see in these images? Please describe them in detail."
                print(f"OllamaChatNode: No prompt provided with images, using default prompt", file=sys.stderr)
            
            # If multiple images are present, always prepend a note about the number of images
            # to ensure all are processed and returned as an array
            print(f"OllamaChatNode: Checking multi-image condition - image_count={image_count}, content_text_length={len(content_text) if content_text else 0}, content_text_bool={bool(content_text)}", file=sys.stderr)
            if image_count > 1 and content_text:
                # Check if prompt already mentions the count explicitly
                already_mentions_count = str(image_count) in content_text
                print(f"OllamaChatNode: Condition met! already_mentions_count={already_mentions_count}", file=sys.stderr)
                
                # Always prepend the note when multiple images are present
                # Make it more explicit and forceful to ensure all images are processed
                if not already_mentions_count:
                    image_numbers = ", ".join([f"Image {i+1}" for i in range(image_count)])
                    object_placeholders = ", ".join([f"object{i+1}" for i in range(image_count)])
                    json_example = ", ".join([f'{{"symbol": "...", ...}}' for _ in range(image_count)])
                    
                    image_note = f"""⚠️ CRITICAL INSTRUCTION: You are receiving {image_count} images total ({image_numbers}).

YOU MUST:
1. Process ALL {image_count} images in order ({image_numbers}) - do not skip any
2. Analyze EACH image separately and create one JSON object per image
3. Return a JSON array with EXACTLY {image_count} objects: [{object_placeholders}]
4. Format: [{json_example}]
5. The array MUST start with [ and end with ]
6. Do NOT return a single object - you MUST return an array with {image_count} objects

CRITICAL: If you return only one object instead of an array with {image_count} objects, your response is INCORRECT.

"""
                    print(f"OllamaChatNode: Detected {image_count} images - prepended CRITICAL instruction to process all images and return JSON array", file=sys.stderr)
                else:
                    # Even if count is mentioned, add a reminder to ensure array format
                    image_note = f"""⚠️ REMINDER: You are receiving {image_count} images. 

Return a JSON array with EXACTLY {image_count} objects (one per image).
Format: [{{...}}, {{...}}, ...] with {image_count} objects total.

"""
                    print(f"OllamaChatNode: Detected {image_count} images (count already mentioned) - prepended REMINDER to return JSON array", file=sys.stderr)
                
                # Also modify the example in the prompt if it contains an array example
                # Replace "[{...}, ...]" patterns with explicit count
                # Look for array examples like "[{...}, ...]" (handles multi-line)
                array_pattern = r'\[\s*\{[^}]*\}[,\s]*\.\.\.\s*\]'
                if re.search(array_pattern, content_text, re.MULTILINE | re.DOTALL):
                    # Replace the example to show exact count
                    example_replacement = f"[{{...}}, {{...}}" + (", ..." if image_count > 2 else "") + f"]  # MUST contain exactly {image_count} objects"
                    content_text = re.sub(array_pattern, example_replacement, content_text, count=1, flags=re.MULTILINE | re.DOTALL)
                    print(f"OllamaChatNode: Modified array example in prompt to show {image_count} objects", file=sys.stderr)
                
                # Also look for multi-line array examples with newlines
                multiline_array_pattern = r'\[\s*\n\s*\{[^}]*\}[,\s]*\n\s*\.\.\.\s*\n\s*\]'
                if re.search(multiline_array_pattern, content_text, re.MULTILINE | re.DOTALL):
                    # Create a multi-line example showing the exact count
                    example_objects = ",\n  ".join(["{...}"] * min(image_count, 3))
                    if image_count > 3:
                        example_objects += f",\n  ...  # ({image_count} objects total)"
                    example_replacement = f"[\n  {example_objects}\n]  # MUST contain exactly {image_count} objects"
                    content_text = re.sub(multiline_array_pattern, example_replacement, content_text, count=1, flags=re.MULTILINE | re.DOTALL)
                    print(f"OllamaChatNode: Modified multi-line array example in prompt to show {image_count} objects", file=sys.stderr)
                
                content_text = image_note + content_text
                
                # Also append a reminder at the end to reinforce the instruction
                reminder_note = f"\n\n⚠️ FINAL REMINDER: You received {image_count} images ({', '.join([f'Image {i+1}' for i in range(image_count)])}). You MUST return a JSON array with EXACTLY {image_count} objects, one per image. The array must start with [ and end with ]. Do NOT return a single object - return [{', '.join([f'object{i+1}' for i in range(image_count)])}]."
                content_text = content_text + reminder_note
                
                # Detect trading/momentum analysis prompts and add ranking/formatting instructions
                is_trading_analysis = (
                    "momentum trader" in content_text.lower() or
                    "rainbow" in content_text.lower() or
                    "rainbow_bias" in content_text.lower() or
                    "bullish" in content_text.lower() or
                    "bearish" in content_text.lower()
                )
                
                if is_trading_analysis and image_count > 1:
                    # Get ranking mode from params
                    try:
                        ranking_mode = str(self.params.get("ranking_mode", "bullish")).lower()
                        print(f"OllamaChatNode: Retrieved ranking_mode from params: {ranking_mode}", file=sys.stderr)
                    except Exception as e:
                        print(f"OllamaChatNode: Error accessing ranking_mode from params: {e}, using default 'bullish'", file=sys.stderr)
                        ranking_mode = "bullish"
                    is_bullish_mode = ranking_mode == "bullish"
                    rank_direction = "bullish" if is_bullish_mode else "bearish"
                    rank_field = "bullish_rank" if is_bullish_mode else "bearish_rank"
                    top_3_field = "top_3_bullish" if is_bullish_mode else "top_3_bearish"
                    rank_description = "most bullish first, most bearish last" if is_bullish_mode else "most bearish first, most bullish last"
                    
                    ranking_instructions = f"""

📊 OUTPUT FORMATTING REQUIREMENTS:

After analyzing all {image_count} images, you MUST:

1. RANK all symbols by {rank_direction}ness ({rank_description})
2. Add a "{rank_field}" field to each object (1 = most {rank_direction}, {image_count} = least {rank_direction})
3. Add a summary section at the END of your response with the top 3 most {rank_direction} symbols

OUTPUT FORMAT:
{{
  "results": [
    {{"symbol": "...", "rainbow_bias": "...", "{rank_field}": 1, ...}},
    {{"symbol": "...", "rainbow_bias": "...", "{rank_field}": 2, ...}},
    ...
  ],
  "{top_3_field}": [
    {{"symbol": "...", "rainbow_bias": "...", "confidence": ..., "visual_thesis": "..."}},
    {{"symbol": "...", "rainbow_bias": "...", "confidence": ..., "visual_thesis": "..."}},
    {{"symbol": "...", "rainbow_bias": "...", "confidence": ..., "visual_thesis": "..."}}
  ]
}}

RANKING LOGIC ({rank_direction.upper()} MODE):
- {"Strongest bullish first" if is_bullish_mode else "Strongest bearish first"}
- "strong bullish" > "mild bullish" > "neutral" > "mild bearish" > "strong bearish"
- Within same bias level, rank by confidence ({"higher = more bullish" if is_bullish_mode else "higher = more bearish"})
- Green colors (lime green, dark green, teal) = bullish
- Red/brown colors (hot pink, deep red, brown) = bearish
- White stripes reduce bullishness (caution signal)

CRITICAL: Sort the results array by {rank_field} (1 to {image_count}) and include the {top_3_field} summary.
"""
                    content_text = content_text + ranking_instructions
                    print(f"OllamaChatNode: Detected trading analysis prompt - added ranking and formatting instructions (mode: {rank_direction})", file=sys.stderr)
                
                print(f"OllamaChatNode: Final content length after prepending and appending: {len(content_text)} chars", file=sys.stderr)
                print(f"OllamaChatNode: Content preview (first 500 chars): {content_text[:500]}", file=sys.stderr)
            
            user_message: Dict[str, Any] = {
                "role": "user",
                "content": content_text
            }
            print(f"OllamaChatNode: Built user message - content_length={len(content_text)}, content_preview='{content_text[:100]}...', has_images={bool(images)}", file=sys.stderr)
            
            # Extract base64 data from data URLs for Ollama
            if normalized_images:
                image_list: List[str] = []
                for data_url in normalized_images.values():
                    if isinstance(data_url, str):
                        if data_url.startswith("data:image/"):
                            # Extract base64 part (everything after the comma)
                            if "," in data_url:
                                _, base64_part = data_url.split(",", 1)
                                image_list.append(base64_part)
                            else:
                                # If no comma, assume it's already base64
                                image_list.append(data_url)
                        else:
                            # Already a raw base64 string
                            image_list.append(data_url)
                
                if image_list:
                    user_message["images"] = image_list
                    print(f"OllamaChatNode: Added {len(image_list)} images to user message, final content_length={len(user_message.get('content', ''))}", file=sys.stderr)
            
            result.append(user_message)
        elif prompt:
            # Fallback: if only prompt without images
            result.append({"role": "user", "content": prompt})
        
        return result

    def _collect_tools(self, inputs: Dict[str, Any]) -> List[LLMToolSpec]:
        """
        Collect and combine tools from both 'tools' (list) and 'tool' (single/multi) inputs.
        """
        result: List[LLMToolSpec] = []

        # Add tools from the 'tools' input (list)
        tools_list: LLMToolSpecList = inputs.get("tools")
        if tools_list:
            for tool in tools_list:
                if isinstance(tool, dict) and tool.get("type") == "function":
                    result.append(tool)

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

    def _is_vision_capable_model(self, model: str) -> bool:
        """Check if a model name suggests it supports vision capabilities."""
        if not model:
            return False
        model_lower = model.lower()
        vision_indicators = [
            "vl", "vision", "multimodal", "qwen3-vl", "qwen2.5vl", 
            "llava", "bakllava", "moondream", "minicpm-v"
        ]
        return any(indicator in model_lower for indicator in vision_indicators)

    async def _get_model(self, host: str, model_from_input: Optional[str], has_images: bool = False) -> str:
        if model_from_input:
            selected = model_from_input
        else:
            selected = self.params.get("selected_model") or ""

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
            raise ValueError(f"Ollama model query failed: {e}") from e

        # Update params_meta options dynamically for UI consumption via /nodes metadata
        for p in self.params_meta:
            if p["name"] == "selected_model":
                p["options"] = models_list
                break

        # Auto-select vision model if images are provided and current model doesn't support vision
        if has_images and selected:
            if not self._is_vision_capable_model(selected):
                # Try to find a vision-capable model in the available models
                vision_models = [m for m in models_list if self._is_vision_capable_model(m)]
                if vision_models:
                    # Prefer qwen3-vl models, then others
                    qwen3vl = [m for m in vision_models if "qwen3-vl" in m.lower() or "qwen3vl" in m.lower()]
                    if qwen3vl:
                        selected = qwen3vl[0]
                    else:
                        selected = vision_models[0]
                    print(f"OllamaChatNode: Auto-selected vision-capable model '{selected}' (images detected)")
                else:
                    print(f"OllamaChatNode: WARNING - Images provided but no vision-capable models found. Using '{selected}' (may fail)")

        if (not selected or selected not in models_list) and models_list:
            # If no selection and images provided, prefer vision models
            if has_images:
                vision_models = [m for m in models_list if self._is_vision_capable_model(m)]
                if vision_models:
                    qwen3vl = [m for m in vision_models if "qwen3-vl" in m.lower() or "qwen3vl" in m.lower()]
                    selected = qwen3vl[0] if qwen3vl else vision_models[0]
                    print(f"OllamaChatNode: Auto-selected vision-capable model '{selected}' (images detected, no model selected)")
                else:
                    selected = models_list[0]
                    print(f"OllamaChatNode: Auto-selected first model '{selected}' (no vision models available)")
            else:
                selected = models_list[0]
                print(f"OllamaChatNode: Auto-selected first model: {selected}")

        if not selected and not models_list:
            error_msg = "No local Ollama models found. Pull one via 'ollama pull <model>'"
            print(f"OllamaChatNode: ERROR - {error_msg}")
            raise ValueError(error_msg)
        elif selected and selected not in models_list:
            logger.warning(f"OllamaChatNode: WARNING - Selected model '{selected}' not in available models {models_list}")

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
            if hasattr(message, 'role'):  # It's a Message object
                message = self._message_to_dict(message)
            tool_calls = message.get("tool_calls") if isinstance(message, dict) else None

            # Collect thinking if present
            thinking = message.get("thinking")
            if thinking and isinstance(thinking, str):
                thinking_history.append({"thinking": thinking, "iteration": _round})

            messages.append(message)

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

    async def _execute_impl(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        # Prefer host/model from inputs when provided
        host = self._get_effective_host(inputs)
        input_model = (inputs.get("model") if isinstance(inputs, dict) else None)
        images: Optional[ConfigDict] = inputs.get("images")
        has_images = bool(images and isinstance(images, dict) and any(
            isinstance(v, str) and v.startswith("data:image/") for v in images.values()
        ))
        model: str = await self._get_model(host, input_model, has_images=has_images)
        self._last_host = host
        self._last_model = model
        raw_messages: Optional[List[Dict[str, Any]]] = inputs.get("messages")
        prompt_text: Optional[str] = inputs.get("prompt")
        system_input: Optional[Any] = inputs.get("system")
        images: Optional[ConfigDict] = inputs.get("images")
        
        # Debug: Check what we received
        print(f"OllamaChatNode: Input keys received: {list(inputs.keys())}", file=sys.stderr)
        print(f"OllamaChatNode: images input type: {type(images)}, value: {images}", file=sys.stderr)
        if images:
            print(f"OllamaChatNode: images dict keys: {list(images.keys())[:5] if isinstance(images, dict) else 'not a dict'}", file=sys.stderr)
            if isinstance(images, dict) and images:
                sample_key = list(images.keys())[0]
                sample_value = images[sample_key]
                print(f"OllamaChatNode: Sample image value type: {type(sample_value)}, starts with data:image/: {str(sample_value)[:11] if isinstance(sample_value, str) else 'N/A'}", file=sys.stderr)
        
        print(f"OllamaChatNode: Building messages - prompt_length={len(prompt_text) if prompt_text else 0}, has_images={bool(images)}, images_count={len(images) if images else 0}", file=sys.stderr)
        messages: List[Dict[str, Any]] = self._build_messages(raw_messages, prompt_text, system_input, images)
        tools: List[Dict[str, Any]] = self._collect_tools(inputs)

        print(f"OllamaChatNode: Execute - model='{model}', host='{host}', prompt='{prompt_text}', messages_count={len(raw_messages) if raw_messages else 0}")
        # Re-affirm host using same precedence (inputs -> params -> env)
        host: str = self._get_effective_host(inputs)
        # Track last used model/host for stop/unload
        self._last_model = model
        self._last_host = host
        # Force non-streaming for execute()
        fmt: Optional[str] = self._get_format_value()
        # Note: JSON format is now allowed even with images (user-controlled via json_mode toggle)
        # Some vision models may not support JSON format, but we let the user decide
        if fmt == "json" and images:
            print(f"OllamaChatNode: JSON format enabled with images (format={fmt}). Some vision models may not support JSON format.", file=sys.stderr)
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

        try:
            # Auto-detect and apply model context window (clamp num_ctx) for execute()
            # Only perform network lookup when 'messages' are provided; skip for prompt-only inputs
            try:
                if isinstance(inputs, dict) and inputs.get("messages"):
                    options = await self._apply_context_window(host, model, options)
            except Exception as ctx_err:
                logger.warning(f"OllamaChatNode: Warning - context window detection failed: {ctx_err}")

            # Debug: Log message structure before sending
            print(f"OllamaChatNode: Sending {len(messages)} message(s) to Ollama", file=sys.stderr)
            logger.debug(f"OllamaChatNode: Sending {len(messages)} message(s) to Ollama")
            for i, msg in enumerate(messages):
                msg_type = type(msg.get("content", "")).__name__
                has_images = "images" in msg and msg["images"]
                img_count = len(msg.get("images", [])) if has_images else 0
                content_preview = str(msg.get("content", ""))[:100] if msg.get("content") else ""
                print(f"  Message {i}: role={msg.get('role')}, content_type={msg_type}, content_length={len(str(msg.get('content', '')))}, content_preview='{content_preview}...', has_images={has_images}, image_count={img_count}", file=sys.stderr)
                if has_images:
                    total_img_size = 0
                    for j, img_data in enumerate(msg.get("images", [])):
                        img_size = len(img_data) if isinstance(img_data, str) else 0
                        total_img_size += img_size
                        print(f"    Image {j}: base64_length={img_size}, preview={img_data[:50] if isinstance(img_data, str) else 'N/A'}...", file=sys.stderr)
                    print(f"  Total image data size: {total_img_size/1024:.1f}KB ({total_img_size/1024/1024:.2f}MB)", file=sys.stderr)
                logger.debug(f"  Message {i}: role={msg.get('role')}, content_type={msg_type}, has_images={has_images}, image_count={img_count}")

            # Tool orchestration if needed
            tool_rounds_info = {"messages": messages, "last_response": None, "metrics": {}, "tool_history": [], "thinking_history": []}
            if tools:
                tool_rounds_info = await self._maybe_execute_tools_and_augment_messages(
                    host, model, messages, tools, fmt, options, keep_alive, think
                )
            else:
                client = AsyncClient(host=host)
                self._client = client

                # Sequential processing for multiple images with JSON mode
                # Some vision models struggle with processing multiple images at once
                image_count = len(images) if images and isinstance(images, dict) else 0
                if image_count > 1 and fmt == "json" and images:
                    print(f"OllamaChatNode: Detected {image_count} images with JSON mode - using sequential processing for reliability", file=sys.stderr)
                    results = []
                    for i, (img_key, img_data) in enumerate(images.items()):
                        print(f"OllamaChatNode: Processing image {i+1}/{image_count} ({img_key})", file=sys.stderr)
                        single_image = {img_key: img_data}
                        single_image_messages = self._build_messages(raw_messages, prompt_text, system_input, single_image)
                        try:
                            single_resp = await client.chat(
                                model=model,
                                messages=single_image_messages,
                                tools=None,
                                stream=False,
                                format=fmt,
                                options=options,
                                keep_alive=keep_alive,
                                think=think,
                            )
                            if hasattr(single_resp, 'message'):
                                single_message = single_resp.message
                                single_content = getattr(single_message, 'content', '') if hasattr(single_message, 'content') else str(single_message)
                            elif isinstance(single_resp, dict):
                                single_message = single_resp.get('message', {})
                                single_content = single_message.get('content', '') if isinstance(single_message, dict) else str(single_message)
                            else:
                                single_content = str(single_resp)
                            
                            # Parse JSON from single response
                            try:
                                import json
                                parsed = json.loads(single_content) if isinstance(single_content, str) else single_content
                                if isinstance(parsed, dict):
                                    # Add symbol tracking: ensure image_key is set to the actual symbol from the image key
                                    parsed["image_key"] = img_key
                                    # If model didn't detect a symbol or detected a different one, add both
                                    detected_symbol = parsed.get("symbol", "unknown")
                                    if "symbol" not in parsed or detected_symbol != img_key:
                                        parsed["detected_symbol"] = detected_symbol
                                        parsed["symbol"] = img_key  # Use the actual symbol from image key
                                        print(f"OllamaChatNode: Symbol correction - image_key={img_key}, detected_symbol={detected_symbol}, using image_key as symbol", file=sys.stderr)
                                    results.append(parsed)
                                elif isinstance(parsed, list) and parsed:
                                    # If it's a list, add image_key to each item
                                    for item in parsed:
                                        if isinstance(item, dict):
                                            item["image_key"] = img_key
                                            detected_symbol = item.get("symbol", "unknown")
                                            if "symbol" not in item or detected_symbol != img_key:
                                                item["detected_symbol"] = detected_symbol
                                                item["symbol"] = img_key
                                                print(f"OllamaChatNode: Symbol correction in list - image_key={img_key}, detected_symbol={detected_symbol}, using image_key as symbol", file=sys.stderr)
                                    results.extend(parsed)
                                else:
                                    # Wrap non-dict results with symbol tracking
                                    results.append({"content": parsed, "image_key": img_key, "symbol": img_key})
                            except json.JSONDecodeError:
                                # If not JSON, wrap in dict with symbol tracking
                                results.append({"content": single_content, "image_index": i, "image_key": img_key, "symbol": img_key})
                        except Exception as img_err:
                            print(f"OllamaChatNode: Error processing image {i+1} ({img_key}): {img_err}", file=sys.stderr)
                            results.append({"error": f"Failed to process image {i+1}: {str(img_err)}", "image_index": i, "image_key": img_key, "symbol": img_key})
                    
                    # Create combined response
                    combined_content = json.dumps(results) if results else "[]"
                    resp = type('Response', (), {
                        'message': type('Message', (), {
                            'role': 'assistant',
                            'content': combined_content,
                            'thinking': None
                        })(),
                        'done': True,
                        'done_reason': 'stop'
                    })()
                    print(f"OllamaChatNode: Sequential processing complete - combined {len(results)} results into array", file=sys.stderr)
                else:
                    # Original single API call for non-multi-image cases
                    # Cooperative cancellation for non-streaming execute()
                    try:
                        print(f"OllamaChatNode: Calling Ollama API with model={model}, messages_count={len(messages)}, format={fmt}, think={think}", file=sys.stderr)
                        logger.debug(f"OllamaChatNode: Calling Ollama API with model={model}, messages_count={len(messages)}, format={fmt}, think={think}")
                        chat_task = asyncio.create_task(client.chat(
                            model=model,
                            messages=messages,
                            tools=None,
                            stream=False,
                            format=fmt,
                            options=options,
                            keep_alive=keep_alive,
                            think=think,
                        ))
                        print(f"OllamaChatNode: API call task created, waiting for response...", file=sys.stderr)
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
                            self._client = None
                            raise asyncio.CancelledError()
                        resp = await chat_task
                        print(f"OllamaChatNode: Received response from Ollama, resp type: {type(resp)}, keys: {list(resp.keys()) if isinstance(resp, dict) else 'not a dict'}", file=sys.stderr)
                        if hasattr(resp, '__dict__'):
                            print(f"OllamaChatNode: Response attributes: {list(resp.__dict__.keys())}", file=sys.stderr)
                            # Check done status and done_reason
                            if hasattr(resp, 'done'):
                                print(f"OllamaChatNode: Response done status: {resp.done}", file=sys.stderr)
                            if hasattr(resp, 'done_reason'):
                                print(f"OllamaChatNode: Response done_reason: {resp.done_reason}", file=sys.stderr)
                        if hasattr(resp, 'message'):
                            msg_obj = resp.message
                            if hasattr(msg_obj, '__dict__'):
                                print(f"OllamaChatNode: Message object attributes: {list(msg_obj.__dict__.keys())}", file=sys.stderr)
                                if hasattr(msg_obj, 'content'):
                                    content_val = getattr(msg_obj, 'content', None)
                                    print(f"OllamaChatNode: Message content type: {type(content_val)}, length: {len(str(content_val)) if content_val else 0}, preview: {str(content_val)[:200] if content_val else 'None'}...", file=sys.stderr)
                                if hasattr(msg_obj, 'thinking'):
                                    thinking_val = getattr(msg_obj, 'thinking', None)
                                    print(f"OllamaChatNode: Message thinking type: {type(thinking_val)}, length: {len(str(thinking_val)) if thinking_val else 0}, preview: {str(thinking_val)[:200] if thinking_val else 'None'}...", file=sys.stderr)
                        logger.debug(f"OllamaChatNode: Received response from Ollama, resp keys: {list(resp.keys()) if isinstance(resp, dict) else 'not a dict'}")
                    except Exception as chat_err:
                        import traceback
                        print(f"OllamaChatNode: Chat API call failed: {type(chat_err).__name__}: {chat_err}", file=sys.stderr)
                        print(f"OllamaChatNode: Traceback:\n{traceback.format_exc()}", file=sys.stderr)
                        logger.error(f"OllamaChatNode: Chat API call failed: {type(chat_err).__name__}: {chat_err}")
                        logger.error(f"OllamaChatNode: Traceback:\n{traceback.format_exc()}")
                        raise

            if tools:
                resp = tool_rounds_info.get("last_response") or {}
                metrics = tool_rounds_info.get("metrics") or {}
                tool_history = tool_rounds_info.get("tool_history") or []
                thinking_history = tool_rounds_info.get("thinking_history") or []
            else:
                metrics = {}
                tool_history = []
                thinking_history = []

            # Handle response - Ollama returns a ChatResponse object with a .message attribute
            # The ChatResponse object has attributes: message, done, model, created_at, etc.
            if resp is None:
                logger.warning("OllamaChatNode: Warning - No response received, using empty message")
                final_message = {"role": "assistant", "content": ""}
            elif hasattr(resp, 'message'):
                # It's a ChatResponse object from Ollama client
                resp_message = resp.message
                if resp_message is None:
                    logger.warning("OllamaChatNode: Warning - No message in ChatResponse, using empty message")
                    final_message = {"role": "assistant", "content": ""}
                elif hasattr(resp_message, 'role'):
                    # It's a Message object, convert to dict
                    final_message = self._message_to_dict(resp_message)
                    # Handle thinking field: append to content instead of replacing it
                    # This allows debugging while preserving both fields
                    thinking_val = final_message.get('thinking')
                    thinking_len = len(str(thinking_val)) if thinking_val else 0
                    content_val = final_message.get('content', '')
                    content_len = len(str(content_val)) if content_val else 0
                    
                    if thinking_val:
                        print(f"OllamaChatNode: Thinking field has content (length={thinking_len}), preview: {str(thinking_val)[:200]}...", file=sys.stderr)
                    
                    # Append thinking to content for better visibility and debugging
                    if thinking_val:
                        thinking_str = str(thinking_val)
                        if not content_val:
                            # If content is empty, use thinking as content
                            print(f"OllamaChatNode: Content is empty, using thinking field as content", file=sys.stderr)
                            final_message['content'] = thinking_str
                        else:
                            # If both exist, append thinking to content with a separator
                            print(f"OllamaChatNode: Both content and thinking present, appending thinking to content for visibility", file=sys.stderr)
                            final_message['content'] = f"{content_val}\n\n--- Thinking ---\n{thinking_str}"
                    
                    print(f"OllamaChatNode: Extracted message from ChatResponse: role={final_message.get('role')}, content_length={len(str(final_message.get('content', '')))}, thinking_length={thinking_len}", file=sys.stderr)
                    logger.debug(f"OllamaChatNode: Converted Message object to dict: role={final_message.get('role')}, content_length={len(str(final_message.get('content', '')))}, thinking_length={thinking_len}")
                    # Warn if content is still empty after extraction
                    if not final_message.get('content') and not thinking_val:
                        error_msg = "Both content and thinking are empty! The model returned an empty response."
                        if fmt == "json" and images:
                            error_msg += " This may indicate that qwen3-vl:8b does not support JSON format with vision inputs. Try disabling JSON mode."
                        print(f"OllamaChatNode: WARNING - {error_msg}", file=sys.stderr)
                        logger.warning(f"OllamaChatNode: WARNING - {error_msg}")
                        # Check if we can get more info from the response
                        if hasattr(resp, 'done_reason'):
                            print(f"OllamaChatNode: Response done_reason: {resp.done_reason}", file=sys.stderr)
                        if hasattr(resp, 'done'):
                            print(f"OllamaChatNode: Response done: {resp.done}", file=sys.stderr)
                        # Add error to metrics for visibility
                        if not isinstance(metrics, dict):
                            metrics = {}
                        metrics["error"] = error_msg
                        # Set a helpful error message in content
                        final_message['content'] = f"ERROR: {error_msg}"
                elif isinstance(resp_message, dict):
                    final_message = resp_message
                    print(f"OllamaChatNode: Extracted dict message from ChatResponse: role={final_message.get('role')}, content_length={len(str(final_message.get('content', '')))}", file=sys.stderr)
                    logger.debug(f"OllamaChatNode: Using dict response: role={final_message.get('role')}, content_length={len(str(final_message.get('content', '')))}")
                else:
                    logger.warning(f"OllamaChatNode: Warning - Unexpected message type in ChatResponse: {type(resp_message)}, using empty message")
                    final_message = {"role": "assistant", "content": ""}
            elif isinstance(resp, dict):
                # Fallback: treat as dict (shouldn't happen with Ollama client, but handle it)
                resp_message = resp.get("message")
                if resp_message is None:
                    logger.warning("OllamaChatNode: Warning - No message in dict response, using empty message")
                    final_message = {"role": "assistant", "content": ""}
                elif isinstance(resp_message, dict):
                    final_message = resp_message
                    print(f"OllamaChatNode: Using dict response: role={final_message.get('role')}, content_length={len(str(final_message.get('content', '')))}", file=sys.stderr)
                else:
                    final_message = {"role": "assistant", "content": ""}
            else:
                logger.warning(f"OllamaChatNode: Warning - Unexpected response type: {type(resp)}, using empty message")
                final_message = {"role": "assistant", "content": ""}
            
            self._ensure_assistant_role_inplace(final_message)
            self._parse_content_if_json_mode(final_message, metrics)
            
            # Post-process trading analysis results: rank by bullishness and add summary
            print(f"OllamaChatNode: About to call _post_process_trading_analysis - prompt_text={bool(prompt_text)}, images={bool(images)}", file=sys.stderr)
            try:
                self._post_process_trading_analysis(final_message, images, prompt_text)
                print(f"OllamaChatNode: _post_process_trading_analysis completed successfully", file=sys.stderr)
                
                # If JSON mode is enabled and content is a dict, serialize it back to JSON string for consistency
                if bool(self.params.get("json_mode", False)) and isinstance(final_message.get("content"), dict):
                    try:
                        final_message["content"] = json.dumps(final_message["content"], indent=2)
                        print(f"OllamaChatNode: Serialized post-processed content to JSON string for JSON mode", file=sys.stderr)
                    except Exception as json_err:
                        print(f"OllamaChatNode: Warning - Failed to serialize content to JSON: {json_err}", file=sys.stderr)
            except Exception as e:
                import traceback
                print(f"OllamaChatNode: Error in _post_process_trading_analysis: {type(e).__name__}: {str(e)}", file=sys.stderr)
                print(f"OllamaChatNode: Traceback:\n{traceback.format_exc()}", file=sys.stderr)
                # Don't fail the whole execution if post-processing fails
                pass
            
            # Check if multiple images were sent but only a single object was returned
            # Note: This check happens after post-processing, so content might be formatted as {"results": [...], "top_3_bullish": [...]}
            if images and isinstance(images, dict):
                image_count = len(images)
                if image_count > 1:
                    content = final_message.get("content")
                    
                    # Skip check if content is post-processed format (has "results" key) - post-processing already handled validation
                    if isinstance(content, dict) and "results" in content:
                        # Post-processed format - already validated by post-processing, skip this check
                        pass
                    elif isinstance(content, dict) and not isinstance(content, list):
                        # Single object returned when array expected (not post-processed format)
                        warning_msg = f"WARNING: {image_count} images were sent, but the model returned a single JSON object instead of an array with {image_count} objects. The model may not have processed all images."
                        print(f"OllamaChatNode: {warning_msg}", file=sys.stderr)
                        logger.warning(f"OllamaChatNode: {warning_msg}")
                        metrics["array_warning"] = warning_msg
                        # Wrap the single object in an array for consistency
                        final_message["content"] = [content]
                        print(f"OllamaChatNode: Wrapped single object in array for consistency", file=sys.stderr)
                    elif isinstance(content, list):
                        if len(content) != image_count:
                            warning_msg = f"WARNING: {image_count} images were sent, but the model returned an array with {len(content)} objects instead of {image_count}."
                            print(f"OllamaChatNode: {warning_msg}", file=sys.stderr)
                            logger.warning(f"OllamaChatNode: {warning_msg}")
                            metrics["array_warning"] = warning_msg
            
            self._parse_tool_calls_from_message(final_message)

            self._update_metrics_from_source(metrics, resp)
            metrics["seed"] = int(effective_seed) if effective_seed is not None else None
            if "temperature" in options:
                metrics["temperature"] = options["temperature"]
            t_metrics = tool_rounds_info.get("metrics") or {}
            if isinstance(t_metrics, dict):
                metrics.update(t_metrics)
            if not tools:
                thinking = final_message.get("thinking")
                if thinking and isinstance(thinking, str):
                    thinking_history.append({"thinking": thinking, "iteration": 0})
            
            content_preview = str(final_message.get("content", ""))[:200] if final_message.get("content") else ""
            print(f"OllamaChatNode: Successfully received response from Ollama. Content length: {len(str(final_message.get('content', '')))}, preview: {content_preview}...", file=sys.stderr)
            logger.info(f"OllamaChatNode: Successfully received response from Ollama. Content preview: {content_preview}...")
            
            return {
                "message": final_message,
                "metrics": metrics,
                "tool_history": tool_history,
                "thinking_history": thinking_history
            }
        except Exception as e:
            import traceback
            error_msg = f"{type(e).__name__}: {str(e)}"
            print(f"OllamaChatNode: Execution failed - {error_msg}", file=sys.stderr)
            print(f"OllamaChatNode: Full traceback:\n{traceback.format_exc()}", file=sys.stderr)
            logger.error(f"OllamaChatNode: Execution failed - {error_msg}")
            logger.error(f"OllamaChatNode: Full traceback:\n{traceback.format_exc()}")
            error_message = {"role": "assistant", "content": ""}
            return {"message": error_message, "metrics": {"error": error_msg}, "tool_history": [], "thinking_history": []}

    def _post_process_trading_analysis(self, message: Dict[str, Any], images: Optional[ConfigDict], prompt_text: Optional[str]) -> None:
        """Post-process trading analysis results: rank by bullishness or bearishness and add summary."""
        print(f"OllamaChatNode: _post_process_trading_analysis called - prompt_text={bool(prompt_text)}, images={bool(images)}", file=sys.stderr)
        # Check if this is a trading analysis prompt
        is_trading_analysis = (
            prompt_text and (
                "momentum trader" in prompt_text.lower() or
                "rainbow_bias" in prompt_text.lower() or
                "bullish" in prompt_text.lower()
            )
        )
        
        print(f"OllamaChatNode: is_trading_analysis={is_trading_analysis}", file=sys.stderr)
        if not is_trading_analysis:
            print(f"OllamaChatNode: Not a trading analysis prompt, skipping post-processing", file=sys.stderr)
            return
        
        # Get ranking mode from params
        ranking_mode = str(self.params.get("ranking_mode", "bullish")).lower()
        is_bullish_mode = ranking_mode == "bullish"
        rank_direction = "bullish" if is_bullish_mode else "bearish"
        rank_field = "bullish_rank" if is_bullish_mode else "bearish_rank"
        top_3_field = "top_3_bullish" if is_bullish_mode else "top_3_bearish"
        
        content = message.get("content")
        
        # Try to parse if it's a string
        if isinstance(content, str):
            try:
                content = json.loads(content)
            except (json.JSONDecodeError, ValueError):
                return
        
        if not isinstance(content, (list, dict)):
            return
        
        # Extract results array
        results = []
        if isinstance(content, dict):
            # Check if it already has a results field
            if "results" in content:
                results = content["results"]
            elif top_3_field in content or "top_3_bullish" in content or "top_3_bearish" in content:
                # Already formatted, skip
                return
            else:
                # Assume the dict itself is a single result, or try to extract array
                results = [content] if isinstance(content, dict) and "symbol" in content else []
        elif isinstance(content, list):
            results = content
        
        if not results or not isinstance(results, list):
            return
        
        # Check if results have trading analysis fields
        if not any(isinstance(r, dict) and "rainbow_bias" in r for r in results):
            return
        
        print(f"OllamaChatNode: Post-processing {len(results)} trading analysis results - ranking by {rank_direction}ness", file=sys.stderr)
        
        # Define bias scoring (same for both modes, we'll invert for bearish)
        bias_scores = {
            "strong bullish": 5,
            "mild bullish": 4,
            "neutral": 3,
            "mild bearish": 2,
            "strong bearish": 1
        }
        
        # Score and rank each result
        scored_results = []
        for i, result in enumerate(results):
            if not isinstance(result, dict):
                continue
            
            bias = str(result.get("rainbow_bias", "neutral")).lower()
            confidence = result.get("confidence", 50)
            white_stripe = result.get("white_stripe_warning", False)
            
            # Calculate base score
            base_score = bias_scores.get(bias, 3)
            # Adjust by confidence (higher confidence = higher score)
            confidence_adjustment = (confidence - 50) / 100.0
            # White stripes reduce bullishness (or increase bearishness)
            stripe_penalty = -0.5 if white_stripe else 0
            
            score = base_score + confidence_adjustment + stripe_penalty
            
            # For bearish mode, invert the score (we want most bearish first)
            if not is_bullish_mode:
                score = 6 - score  # Invert: 5 becomes 1, 1 becomes 5
            
            scored_results.append({
                "result": result,
                "score": score,
                "index": i
            })
        
        # Sort by score (highest first for bullish, highest first for bearish after inversion)
        scored_results.sort(key=lambda x: x["score"], reverse=True)
        
        # Add rank field to each result
        for rank, scored in enumerate(scored_results, start=1):
            scored["result"][rank_field] = rank
        
        # Extract top 3
        top_3 = []
        for scored in scored_results[:3]:
            result = scored["result"]
            top_3.append({
                "symbol": result.get("symbol", "unknown"),
                "rainbow_bias": result.get("rainbow_bias", "neutral"),
                "confidence": result.get("confidence", 50),
                "visual_thesis": result.get("visual_thesis", ""),
                rank_field: result.get(rank_field, 999)
            })
        
        # Reconstruct results array in ranked order
        ranked_results = [scored["result"] for scored in scored_results]
        
        # Format output with summary
        formatted_output = {
            "results": ranked_results,
            top_3_field: top_3,
            "total_analyzed": len(ranked_results)
        }
        
        message["content"] = formatted_output
        
        # Log top 3 summary prominently
        top_3_summary = "\n".join([
            f"  {i+1}. {r.get('symbol')} - {r.get('rainbow_bias')} (confidence: {r.get('confidence')}%)"
            for i, r in enumerate(top_3)
        ])
        print(f"OllamaChatNode: Post-processing complete - ranked {len(ranked_results)} results by {rank_direction}ness", file=sys.stderr)
        print(f"OllamaChatNode: TOP 3 {rank_direction.upper()} SUMMARY:\n{top_3_summary}", file=sys.stderr)
        print(f"OllamaChatNode: Full output structure: {{'results': [...], '{top_3_field}': [...], 'total_analyzed': {len(ranked_results)}}}", file=sys.stderr)

    def _parse_content_if_json_mode(self, message: Dict[str, Any], metrics: Dict[str, Any]) -> None:
        if bool(self.params.get("json_mode", False)):
            content_str = message.get("content", "")
            if isinstance(content_str, str):
                try:
                    parsed = json.loads(content_str)
                    message["content"] = parsed
                except json.JSONDecodeError as e:
                    metrics["parse_error"] = str(e)

    def _parse_tool_calls_from_message(self, message: Dict[str, Any]) -> None:
        """Normalize tool_calls in-place to a dict-based schema.

        Converts any client-specific ToolCall objects or malformed entries into
        {"function": {"name": str, "arguments": Dict[str, Any]}} items so that
        downstream consumers and tests can rely on a consistent structure.
        """
        try:
            if not isinstance(message, dict):
                return
            tool_calls = message.get("tool_calls")
            if not tool_calls or not isinstance(tool_calls, list):
                return
            normalized: List[Dict[str, Any]] = []
            for call in tool_calls:
                # If already a dict with proper structure, coerce arguments to dict
                if isinstance(call, dict):
                    func = call.get("function")
                    if isinstance(func, dict):
                        name = func.get("name") if isinstance(func.get("name"), str) else ""
                        args = func.get("arguments")
                        # If args is a JSON string, try to parse; otherwise ensure dict
                        if isinstance(args, str):
                            try:
                                parsed_args = json.loads(args)
                                args = parsed_args if isinstance(parsed_args, dict) else {}
                            except Exception:
                                args = {}
                        elif not isinstance(args, dict):
                            args = {}
                        normalized.append({"function": {"name": name, "arguments": args}})
                    else:
                        # Attempt to convert object-like entries
                        normalized.append(self._tool_call_to_dict(call))
                else:
                    # Object from client SDK; convert via helper
                    normalized.append(self._tool_call_to_dict(call))
            message["tool_calls"] = normalized
        except Exception:
            # Be resilient; never raise from parser
            pass

    def force_stop(self):
        was_stopped = self._is_stopped
        super().force_stop()
        if not was_stopped:
            self.stop()

    # _make_full_message no longer used for final outputs; kept for potential future use
    # def _make_full_message(self, base: Dict[str, Any]) -> Dict[str, Any]:
    #     return base
