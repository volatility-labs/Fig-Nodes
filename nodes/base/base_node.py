import logging
from abc import ABC, abstractmethod
from collections.abc import Hashable
from typing import Any, cast, get_args, get_origin

from pydantic import BaseModel, ValidationError, create_model

from core.types_registry import (
    DefaultParams,
    NodeCategory,
    NodeExecutionError,
    NodeInputs,
    NodeOutputs,
    NodeValidationError,
    ParamMeta,
    ProgressCallback,
    ProgressEvent,
    ProgressState,
)

logger = logging.getLogger(__name__)


class Base(ABC):
    # Default values for inputs, outputs, params_meta, default_params, and CATEGORY
    inputs: NodeInputs = {}
    outputs: NodeOutputs = {}
    params_meta: list[ParamMeta] = []
    default_params: DefaultParams = {}
    required_keys: list[str] = []
    CATEGORY: NodeCategory = NodeCategory.BASE

    def __init__(self, id: int, params: dict[str, Any], graph_context: dict[str, Any] | None = None):
        self.id = id
        self.params = {**self.default_params, **(params or {})}
        self.inputs = dict(getattr(self, "inputs", {}))
        self.outputs = dict(getattr(self, "outputs", {}))
        self._progress_callback: ProgressCallback | None = None
        self._is_stopped = False
        self.graph_context = graph_context or {}

    @staticmethod
    def _normalize_to_list(value: Any) -> list[Any]:
        if value is None:
            return []
        if isinstance(value, list):
            return cast(list[Any], value)
        return [value]

    @staticmethod
    def _dedupe_preserve_order(items: list[Any]) -> list[Any]:
        if not items:
            return []
        result: list[Any] = []
        seen_hashables: set[Hashable] = set()
        for item in items:
            if isinstance(item, Hashable):
                if item in seen_hashables:
                    continue
                seen_hashables.add(item)
            result.append(item)
        return result

    @staticmethod
    def _is_declared_list(expected_type: type[Any] | None) -> bool:
        if expected_type is None:
            return False
        return get_origin(expected_type) in (list, list)

    def collect_multi_input(self, key: str, inputs: dict[str, Any]) -> list[Any]:
        expected_type = self.inputs.get(key)

        # If not declared as List[...], just normalize the primary value to a list
        if not self._is_declared_list(expected_type):
            return self._normalize_to_list(inputs.get(key))

        # Declared as List[...] – collect primary and suffixed values into a single list
        collected: list[Any] = []
        collected.extend(self._normalize_to_list(inputs.get(key)))

        i = 0
        while True:
            multi_key = f"{key}_{i}"
            if multi_key not in inputs:
                break
            collected.extend(self._normalize_to_list(inputs.get(multi_key)))
            i += 1

        return self._dedupe_preserve_order(collected)

    def _type_allows_none(self, tp: type[Any]) -> bool:
        # Works for Union[T, None] and T | None
        return type(None) in get_args(tp)

    def _get_or_build_model(self, fields: dict[str, type[Any]]) -> type[BaseModel]:
        # All fields are required at the model level; None acceptance comes from the type
        field_defs: dict[str, Any] = {name: (tp, ...) for name, tp in fields.items()}
        return create_model(
            f"Node{type(self).__name__}Model",
            __base__=BaseModel,
            **field_defs,
        )

    def validate_inputs(self, inputs: dict[str, Any]) -> None:
        """Validate inputs using Pydantic with support for multi-inputs and explicit None via type unions.

        Raises NodeValidationError on missing required inputs or type mismatches.
        """

        normalized: dict[str, Any] = dict(inputs)
        for key, expected_type in self.inputs.items():
            if key in normalized:
                continue
            origin = get_origin(expected_type)
            if origin in (list, list):
                # Collect any suffixed items and fold into a single list
                collected = self.collect_multi_input(key, inputs)
                if collected:
                    normalized[key] = collected

        for key, tp in self.inputs.items():
            if key not in normalized and self._type_allows_none(tp):
                normalized[key] = None

        try:
            input_model = self._get_or_build_model(self.inputs)
            input_model.model_validate(normalized, strict=False)
        except ValidationError as ve:
            raise NodeValidationError(self.id, f"Input validation failed: {ve}") from ve

    def _validate_outputs(self, outputs: dict[str, Any]) -> None:
        """Best-effort output validation using Pydantic. Only validates declared outputs.

        Intentionally lenient: fields are optional and only validated if present.
        """
        if not self.outputs:
            return
        try:
            if outputs:
                present_fields: dict[str, type[Any]] = {
                    k: self.outputs[k] for k in self.outputs.keys() if k in outputs
                }
                if present_fields:
                    output_model = self._get_or_build_model(present_fields)
                    output_model.model_validate(
                        {k: outputs[k] for k in present_fields.keys()}, strict=False
                    )
        except ValidationError as ve:
            raise TypeError(f"Output validation failed for node {self.id}: {ve}") from ve

    def set_progress_callback(self, callback: ProgressCallback) -> None:
        """Set a callback function to report progress during execution."""
        self._progress_callback = callback

    def _clamp_progress(self, value: float) -> float:
        if value < 0.0:
            return 0.0
        if value > 100.0:
            return 100.0
        return value

    def _emit_progress(
        self,
        state: ProgressState,
        progress: float | None = None,
        text: str = "",
        meta: dict[str, Any] | None = None,
    ) -> None:
        if not self._progress_callback:
            return
        event: ProgressEvent = {
            "node_id": self.id,
            "state": state,
        }
        if progress is not None:
            event["progress"] = self._clamp_progress(progress)
        if text:
            event["text"] = text
        if meta:
            event["meta"] = meta
        self._progress_callback(event)

    def report_progress(self, progress: float, text: str = ""):
        """Convenience helper for subclasses to report an UPDATE event."""
        self._emit_progress(ProgressState.UPDATE, progress, text)

    def force_stop(self):
        """Immediately terminate node execution and clean up resources. Idempotent."""
        logger.debug(
            f"BaseNode: force_stop called for node {self.id}, already stopped: {self._is_stopped}"
        )
        if self._is_stopped:
            return  # Idempotent
        self._is_stopped = True
        self._emit_progress(ProgressState.STOPPED, 100.0, "stopped")

    async def execute(self, inputs: dict[str, Any]) -> dict[str, Any]:
        """Template method for execution with uniform error handling and progress lifecycle."""
        self.validate_inputs(
            inputs
        )  # Raises NodeValidationError if invalid (missing or type issues)
        self._emit_progress(ProgressState.START, 0.0, "start")
        try:
            result = await self._execute_impl(inputs)
            self._validate_outputs(result)
            self._emit_progress(ProgressState.DONE, 100.0, "")
            return result
        except NodeExecutionError:
            # Re-raise NodeExecutionError as-is to preserve detailed error messages
            raise
        except Exception as e:
            self._emit_progress(ProgressState.ERROR, 100.0, f"error: {type(e).__name__}: {str(e)}")
            raise NodeExecutionError(self.id, "Execution failed", original_exc=e) from e

    @abstractmethod
    async def _execute_impl(self, inputs: dict[str, Any]) -> dict[str, Any]:
        """Core execution logic - implement in subclasses. Do not add try/except here; let base handle errors."""
        raise NotImplementedError("Subclasses must implement _execute_impl()")
