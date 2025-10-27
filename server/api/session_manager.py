"""Session management for WebSocket connections."""

import uuid

from fastapi import WebSocket
from starlette.websockets import WebSocketState

from server.api.websocket_schemas import (
    ClientToServerConnectMessage,
    ServerToClientSessionMessage,
)
from server.queue import ExecutionJob


class ConnectionRegistry:
    """Manage WebSocket sessions and track active connections."""

    def __init__(self):
        self.sessions: dict[str, WebSocket] = {}
        self.session_to_job: dict[str, ExecutionJob | None] = {}

    def register(self, session_id: str, websocket: WebSocket) -> None:
        """Register a new session with its WebSocket connection."""
        self.sessions[session_id] = websocket

    def unregister(self, session_id: str, websocket: WebSocket | None = None) -> None:
        """Unregister a session and clean up associated job.

        If websocket is provided, only unregister if it matches the stored websocket.
        This prevents race conditions where a new connection replaced an old one.

        Args:
            session_id: Session ID to unregister.
            websocket: Optional websocket to check against stored websocket.
        """
        # If websocket provided, only unregister if it matches (prevent race conditions)
        if websocket is not None:
            stored_ws = self.sessions.get(session_id)
            if stored_ws is not websocket:
                # Different websocket already registered - don't unregister
                print(f"Skipping unregister for session {session_id} - already replaced")
                return

        self.sessions.pop(session_id, None)
        self.session_to_job.pop(session_id, None)

    def get_websocket(self, session_id: str) -> WebSocket | None:
        """Get WebSocket connection for a session."""
        return self.sessions.get(session_id)

    def has_session(self, session_id: str) -> bool:
        """Check if a session exists."""
        return session_id in self.sessions

    def set_job(self, session_id: str, job: ExecutionJob | None) -> None:
        """Associate a job with a session."""
        self.session_to_job[session_id] = job

    def get_job(self, session_id: str) -> ExecutionJob | None:
        """Get job associated with a session."""
        return self.session_to_job.get(session_id)


async def close_old_connection_if_exists(
    registry: ConnectionRegistry, session_id: str, new_websocket: WebSocket
) -> None:
    """Close old WebSocket connection if it exists for this session.

    This ensures only one active connection per session.

    Args:
        registry: Connection registry to check.
        session_id: Session ID to check for existing connection.
        new_websocket: The new websocket that will replace the old one.
    """
    if session_id in registry.sessions:
        old_ws = registry.sessions[session_id]
        # Only close if it's a different websocket instance
        if old_ws is not new_websocket and old_ws.client_state == WebSocketState.CONNECTED:
            print(f"Closing old connection for session {session_id}")
            try:
                await old_ws.close()
            except Exception as e:
                print(f"Error closing old connection: {e}")


async def establish_session(
    websocket: WebSocket,
    registry: ConnectionRegistry,
    connect_msg: ClientToServerConnectMessage,
) -> str:
    """Establish a WebSocket session.

    This function handles:
    - Validating or generating session_id
    - Closing old connections for the same session
    - Registering the new connection
    - Sending session confirmation to client

    Args:
        websocket: WebSocket connection from client.
        registry: Connection registry to store session.
        connect_msg: Connect message from client.

    Returns:
        The session_id (either reused or newly generated).

    Raises:
        Exception: If session establishment fails.
    """
    incoming_session_id = connect_msg.session_id

    # Check if session exists
    if incoming_session_id and registry.has_session(incoming_session_id):
        # Existing session - reuse it
        session_id = incoming_session_id
        print(f"Resuming existing session: {session_id}")
    else:
        # New session or session expired
        session_id = str(uuid.uuid4())
        print(f"Creating new session: {session_id}")

    # Close old connection if exists (prevents multiple connections per session)
    await close_old_connection_if_exists(registry, session_id, websocket)

    # Register new connection
    registry.register(session_id, websocket)

    # Send session ID back to client
    session_msg = ServerToClientSessionMessage(type="session", session_id=session_id)
    await websocket.send_json(session_msg.model_dump())

    print(f"Session established: {session_id}")
    return session_id
