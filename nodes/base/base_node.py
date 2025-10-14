import typing
from typing import Dict, Any, Type, Optional, get_origin, get_args, List
from core.types_registry import get_type, AssetSymbol, AssetClass, NodeValidationError, NodeExecutionError
from typing import Any as TypingAny
import logging
from abc import abstractmethod
from pydantic import BaseModel, ValidationError, create_model

logger = logging.getLogger(__name__)

class BaseNode:
    """
    Abstract base class for all graph nodes.
    
    Subclasses must define:
    - inputs: Dict[str, Type] - Expected input types
    - outputs: Dict[str, Type] - Produced output types
    - default_params: Dict[str, Any] - Default parameter values
    - Optional: params_meta - List of dicts for UI parameter config
    - _execute_impl(self, inputs: Dict[str, Any]) -> Dict[str, Any]  # New: Core logic only; base handles errors
    
    Optional:
    - required_asset_class: AssetClass - For asset-specific nodes
    - validate_inputs(self, inputs) - Custom validation
    
    For specialized hierarchies (e.g., filter nodes), extend this class with abstract methods for shared behavior, then create concrete subclasses. Example: BaseFilterNode extends BaseNode with filtering logic, and BaseIndicatorFilterNode extends BaseFilterNode for indicator-specific filters.
    
    Error Handling Contract: Base class wraps _execute_impl with validation and uniform error raising (NodeExecutionError). Subclasses should not add broad try/except in _execute_impl; raise specific errors for domain logic.
    """
    inputs: Dict[str, Type] = {}
    outputs: Dict[str, Type] = {"output": Any}
    default_params: Dict[str, Any] = {}
    required_asset_class: Optional[AssetClass] = None
    # New: unified optional input support at the base level
    optional_inputs: List[str] = []

    def __init__(self, id: int, params: Dict[str, Any] = None):
        self.id = id
        self.params = {**self.default_params, **(params or {})}
        # Ensure per-instance mutable copies to avoid cross-test/class mutation
        self.inputs = dict(getattr(self, "inputs", {}))
        self.outputs = dict(getattr(self, "outputs", {}))
        self._progress_callback = None
        self._is_stopped = False  # For idempotency in force_stop
        # Lazy caches for dynamic pydantic models
        self._input_model_cls: Optional[Type[BaseModel]] = None
        self._output_model_cls: Optional[Type[BaseModel]] = None

    def collect_multi_input(self, key: str, inputs: Dict[str, Any]) -> List[Any]:
        expected_type = self.inputs.get(key)
        if expected_type is None:
            val = inputs.get(key)
            return [val] if val is not None else []
        origin = get_origin(expected_type)
        if origin not in (list, typing.List):
            val = inputs.get(key)
            return [val] if val is not None else []

        collected = []
        if key in inputs:
            val = inputs[key]
            if val is not None:
                if isinstance(val, list):
                    collected.extend(val)
                else:
                    collected.append(val)

        i = 0
        while True:
            multi_key = f"{key}_{i}"
            if multi_key not in inputs:
                break
            val = inputs[multi_key]
            if val is None:
                i += 1
                continue
            if isinstance(val, list):
                collected.extend(val)
            else:
                collected.append(val)
            i += 1

        # Deduplicate
        seen = set()
        unique = []
        for item in collected:
            item_str = str(item)
            if item_str not in seen:
                seen.add(item_str)
                unique.append(item)

        return unique

    def validate_inputs(self, inputs: Dict[str, Any]) -> bool:
        """Validate inputs against declared types using Pydantic with support for optional and multi-inputs.

        Returns True when inputs are valid or sufficient according to optional_inputs.
        Returns False when required inputs are missing (to allow executor to skip node).
        Raises TypeError/ValueError for type or asset-class mismatches.
        """

        # 1) Normalize inputs to fold multi-inputs (key_0, key_1, ...) into the main key when expected is a List[...] 
        normalized: Dict[str, Any] = dict(inputs)
        for key, expected_type in self.inputs.items():
            if key in normalized:
                continue
            origin = get_origin(expected_type)
            if origin in (list, typing.List):
                # Collect any suffixed items and fold into a single list
                collected = self.collect_multi_input(key, inputs)
                if collected:
                    normalized[key] = collected

        # 2) Check required presence honoring optional_inputs
        missing_required = [k for k in self.inputs.keys() if k not in normalized and k not in (self.optional_inputs or [])]
        if missing_required:
            return False

        # 3) Build and apply a dynamic Pydantic model for type validation
        try:
            input_model = self._get_or_build_model(self.inputs, optional_fields=(self.optional_inputs or []))
            # Only validate declared fields; ignore extra keys
            # Pydantic v2: use model_validate with from attributes
            input_model.model_validate(normalized, strict=False)
        except ValidationError as ve:
            # Provide concise message for developer ergonomics
            raise TypeError(f"Input validation failed for node {self.id}: {ve}") from ve

        # 4) Additional domain-specific checks: required_asset_class
        for key, expected_type in self.inputs.items():
            if key not in normalized:
                continue
            value = normalized[key]
            origin = get_origin(expected_type)
            if origin in (list, typing.List):
                elem_t = get_args(expected_type)[0] if get_args(expected_type) else Any
                if elem_t == AssetSymbol and isinstance(value, list) and self.required_asset_class:
                    for item in value:
                        if isinstance(item, AssetSymbol) and item.asset_class != self.required_asset_class:
                            raise ValueError(
                                f"Invalid asset class for item in '{key}' in node {self.id}: expected {self.required_asset_class}, got {item.asset_class}"
                            )
            else:
                if expected_type == AssetSymbol and isinstance(value, AssetSymbol) and self.required_asset_class:
                    if value.asset_class != self.required_asset_class:
                        raise ValueError(
                            f"Invalid asset class for '{key}' in node {self.id}: expected {self.required_asset_class}, got {value.asset_class}"
                        )
        return True

    def _get_or_build_model(self, fields: Dict[str, Type], optional_fields: List[str]) -> Type[BaseModel]:
        """Create a Pydantic model class for the provided field mapping. Caches per instance.

        We generate models with all declared fields; optional fields accept None by default.
        """
        # Simple cache keyed by id of dict to avoid re-creating per call
        cache_attr = '_input_model_cls' if fields is self.inputs else '_output_model_cls'
        cached = getattr(self, cache_attr, None)
        if cached is not None:
            return cached
        model_fields: Dict[str, tuple] = {}
        for name, tp in fields.items():
            if name in (optional_fields or []):
                model_fields[name] = (Optional[tp], None)
            else:
                model_fields[name] = (tp, ...)
        model_cls = create_model(
            f"Node{type(self).__name__}{cache_attr.title()}",
            **model_fields,
        )
        setattr(self, cache_attr, model_cls)
        return model_cls

    def _validate_outputs(self, outputs: Dict[str, Any]) -> None:
        """Best-effort output validation using Pydantic. Only validates declared outputs.

        Intentionally lenient: fields are optional and only validated if present.
        """
        if not isinstance(self.outputs, dict) or not self.outputs:
            return
        try:
            # Make all outputs optional for validation to avoid over-constraining nodes
            output_model = self._get_or_build_model(self.outputs, optional_fields=list(self.outputs.keys()))
            output_model.model_validate(outputs or {}, strict=False)
        except ValidationError as ve:
            raise TypeError(f"Output validation failed for node {self.id}: {ve}") from ve

    def set_progress_callback(self, callback):
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
        if not self.validate_inputs(inputs):
            raise NodeValidationError(self.id, f"Missing or invalid inputs: {self.inputs}")
        
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