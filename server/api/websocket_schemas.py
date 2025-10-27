"""Pydantic schemas for WebSocket message validation."""

from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, Field

from core.types_registry import SerialisableGraph

# ============================================================================
# SHARED ENUMS
# ============================================================================


class ExecutionState(str, Enum):
    """Execution state enum - must match frontend."""

    QUEUED = "queued"
    RUNNING = "running"
    STREAMING = "streaming"
    FINISHED = "finished"
    ERROR = "error"
    CANCELLED = "cancelled"


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
    """Status update message - state is required."""

    type: Literal["status"] = "status"
    state: ExecutionState = Field(..., description="Current execution state")
    message: str = Field(..., description="Human-readable status message")
    job_id: int = Field(..., description="Job ID for this execution")


class ServerToClientErrorMessage(BaseModel):
    """Error message."""

    type: Literal["error"] = "error"
    message: str = Field(..., description="Error message")
    code: Literal["MISSING_API_KEYS"] | None = Field(None, description="Error code")
    missing_keys: list[str] | None = Field(None, description="List of missing API keys")
    job_id: int | None = Field(None, description="Job ID if applicable")


class ServerToClientStoppedMessage(BaseModel):
    """Stop confirmation message."""

    type: Literal["stopped"] = "stopped"
    message: str = Field(..., description="Stop confirmation message")
    job_id: int | None = Field(None, description="Job ID that was stopped")


class ServerToClientDataMessage(BaseModel):
    """Data update message with execution results."""

    type: Literal["data"] = "data"
    results: dict[str, dict[str, Any]] = Field(..., description="Execution results")
    stream: bool = Field(default=False, description="Whether this is a streaming update")
    job_id: int = Field(..., description="Job ID for this data")


class ServerToClientProgressMessage(BaseModel):
    """Progress update message."""

    type: Literal["progress"] = "progress"
    node_id: int | None = Field(None, description="Node ID for progress update")
    progress: float | None = Field(None, description="Progress percentage")
    text: str | None = Field(None, description="Progress text")
    meta: dict[str, Any] | None = Field(None, description="Additional metadata")
    job_id: int = Field(..., description="Job ID for this progress")


class ServerToClientQueuePositionMessage(BaseModel):
    """Queue position update message."""

    type: Literal["queue_position"] = "queue_position"
    position: int = Field(..., description="Position in execution queue")
    job_id: int = Field(..., description="Job ID for queue position")


# Union type for server messages
ServerToClientMessage = (
    ServerToClientStatusMessage
    | ServerToClientErrorMessage
    | ServerToClientStoppedMessage
    | ServerToClientDataMessage
    | ServerToClientProgressMessage
    | ServerToClientQueuePositionMessage
)
