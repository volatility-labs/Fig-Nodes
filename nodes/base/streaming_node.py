from typing import Dict, Any, AsyncGenerator
from abc import ABC, abstractmethod
from .base_node import Base
import logging
from core.types_registry import NodeValidationError, NodeExecutionError

logger = logging.getLogger(__name__)

class Streaming(Base, ABC):
    """
    Base class for streaming nodes that produce continuous outputs.
    
    Subclasses must implement:
    - _start_impl(self, inputs) -> AsyncGenerator[Dict[str, Any], None]  # New: Core streaming logic
    - stop(self)
    
    Error Handling Contract: Base class wraps _start_impl with validation and uniform error raising (NodeExecutionError). Subclasses should not add broad try/except in _start_impl.
    """
    is_streaming = True

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._is_force_stopped = False  # For idempotency

    async def start(self, inputs: Dict[str, Any]) -> AsyncGenerator[Dict[str, Any], None]:
        """Template method for streaming with uniform error handling."""
        if not self.validate_inputs(inputs):
            raise NodeValidationError(self.id, f"Missing or invalid inputs: {self.inputs}")
        
        try:
            async for item in self._start_impl(inputs):
                yield item
        except Exception as e:
            logger.error(f"Streaming failed in node {self.id}: {str(e)}", exc_info=True)
            raise NodeExecutionError(self.id, "Streaming failed", original_exc=e) from e

    @abstractmethod
    async def _start_impl(self, inputs: Dict[str, Any]) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Core streaming logic - implement in subclasses. Do not add try/except here; let base handle errors.
        """
        pass

    def stop(self):
        print(f"StreamingNode: Stopping node {self.id}")
        """
        Stop the streaming operation cleanly.
        """

    def interrupt(self):
        """Forcefully interrupt any blocking operations. Default no-op."""
        pass

    def force_stop(self):
        """Immediately terminate streaming execution without awaiting."""
        if getattr(self, "_is_stopped", False):
            return
        # Mark stopped in base first to guard against re-entrancy
        super().force_stop()
        # Forceful immediate stop: first interrupt blocking ops, then perform cleanup
        try:
            self.interrupt()
        except Exception as e:
            logger.warning(f"Error during interrupt in node {self.id}: {str(e)}")
        try:
            self.stop()
        except Exception as e:
            logger.warning(f"Error during stop in node {self.id}: {str(e)}")
        print(f"StreamingNode: Force stopped node {self.id}")

    async def execute(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        # For compatibility, but streaming nodes use start/stop instead
        raise NotImplementedError("Use start() for streaming nodes")
