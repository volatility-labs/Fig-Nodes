import os
import asyncio
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request, status
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from typing import List
from core.graph_executor import ExecutionResults
from core.node_registry import NODE_REGISTRY
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from contextlib import asynccontextmanager
from pydantic import ValidationError
from .queue import ExecutionQueue, execution_worker
from .queue import JobState
from core.api_key_vault import APIKeyVault
from uvicorn import run # type: ignore
from .api.websocket_schemas import (
    ClientToServerGraphMessage,
    ClientToServerStopMessage,
    ServerToClientStatusMessage,
    ServerToClientErrorMessage,
    ServerToClientStoppedMessage,
)
from .api.v1.routes import router as api_v1_router

@asynccontextmanager
async def lifespan(app: FastAPI):
    if not hasattr(app.state, "loop_queues"):
        app.state.loop_queues = {}
    if not hasattr(app.state, "loop_workers"):
        app.state.loop_workers = {}
    yield

    loop_workers = getattr(app.state, "loop_workers", {})
    current_loop_id = id(asyncio.get_running_loop())
    tasks: List[asyncio.Task[ExecutionResults]] = loop_workers.get(current_loop_id, [])
    
    for t in tasks:
        t.cancel()
    if tasks:
        await asyncio.gather(*tasks, return_exceptions=True)

app: FastAPI = FastAPI(
    title="Fig-Node API",
    description="Graph execution and node registry API for agentic finance and trading workflows",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json"
)

# Include API v1 router
app.include_router(api_v1_router, prefix="/api/v1")

# Add error handling middleware
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Handle Pydantic validation errors."""
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "error": "Validation error",
            "details": exc.errors()
        }
    )

@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """Handle general exceptions."""
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error": "Internal server error",
            "message": str(exc)
        }
    )

# Mount static files
app.mount(
    "/examples",
    StaticFiles(directory=os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "examples"))),
    name="examples",
)

@app.get("/style.css")
def serve_style():
    css_path = os.path.join(os.path.dirname(__file__), "..", "ui", "static", "style.css")
    return FileResponse(css_path, media_type="text/css")

def _get_queue_for_current_loop(app: FastAPI) -> ExecutionQueue:
    """Get or create the ExecutionQueue for the current event loop."""
    loop_id = id(asyncio.get_running_loop())
    queue = app.state.loop_queues.get(loop_id)
    if queue is None:
        queue = ExecutionQueue()
        app.state.loop_queues[loop_id] = queue
    workers: List[asyncio.Task[None]] = app.state.loop_workers.get(loop_id, [])
    alive_tasks = [t for t in workers if not t.done() and not t.cancelled()]
    if not alive_tasks:
        task = asyncio.create_task(execution_worker(queue, NODE_REGISTRY))
        alive_tasks.append(task)
    app.state.loop_workers[loop_id] = alive_tasks
    return queue

@app.get("/")
def read_root():
    return FileResponse(os.path.join(os.path.dirname(__file__), "..", "ui", "static/dist", "index.html"))

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
            
            # Validate incoming message with Pydantic
            try:
                # Try to parse as graph message first
                try:
                    message: ClientToServerGraphMessage | ClientToServerStopMessage = ClientToServerGraphMessage.model_validate(raw_data)
                except ValidationError:
                    # Try as stop message
                    message = ClientToServerStopMessage.model_validate(raw_data)
            except ValidationError as e:
                error_msg = ServerToClientErrorMessage(
                    type="error",
                    message=f"Invalid message format: {e.errors()[0]['msg']}",
                    code=None,
                    missing_keys=None
                )
                await websocket.send_json(error_msg.model_dump(exclude_none=True))
                continue
            
            # Handle graph execution message
            if message.type == "graph":
                graph_data = message.graph_data
                
                # Validate required API keys
                vault = APIKeyVault()
                required_keys = vault.get_required_for_graph(graph_data, NODE_REGISTRY)
                missing = [k for k in required_keys if not vault.get(k)]
                
                if missing:
                    error_msg = ServerToClientErrorMessage(
                        type="error",
                        code="MISSING_API_KEYS",
                        missing_keys=missing,
                        message=f"Missing API keys: {', '.join(missing)}. Please set them in the settings menu."
                    )
                    await websocket.send_json(error_msg.model_dump(exclude_none=True))
                    continue
                
                # Start execution
                status_msg = ServerToClientStatusMessage(
                    type="status",
                    message="Starting execution..."
                )
                await websocket.send_json(status_msg.model_dump())
                queue = _get_queue_for_current_loop(app)
                job = await queue.enqueue(websocket, graph_data)
            
            # Handle stop message
            elif message.type == "stop":
                if job is None:
                    print("Server: No active job to stop")
                    stopped_msg = ServerToClientStoppedMessage(
                        type="stopped",
                        message="No active job to stop"
                    )
                    await websocket.send_json(stopped_msg.model_dump())
                    continue

                if is_cancelling:
                    print("Server: Already cancelling, waiting for completion")
                    await cancel_done_event.wait()
                    stopped_msg = ServerToClientStoppedMessage(
                        type="stopped",
                        message="Stop completed (idempotent)"
                    )
                    await websocket.send_json(stopped_msg.model_dump())
                    await websocket.close()
                    continue

                is_cancelling = True
                queue = _get_queue_for_current_loop(app)
                await queue.cancel_job(job)
                await job.done_event.wait()

                cancel_done_event.set()
                stopped_msg = ServerToClientStoppedMessage(
                    type="stopped",
                    message="Execution stopped and cleaned up"
                )
                await websocket.send_json(stopped_msg.model_dump())
                await websocket.close()
                is_cancelling = False
                
    except WebSocketDisconnect as e:
        print(f"Client disconnected: code={e.code}, reason={e.reason or 'none'}")
        if job is not None and job.state not in [JobState.DONE, JobState.CANCELLED]:
            queue = _get_queue_for_current_loop(app)
            await queue.cancel_job(job)
            await job.done_event.wait()
    except Exception as e:
        print(f"ERROR_TRACE: Exception in execute_endpoint: {type(e).__name__}: {str(e)}")
        import traceback
        traceback.print_exc()
        try:
            error_msg = ServerToClientErrorMessage(
                type="error",
                message=str(e),
                code=None,
                missing_keys=None
            )
            await websocket.send_json(error_msg.model_dump(exclude_none=True))
        except Exception as send_error:
            print(f"ERROR_TRACE: Failed to send error message: {type(send_error).__name__}: {str(send_error)}")
            pass


if 'PYTEST_CURRENT_TEST' not in os.environ:
    app.mount("/static", StaticFiles(directory=os.path.join(os.path.dirname(__file__), "..", "ui", "static/dist")), name="static")
    app.mount("/", StaticFiles(directory=os.path.join(os.path.dirname(__file__), "..", "ui", "static", "dist"), html=True), name="root_static")

if __name__ == "__main__":
    host = os.environ.get("HOST", "0.0.0.0")
    port_str = os.environ.get("PORT", "8000")
    port = int(port_str) if port_str.isdigit() else 8000
    run(app, host=host, port=port)
