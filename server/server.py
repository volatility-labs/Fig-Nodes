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
from uvicorn import run  # type: ignore

from core.api_key_vault import APIKeyVault
from core.node_registry import NODE_REGISTRY

from .api.v1.routes import router as api_v1_router
from .api.websocket_schemas import (
    ClientToServerGraphMessage,
    ClientToServerStopMessage,
    ServerToClientErrorMessage,
    ServerToClientStatusMessage,
    ServerToClientStoppedMessage,
)
from .queue import ExecutionJob, ExecutionQueue, JobState, execution_worker


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize single queue and worker for the entire server
    queue = ExecutionQueue()
    worker_task = asyncio.create_task(execution_worker(queue, NODE_REGISTRY))

    app.state.execution_queue = queue
    app.state.execution_worker = worker_task

    yield

    # Cleanup: cancel worker task and wait for it to finish
    worker_task.cancel()
    await asyncio.gather(worker_task, return_exceptions=True)


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


# Add error handling middleware
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


# Mount static files
app.mount(
    "/examples",
    StaticFiles(
        directory=os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "examples"))
    ),
    name="examples",
)


@app.get("/style.css")
def serve_style():
    css_path = os.path.join(os.path.dirname(__file__), "..", "ui", "static", "style.css")
    return FileResponse(css_path, media_type="text/css")


def _get_execution_queue(app: FastAPI) -> ExecutionQueue:
    """Get the execution queue for the server.

    Args:
        app: The FastAPI application instance containing the execution queue.

    Returns:
        ExecutionQueue: The execution queue for the server.
    """
    return app.state.execution_queue


async def _parse_client_message(
    raw_data: dict[str, Any],
) -> ClientToServerGraphMessage | ClientToServerStopMessage:
    """Parse and validate client message. Raises ValidationError on failure."""
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
):
    """Send error message to client."""
    error_msg = ServerToClientErrorMessage(
        type="error", message=message, code=code, missing_keys=missing_keys
    )
    await websocket.send_json(error_msg.model_dump(exclude_none=True))


async def _handle_graph_message(
    websocket: WebSocket, message: ClientToServerGraphMessage
) -> ExecutionJob | None:
    """Handle graph execution message. Returns job if successful, None otherwise."""
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

    # Start execution
    status_msg = ServerToClientStatusMessage(type="status", message="Starting execution...")
    await websocket.send_json(status_msg.model_dump())

    queue = _get_execution_queue(app)
    job = await queue.enqueue(websocket, graph_data)
    return job


async def _handle_stop_message(
    websocket: WebSocket,
    job: ExecutionJob | None,
    is_cancelling: bool,
    cancel_done_event: asyncio.Event,
) -> tuple[bool, ExecutionJob | None]:
    """Handle stop message. Returns (should_close, new_job_state)."""
    if job is None:
        stopped_msg = ServerToClientStoppedMessage(type="stopped", message="No active job to stop")
        await websocket.send_json(stopped_msg.model_dump())
        return False, None

    if is_cancelling:
        # Already cancelling, wait for completion
        await cancel_done_event.wait()
        stopped_msg = ServerToClientStoppedMessage(
            type="stopped", message="Stop completed (idempotent)"
        )
        await websocket.send_json(stopped_msg.model_dump())
        return False, None  # Don't close - keep connection alive

    # Cancel the job
    queue = _get_execution_queue(app)
    await queue.cancel_job(job)
    await job.done_event.wait()

    cancel_done_event.set()
    stopped_msg = ServerToClientStoppedMessage(
        type="stopped", message="Execution stopped and cleaned up"
    )
    await websocket.send_json(stopped_msg.model_dump())
    return False, None  # Don't close - keep connection alive


async def _cleanup_job(job: ExecutionJob | None):
    """Clean up job if it's still running."""
    if job is not None and job.state not in [JobState.DONE, JobState.CANCELLED]:
        queue = _get_execution_queue(app)
        await queue.cancel_job(job)
        await job.done_event.wait()


@app.get("/")
def read_root():
    return FileResponse(
        os.path.join(os.path.dirname(__file__), "..", "ui", "static/dist", "index.html")
    )


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
        await _cleanup_job(job)

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


if "PYTEST_CURRENT_TEST" not in os.environ:
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

if __name__ == "__main__":
    host = os.environ.get("HOST", "0.0.0.0")
    port_str = os.environ.get("PORT", "8000")
    port = int(port_str) if port_str.isdigit() else 8000
    run(app, host=host, port=port)
