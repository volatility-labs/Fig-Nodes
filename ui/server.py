import sys
import os
import asyncio
from typing import cast
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
import pandas as pd

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from typing import Dict, Any, List
from core.graph_executor import GraphExecutor
from core.node_registry import NODE_REGISTRY
import typing
from core.types_utils import parse_type
from starlette.websockets import WebSocketState

# Add back missing imports
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from contextlib import asynccontextmanager

# Import the refactored queue components
from .queue import ExecutionQueue, execution_worker, _serialize_results
from .queue import JobState

@asynccontextmanager
async def lifespan(app: FastAPI):
    if not hasattr(app.state, "loop_queues"):
        app.state.loop_queues = {}
    if not hasattr(app.state, "loop_workers"):
        app.state.loop_workers = {}
    yield
    loop_workers = getattr(app.state, "loop_workers", {})
    current_loop_id = id(asyncio.get_running_loop())
    tasks: List[asyncio.Task] = loop_workers.get(current_loop_id, [])
    for t in tasks:
        t.cancel()
    if tasks:
        await asyncio.gather(*tasks, return_exceptions=True)

app = FastAPI(lifespan=lifespan)

app.mount(
    "/examples",
    StaticFiles(directory=os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "examples"))),
    name="examples",
)

if 'PYTEST_CURRENT_TEST' not in os.environ:
    app.mount("/static", StaticFiles(directory=os.path.join(os.path.dirname(__file__), "static/dist")), name="static")

def _get_queue_for_current_loop(app) -> ExecutionQueue:
    """Get or create the ExecutionQueue for the current event loop."""
    loop_id = id(asyncio.get_running_loop())
    if not hasattr(app.state, "loop_queues"):
        app.state.loop_queues = {}
    if not hasattr(app.state, "loop_workers"):
        app.state.loop_workers = {}
    queue = app.state.loop_queues.get(loop_id)
    if queue is None:
        queue = ExecutionQueue()
        app.state.loop_queues[loop_id] = queue
    workers: List[asyncio.Task] = app.state.loop_workers.get(loop_id, [])
    alive_tasks = [t for t in workers if not t.done() and not t.cancelled()]
    if not alive_tasks:
        task = asyncio.create_task(execution_worker(queue, NODE_REGISTRY))
        alive_tasks.append(task)
    app.state.loop_workers[loop_id] = alive_tasks
    return queue

@app.get("/")
def read_root():
    return FileResponse(os.path.join(os.path.dirname(__file__), "static/dist", "index.html"))

@app.get("/nodes")
def list_nodes():
    nodes_meta = {}
    for name, cls in NODE_REGISTRY.items():
        inputs_meta = cls.inputs if isinstance(cls.inputs, list) else {k: parse_type(v) for k, v in cls.inputs.items()}
        outputs_meta = cls.outputs if isinstance(cls.outputs, list) else {k: parse_type(v) for k, v in cls.outputs.items()}
        params = []
        if hasattr(cls, 'params_meta'):
            params = cls.params_meta
        elif hasattr(cls, 'default_params'):
            for k, v in cls.default_params.items():
                param_type = 'number' if any(word in k.lower() for word in ['day', 'period']) else 'text'
                default_val = v if isinstance(v, (int, float, str, bool)) else None
                params.append({"name": k, "type": param_type, "default": default_val})
        
        module_name = cls.__module__
        category = getattr(cls, 'CATEGORY', None)
        if not category:
            if 'UniverseNode' in name:
                category = "DataSource"
            elif 'nodes.core' in module_name:
                category = "Core"
            elif getattr(cls, 'is_streaming', False):
                category = "Streaming"
            else:
                category = "Plugins"
            
        nodes_meta[name] = {
            "inputs": inputs_meta,
            "outputs": outputs_meta,
            "params": params,
            "category": category,
            "uiModule": getattr(cls, 'ui_module', None) or (
                "io/TextInputNodeUI" if name == "TextInputNode" else
                "io/LoggingNodeUI" if name == "LoggingNode" else
                "OllamaModelSelectorNodeUI" if name == "OllamaModelSelectorNode" else
                "OllamaChatViewerNodeUI" if name == "OllamaChatViewerNode" else
                "market/PolygonUniverseNodeUI" if name == "PolygonUniverseNode" else
                "market/PolygonAPIKeyNodeUI" if name == "PolygonAPIKeyNode" else
                "market/PolygonCustomBarsNodeUI" if name == "PolygonCustomBarsNode" else
                "market/PolygonBatchCustomBarsNodeUI" if name == "PolygonBatchCustomBarsNode" else
                "market/SMACrossoverFilterNodeUI" if name == "SMACrossoverFilterNode" else
                "market/ADXFilterNodeUI" if name == "ADXFilterNode" else
                "market/RSIFilterNodeUI" if name == "RSIFilterNode" else
                "io/ExtractSymbolsNodeUI" if name == "ExtractSymbolsNode" else
                None
            )
        }
    return {"nodes": nodes_meta}

@app.websocket("/execute")
async def execute_endpoint(websocket: WebSocket):
    await websocket.accept()
    job = None
    is_cancelling = False  # Idempotency flag
    cancel_done_event = asyncio.Event()  # For awaiting cancel completion

    try:
        while True:
            data = await websocket.receive_json()
            msg_type = data.get("type")
            is_raw_graph = msg_type is None and "nodes" in data and "links" in data
            if msg_type == "graph" or is_raw_graph:
                # Normalize graph payload
                graph_data = data.get("graph_data") if msg_type == "graph" else {"nodes": data.get("nodes", []), "links": data.get("links", [])}
                # Always use queue mode
                await websocket.send_json({"type": "status", "message": "Starting execution..."})
                queue = _get_queue_for_current_loop(app)
                job = await queue.enqueue(websocket, graph_data)
            elif data.get("type") == "stop":
                if job is None:
                    print("Server: No active job to stop")
                    await websocket.send_json({"type": "stopped", "message": "No active job to stop"})
                    continue

                if is_cancelling:
                    print("Server: Already cancelling, waiting for completion")
                    # Idempotent: already cancelling, just await existing
                    await cancel_done_event.wait()
                    await websocket.send_json({"type": "stopped", "message": "Stop completed (idempotent)"})
                    await websocket.close()
                    continue

                is_cancelling = True
                queue = _get_queue_for_current_loop(app)
                await queue.cancel_job(job)
                await job.done_event.wait()  # Await cleanup

                cancel_done_event.set()
                await websocket.send_json({"type": "stopped", "message": "Execution stopped and cleaned up"})
                await websocket.close()
                is_cancelling = False
            else:
                await websocket.send_json({"type": "error", "message": "Unknown message type"})
    except WebSocketDisconnect as e:
        print(f"Client disconnected: code={e.code}, reason={e.reason or 'none'}")
        if job is not None and job.state not in [JobState.DONE, JobState.CANCELLED]:
            queue = _get_queue_for_current_loop(app)
            await queue.cancel_job(job)
            await job.done_event.wait()  # Ensure cleanup even on disconnect
    except Exception as e:
        try:
            await websocket.send_json({"type": "error", "message": str(e)})
        except Exception:
            pass
    finally:
        pass

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
