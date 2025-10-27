"""
FastAPI server for Fig-Node graph execution.

This module provides:
- WebSocket endpoint for graph execution
- Queue-based job processing
- API key validation
- Static file serving
"""

import asyncio
import os
import traceback
from contextlib import asynccontextmanager
from typing import Any, Literal

from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import ValidationError
from starlette.websockets import WebSocketState
from uvicorn import run  # type: ignore[import-untyped]

from core.api_key_vault import APIKeyVault
from core.node_registry import NODE_REGISTRY
from server.api.v1.routes import router as api_v1_router
from server.api.websocket_schemas import (
    ClientToServerGraphMessage,
    ClientToServerStopMessage,
    ServerToClientErrorMessage,
    ServerToClientStatusMessage,
    ServerToClientStoppedMessage,
)
from server.queue import ExecutionJob, ExecutionQueue, execution_worker

# ============================================================================
# Lifespan Management
# ============================================================================


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifespan: initialize and cleanup execution queue."""
    # Initialize single queue and worker for the entire server
    queue = ExecutionQueue()
    worker_task = asyncio.create_task(execution_worker(queue, NODE_REGISTRY))

    app.state.execution_queue = queue
    app.state.execution_worker = worker_task

    yield

    # Cleanup: cancel worker task and wait for it to finish
    worker_task.cancel()
    await asyncio.gather(worker_task, return_exceptions=True)


# ============================================================================
# Application Initialization
# ============================================================================


app: FastAPI = FastAPI(
    title="Fig-Node API",
    description="Graph execution and node registry API for agentic finance and trading workflows",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
)

# Include API v1 router
app.include_router(api_v1_router, prefix="/api/v1")


# ============================================================================
# Exception Handlers
# ============================================================================


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Handle Pydantic validation errors."""
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={"error": "Validation error", "details": exc.errors()},
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """Handle general exceptions."""
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"error": "Internal server error", "message": str(exc)},
    )


# ============================================================================
# Helper Functions
# ============================================================================


def _get_execution_queue(app: FastAPI) -> ExecutionQueue:
    """Get the execution queue from the application state.

    Args:
        app: The FastAPI application instance containing the execution queue.

    Returns:
        ExecutionQueue: The execution queue for the server.
    """
    return app.state.execution_queue


async def _parse_client_message(
    raw_data: dict[str, Any],
) -> ClientToServerGraphMessage | ClientToServerStopMessage:
    """Parse and validate client WebSocket message.

    Args:
        raw_data: Raw JSON data from client.

    Returns:
        Parsed message (graph or stop).

    Raises:
        ValidationError: If message format is invalid.
    """
    # Try graph message first
    try:
        return ClientToServerGraphMessage.model_validate(raw_data)
    except ValidationError:
        # Try stop message
        return ClientToServerStopMessage.model_validate(raw_data)


async def _send_error_message(
    websocket: WebSocket,
    message: str,
    code: Literal["MISSING_API_KEYS"] | None = None,
    missing_keys: list[str] | None = None,
    job_id: int | None = None,
):
    """Send error message to client via WebSocket.

    Args:
        websocket: WebSocket connection to client.
        message: Error message text.
        code: Optional error code.
        missing_keys: Optional list of missing API keys.
        job_id: Optional job ID.
    """
    error_msg = ServerToClientErrorMessage(
        type="error", message=message, code=code, missing_keys=missing_keys, job_id=job_id
    )
    await websocket.send_json(error_msg.model_dump(exclude_none=True))


# ============================================================================
# WebSocket Message Handlers
# ============================================================================


async def _handle_graph_message(
    websocket: WebSocket, message: ClientToServerGraphMessage
) -> ExecutionJob | None:
    """Handle graph execution message.

    Validates API keys and enqueues the job for execution.

    Args:
        websocket: WebSocket connection to client.
        message: Graph execution message.

    Returns:
        ExecutionJob if successful, None if validation failed.
    """
    graph_data = message.graph_data

    # Validate required API keys
    vault = APIKeyVault()
    required_keys = vault.get_required_for_graph(graph_data, NODE_REGISTRY)
    missing = [k for k in required_keys if not vault.get(k)]

    if missing:
        await _send_error_message(
            websocket,
            message=f"Missing API keys: {', '.join(missing)}. Please set them in the settings menu.",
            code="MISSING_API_KEYS",
            missing_keys=missing,
        )
        return None

    # Enqueue job first to get job_id
    queue = _get_execution_queue(app)
    job = await queue.enqueue(websocket, graph_data)

    # Send status message with job_id
    from server.api.websocket_schemas import ExecutionState

    status_msg = ServerToClientStatusMessage(
        type="status", state=ExecutionState.QUEUED, message="Queued for execution", job_id=job.id
    )
    await websocket.send_json(status_msg.model_dump())

    return job


# Handle a stop message from the UI client
# If there is no active job, send a stopped message and return False
# If the job is already being cancelled, wait for the cancellation to complete and send a stopped message
# Otherwise, cancel the job and send a stopped message
# Return True if the job was cancelled, False otherwise
# Return the updated job state


async def _handle_stop_message(
    websocket: WebSocket,
    job: ExecutionJob | None,
    is_cancelling: bool,
    cancel_done_event: asyncio.Event,
) -> tuple[bool, ExecutionJob | None]:
    """Handle stop execution message.

    Args:
        websocket: WebSocket connection to client.
        job: Current execution job, if any.
        is_cancelling: Whether cancellation is already in progress.
        cancel_done_event: Event to signal cancellation completion.

    Returns:
        Tuple of (should_close, updated_job_state).
    """
    if job is None:
        stopped_msg = ServerToClientStoppedMessage(
            type="stopped", message="No active job to stop", job_id=None
        )
        await websocket.send_json(stopped_msg.model_dump())
        return False, None

    if is_cancelling:
        # Already cancelling, wait for completion
        await cancel_done_event.wait()
        stopped_msg = ServerToClientStoppedMessage(
            type="stopped", message="Stop completed (idempotent)", job_id=None
        )
        await websocket.send_json(stopped_msg.model_dump())
        return False, None

    # Cancel the job by sending the cancel event to the ExecutionWorker
    queue = _get_execution_queue(app)
    await queue.cancel_job(job)
    await job.done_event.wait()

    cancel_done_event.set()
    return False, None


# ============================================================================
# Routes
# ============================================================================


@app.get("/")
def read_root():
    """Serve the main application UI."""
    return FileResponse(
        os.path.join(os.path.dirname(__file__), "..", "ui", "static/dist", "index.html")
    )


@app.get("/style.css")
def serve_style():
    """Serve the main stylesheet."""
    css_path = os.path.join(os.path.dirname(__file__), "..", "ui", "static", "style.css")
    return FileResponse(css_path, media_type="text/css")


@app.websocket("/execute")
async def execute_endpoint(websocket: WebSocket):
    """WebSocket endpoint for graph execution.

    Accepts two message types:
    - "graph": Start execution with graph_data
    - "stop": Stop current execution

    Returns various message types including status, error, data, progress, and stopped.
    """
    await websocket.accept()
    job = None
    is_cancelling = False
    cancel_done_event = asyncio.Event()

    try:
        while True:
            raw_data = await websocket.receive_json()

            # Parse and validate message
            try:
                message = await _parse_client_message(raw_data)
            except ValidationError as e:
                await _send_error_message(
                    websocket, message=f"Invalid message format: {e.errors()[0]['msg']}"
                )
                continue

            # Handle message based on type
            if message.type == "graph":
                job = await _handle_graph_message(websocket, message)

            elif message.type == "stop":
                await _handle_stop_message(websocket, job, is_cancelling, cancel_done_event)
                is_cancelling = True

    except WebSocketDisconnect as e:
        print(f"Client disconnected: code={e.code}, reason={e.reason or 'none'}")

    except Exception as e:
        print(f"ERROR_TRACE: Exception in execute_endpoint: {type(e).__name__}: {str(e)}")
        traceback.print_exc()

        # Try to send error, but don't fail if websocket is closed
        if websocket.client_state == WebSocketState.CONNECTED:
            try:
                await _send_error_message(websocket, message=str(e))
            except Exception as send_error:
                print(
                    f"ERROR_TRACE: Failed to send error message: {type(send_error).__name__}: {str(send_error)}"
                )


# ============================================================================
# Static File Mounts (Conditional)
# ============================================================================

if "PYTEST_CURRENT_TEST" not in os.environ:
    app.mount(
        "/examples",
        StaticFiles(
            directory=os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "examples"))
        ),
        name="examples",
    )
    app.mount(
        "/static",
        StaticFiles(directory=os.path.join(os.path.dirname(__file__), "..", "ui", "static/dist")),
        name="static",
    )
    app.mount(
        "/",
        StaticFiles(
            directory=os.path.join(os.path.dirname(__file__), "..", "ui", "static", "dist"),
            html=True,
        ),
        name="root_static",
    )


# ============================================================================
# Main Entry Point
# ============================================================================

if __name__ == "__main__":
    host = os.environ.get("HOST", "0.0.0.0")
    port_str = os.environ.get("PORT", "8000")
    port = int(port_str) if port_str.isdigit() else 8000
    run(app, host=host, port=port)
