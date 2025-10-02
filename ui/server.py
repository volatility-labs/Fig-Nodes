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

# Import the refactored queue components
from .queue import ExecutionQueue, execution_worker, _serialize_results
from .queue import JobState

app = FastAPI()

EXECUTION_QUEUE = ExecutionQueue()
_WORKER_TASKS: List[asyncio.Task] = []

@app.on_event("startup")
async def _startup_queue_worker():
    # Always start queue worker now
    task = asyncio.create_task(execution_worker(EXECUTION_QUEUE, NODE_REGISTRY))
    _WORKER_TASKS.append(task)

@app.on_event("shutdown")
async def _shutdown_queue_worker():
    for t in _WORKER_TASKS:
        t.cancel()
    if _WORKER_TASKS:
        await asyncio.gather(*_WORKER_TASKS, return_exceptions=True)

app.mount("/static", StaticFiles(directory=os.path.join(os.path.dirname(__file__), "static/dist")), name="static")

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
                "TextInputNodeUI" if name == "TextInputNode" else
                "LoggingNodeUI" if name == "LoggingNode" else
                "OllamaModelSelectorNodeUI" if name == "OllamaModelSelectorNode" else
                "OllamaChatViewerNodeUI" if name == "OllamaChatViewerNode" else
                "PolygonUniverseNodeUI" if name == "PolygonUniverseNode" else
                "PolygonAPIKeyNodeUI" if name == "PolygonAPIKeyNode" else
                "PolygonCustomBarsNodeUI" if name == "PolygonCustomBarsNode" else
                "PolygonBatchCustomBarsNodeUI" if name == "PolygonBatchCustomBarsNode" else
                "SMACrossoverFilterNodeUI" if name == "SMACrossoverFilterNode" else
                "ADXFilterNodeUI" if name == "ADXFilterNode" else
                "RSIFilterNodeUI" if name == "RSIFilterNode" else
                "ExtractSymbolsNodeUI" if name == "ExtractSymbolsNode" else
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
                # Ensure a live worker is running (handle cases where startup worker isn't active in tests)
                alive_tasks = [t for t in _WORKER_TASKS if not t.done() and not t.cancelled()]
                if not alive_tasks:
                    task = asyncio.create_task(execution_worker(EXECUTION_QUEUE, NODE_REGISTRY))
                    alive_tasks.append(task)
                # Replace the task list with only alive tasks (plus newly started one if any)
                _WORKER_TASKS[:] = alive_tasks
                job = await EXECUTION_QUEUE.enqueue(websocket, graph_data)
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
                await EXECUTION_QUEUE.cancel_job(job)
                await job.done_event.wait()  # Await cleanup

                cancel_done_event.set()
                await websocket.send_json({"type": "stopped", "message": "Execution stopped and cleaned up"})
                await websocket.close()
                is_cancelling = False
            else:
                await websocket.send_json({"type": "error", "message": "Unknown message type"})
    except WebSocketDisconnect:
        print("Client disconnected unexpectedly.")
        if job is not None and job.state not in [JobState.DONE, JobState.CANCELLED]:
            await EXECUTION_QUEUE.cancel_job(job)
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
