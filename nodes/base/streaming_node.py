from typing import Dict, Any, AsyncGenerator
from abc import ABC, abstractmethod
from .base_node import BaseNode

class StreamingNode(BaseNode, ABC):
    """
    Base class for streaming nodes that produce continuous outputs.
    
    Subclasses must implement:
    - start(self, inputs) -> AsyncGenerator[Dict[str, Any], None]
    - stop(self)
    """
    is_streaming = True

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._is_force_stopped = False  # For idempotency

    @abstractmethod
    async def start(self, inputs: Dict[str, Any]) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Start the streaming operation and yield outputs continuously.
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
        self.interrupt()
        self.stop()
        print(f"StreamingNode: Force stopped node {self.id}")

    async def execute(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        # For compatibility, but streaming nodes use start/stop instead
        raise NotImplementedError("Use start() for streaming nodes")
