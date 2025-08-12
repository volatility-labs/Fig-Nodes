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

    @abstractmethod
    async def start(self, inputs: Dict[str, Any]) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Start the streaming operation and yield outputs continuously.
        """
        pass

    @abstractmethod
    def stop(self):
        """
        Stop the streaming operation cleanly.
        """
        pass

    async def execute(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        # For compatibility, but streaming nodes use start/stop instead
        raise NotImplementedError("Use start() for streaming nodes")
