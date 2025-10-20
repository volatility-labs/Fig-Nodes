import typing
from typing import Dict, Any, Type, get_origin, get_args, List, cast, Callable
from collections.abc import Hashable
from core.types_registry import NodeValidationError, NodeExecutionError
import logging
from abc import abstractmethod
from pydantic import BaseModel, ValidationError, create_model

logger = logging.getLogger(__name__)

class Base:
    inputs = {}
    outputs = {}
    params_meta = []
    default_params: Dict[str, Any] = {}

    def __init__(self, id: int, params: Dict[str, Any]):
        self.id = id
        self.params = {**self.default_params, **(params or {})}
        self.inputs = dict(getattr(self, "inputs", {}))
        self.outputs = dict(getattr(self, "outputs", {}))
        self._progress_callback: typing.Union[Callable[[int, float, str], None], None] = None
        self._is_stopped = False  
        # Execution state flags
        
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
    def _is_declared_list(expected_type: typing.Union[Type[Any], None]) -> bool:
        if expected_type is None:
            return False
        return get_origin(expected_type) in (list, typing.List)

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

        # 1) Normalize inputs to fold multi-inputs (key_0, key_1, ...) into the main key when expected is a List[...] 
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

        # 2) Normalize missing nullable to explicit None (preserves intent without special skip logic)
        for key, tp in self.inputs.items():
            if key not in normalized and self._type_allows_none(tp):
                normalized[key] = None

        # 3) Build and apply a dynamic Pydantic model for type validation (missing required will raise here)
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
            # Validate only provided outputs (lenient presence), but enforce declared types on those present
            if outputs:
                present_fields: Dict[str, Type[Any]] = {k: self.outputs[k] for k in self.outputs.keys() if k in outputs}
                if present_fields:
                    output_model = self._get_or_build_model(present_fields)
                    output_model.model_validate({k: outputs[k] for k in present_fields.keys()}, strict=False)
        except ValidationError as ve:
            raise TypeError(f"Output validation failed for node {self.id}: {ve}") from ve

    def set_progress_callback(self, callback: Callable[[int, float, str], None]) -> None:
        """Set a callback function to report progress during execution."""
        self._progress_callback = callback

    def report_progress(self, progress: float, text: str = ""):
        """Report progress to the execution system."""
        if self._progress_callback:
            self._progress_callback(self.id, progress, text)

    def force_stop(self):
        """Immediately terminate node execution and clean up resources. Idempotent."""
        logger.debug(f"BaseNode: force_stop called for node {self.id}, already stopped: {self._is_stopped}")
        if self._is_stopped:
            return  # Idempotent
        self._is_stopped = True
        # Base implementation: no-op, subclasses can override for specific kill logic
        logger.debug(f"BaseNode: Force stopping node {self.id} (no-op in base class)")

    async def execute(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """Template method for execution with uniform error handling."""
        self.validate_inputs(inputs)  # Raises NodeValidationError if invalid (missing or type issues)
        
        try:
            result = await self._execute_impl(inputs)
            # Validate outputs (lenient)
            self._validate_outputs(result)
            return result
        except Exception as e:
            logger.error(f"Execution failed in node {self.id}: {str(e)}", exc_info=True)
            raise NodeExecutionError(self.id, "Execution failed", original_exc=e) from e

    @abstractmethod
    async def _execute_impl(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """Core execution logic - implement in subclasses. Do not add try/except here; let base handle errors."""
        raise NotImplementedError("Subclasses must implement _execute_impl()") 