from typing import Dict, Any, Type, Union, get_origin, get_args, List, cast, Optional
from collections.abc import Hashable
from core.types_registry import DefaultParams, NodeCategory, NodeInputs, NodeOutputs, NodeValidationError, NodeExecutionError, ParamMeta, ProgressCallback, ProgressEvent, ProgressState
import logging
from abc import abstractmethod
from pydantic import BaseModel, ValidationError, create_model
from abc import ABC

logger = logging.getLogger(__name__)

class Base(ABC):
    inputs: NodeInputs = {}
    outputs: NodeOutputs = {}
    params_meta: List[ParamMeta] = []
    default_params: DefaultParams = {}
    CATEGORY: NodeCategory = NodeCategory.BASE

    def __init__(self, id: int, params: Dict[str, Any]):
        self.id = id
        self.params = {**self.default_params, **(params or {})}
        self.inputs = dict(getattr(self, "inputs", {}))
        self.outputs = dict(getattr(self, "outputs", {}))
        self._progress_callback: Optional[ProgressCallback] = None
        self._is_stopped = False  
        
    @staticmethod
    def _normalize_to_list(value: Any) -> List[Any]:
        if value is None:
            return []
        if isinstance(value, list):
            return cast(List[Any], value)
        return [value]

    @staticmethod
    def _dedupe_preserve_order(items: List[Any]) -> List[Any]:
        if not items:
            return []
        result: List[Any] = []
        seen_hashables: set[Hashable] = set()
        for item in items:
            if isinstance(item, Hashable):
                if item in seen_hashables:
                    continue
                seen_hashables.add(item)
            result.append(item)
        return result

    @staticmethod
    def _is_declared_list(expected_type: Union[Type[Any], None]) -> bool:
        if expected_type is None:
            return False
        return get_origin(expected_type) in (list, List)

    def collect_multi_input(self, key: str, inputs: Dict[str, Any]) -> List[Any]:
        expected_type = self.inputs.get(key)

        # If not declared as List[...], just normalize the primary value to a list
        if not self._is_declared_list(expected_type):
            return self._normalize_to_list(inputs.get(key))

        # Declared as List[...] – collect primary and suffixed values into a single list
        collected: List[Any] = []
        collected.extend(self._normalize_to_list(inputs.get(key)))

        i = 0
        while True:
            multi_key = f"{key}_{i}"
            if multi_key not in inputs:
                break
            collected.extend(self._normalize_to_list(inputs.get(multi_key)))
            i += 1

        return self._dedupe_preserve_order(collected)
    
    def _type_allows_none(self, tp: Type[Any]) -> bool:
        # Works for Union[T, None] and T | None
        return type(None) in get_args(tp)

    def _get_or_build_model(self, fields: Dict[str, Type[Any]]) -> Type[BaseModel]:
        # All fields are required at the model level; None acceptance comes from the type
        field_defs: Dict[str, Any] = {name: (tp, ...) for name, tp in fields.items()}
        return create_model(
            f"Node{type(self).__name__}Model",
            __base__=BaseModel,
            **field_defs,
    )

    def validate_inputs(self, inputs: Dict[str, Any]) -> None:  
        """Validate inputs using Pydantic with support for multi-inputs and explicit None via type unions.

        Raises NodeValidationError on missing required inputs or type mismatches.
        """

        normalized: Dict[str, Any] = dict(inputs)
        for key, expected_type in self.inputs.items():
            if key in normalized:
                continue
            origin = get_origin(expected_type)
            if origin in (list, List):
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

    def _validate_outputs(self, outputs: Dict[str, Any]) -> None:
        """Best-effort output validation using Pydantic. Only validates declared outputs.

        Intentionally lenient: fields are optional and only validated if present.
        """
        if not self.outputs:
            return
        try:
            if outputs:
                present_fields: Dict[str, Type[Any]] = {k: self.outputs[k] for k in self.outputs.keys() if k in outputs}
                if present_fields:
                    output_model = self._get_or_build_model(present_fields)
                    output_model.model_validate({k: outputs[k] for k in present_fields.keys()}, strict=False)
        except ValidationError as ve:
            raise TypeError(f"Output validation failed for node {self.id}: {ve}") from ve

    def set_progress_callback(self, callback: ProgressCallback) -> None:
        """Set a callback function to report progress during execution."""
        self._progress_callback = callback

    def _clamp_progress(self, value: float) -> float:
        if value < 0.0:
            return 0.0
        if value > 1.0:
            return 1.0
        return value

    def _emit_progress(self, state: ProgressState, progress: Optional[float] = None, text: str = "", meta: Optional[Dict[str, Any]] = None) -> None:
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
        logger.debug(f"BaseNode: force_stop called for node {self.id}, already stopped: {self._is_stopped}")
        if self._is_stopped:
            return  # Idempotent
        self._is_stopped = True
        # Base implementation: no-op, subclasses can override for specific kill logic
        logger.debug(f"BaseNode: Force stopping node {self.id} (no-op in base class)")
        self._emit_progress(ProgressState.STOPPED, 1.0, "stopped")

    async def execute(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """Template method for execution with uniform error handling and progress lifecycle."""
        self.validate_inputs(inputs)  # Raises NodeValidationError if invalid (missing or type issues)
        self._emit_progress(ProgressState.START, 0.0, "start")
        try:
            result = await self._execute_impl(inputs)
            self._validate_outputs(result)
            self._emit_progress(ProgressState.DONE, 1.0, "done")
            return result
        except Exception as e:
            self._emit_progress(ProgressState.ERROR, 1.0, f"error: {type(e).__name__}: {str(e)}")
            raise NodeExecutionError(self.id, "Execution failed", original_exc=e) from e

    @abstractmethod
    async def _execute_impl(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """Core execution logic - implement in subclasses. Do not add try/except here; let base handle errors."""
        raise NotImplementedError("Subclasses must implement _execute_impl()") 