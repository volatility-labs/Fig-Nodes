"""Pydantic schemas for WebSocket message validation."""

from pydantic import BaseModel, Field
from typing import Literal, Dict, Any, List, Optional
from core.types_registry import SerialisableGraph


# ============================================================================
# CLIENT → SERVER MESSAGES
# ============================================================================

class ClientToServerGraphMessage(BaseModel):
    """Message to start graph execution."""
    type: Literal["graph"] = "graph"
    graph_data: SerialisableGraph = Field(..., description="Graph data to execute")


class ClientToServerStopMessage(BaseModel):
    """Message to stop current execution."""
    type: Literal["stop"] = "stop"


# Union type for client messages
ClientToServerMessage = ClientToServerGraphMessage | ClientToServerStopMessage


# ============================================================================
# SERVER → CLIENT MESSAGES
# ============================================================================

class ServerToClientStatusMessage(BaseModel):
    """Status update message."""
    type: Literal["status"] = "status"
    message: str = Field(..., description="Status message")


class ServerToClientErrorMessage(BaseModel):
    """Error message."""
    type: Literal["error"] = "error"
    message: str = Field(..., description="Error message")
    code: Optional[Literal["MISSING_API_KEYS"]] = Field(None, description="Error code")
    missing_keys: Optional[List[str]] = Field(None, description="List of missing API keys")


class ServerToClientStoppedMessage(BaseModel):
    """Stop confirmation message."""
    type: Literal["stopped"] = "stopped"
    message: str = Field(..., description="Stop confirmation message")


class ServerToClientDataMessage(BaseModel):
    """Data update message with execution results."""
    type: Literal["data"] = "data"
    results: Dict[str, Dict[str, Any]] = Field(..., description="Execution results")
    stream: Optional[bool] = Field(default=None, description="Whether this is a streaming update")


class ServerToClientProgressMessage(BaseModel):
    """Progress update message."""
    type: Literal["progress"] = "progress"
    node_id: Optional[int] = Field(None, description="Node ID for progress update")
    progress: Optional[float] = Field(None, description="Progress percentage")
    text: Optional[str] = Field(None, description="Progress text")
    state: Optional[str] = Field(None, description="Progress state")
    meta: Optional[Dict[str, Any]] = Field(None, description="Additional metadata")


class ServerToClientQueuePositionMessage(BaseModel):
    """Queue position update message."""
    type: Literal["queue_position"] = "queue_position"
    position: int = Field(..., description="Position in execution queue")


# Union type for server messages
ServerToClientMessage = (
    ServerToClientStatusMessage |
    ServerToClientErrorMessage |
    ServerToClientStoppedMessage |
    ServerToClientDataMessage |
    ServerToClientProgressMessage |
    ServerToClientQueuePositionMessage
)

