import os
import asyncio

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from typing import Dict, Any, List
from core.node_registry import NODE_REGISTRY
from core.types_utils import parse_type

# Add back missing imports
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from contextlib import asynccontextmanager
from dotenv import unset_key, find_dotenv

# Import the refactored queue components
from .queue import ExecutionQueue, execution_worker
from .queue import JobState
from core.api_key_vault import APIKeyVault

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

@app.get("/style.css")
def serve_style():
    css_path = os.path.join(os.path.dirname(__file__), "static", "style.css")
    return FileResponse(css_path, media_type="text/css")

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
            "required_keys": getattr(cls, 'required_keys', []),
            "uiModule": getattr(cls, 'ui_module', None) or (
                "io/TextInputNodeUI" if name == "TextInput" else
                "io/LoggingNodeUI" if name == "Logging" else
                "io/SaveOutputNodeUI" if name == "SaveOutput" else
                "io/ExtractSymbolsNodeUI" if name == "ExtractSymbols" else
                "llm/LLMMessagesBuilderNodeUI" if name == "LLMMessagesBuilder" else
                "llm/OllamaChatNodeUI" if name == "OllamaChat" else
                "llm/OpenRouterChatNodeUI" if name == "OpenRouterChat" else
                "llm/SystemPromptLoaderNodeUI" if name == "SystemPromptLoader" else
                "market/PolygonUniverseNodeUI" if name == "PolygonUniverse" else
                "market/PolygonCustomBarsNodeUI" if name == "PolygonCustomBars" else
                "market/PolygonBatchCustomBarsNodeUI" if name == "PolygonBatchCustomBars" else
                "market/SMACrossoverFilterNodeUI" if name == "SMACrossoverFilter" else
                "market/ADXFilterNodeUI" if name == "ADXFilter" else
                "market/RSIFilterNodeUI" if name == "RSIFilter" else
                "market/ATRFilterNodeUI" if name == "ATRFilter" else
                "market/ATRIndicatorNodeUI" if name == "ATRIndicator" else
                "market/SMAFilterNodeUI" if name == "SMAFilter" else
                "market/OrbFilterNodeUI" if name == "OrbFilter" else
                "market/LodFilterNodeUI" if name == "LodFilter" else
                "market/EmaRangeFilterNodeUI" if name == "EmaRangeFilter" else
                "market/AtrXFilterNodeUI" if name == "AtrXFilter" else
                "market/AtrXIndicatorNodeUI" if name == "AtrXIndicator" else
                "market/OHLCVPlotNodeUI" if name == "OHLCVPlot" else
                None
            )
        }
    return {"nodes": nodes_meta}

@app.get("/api_keys")
def get_api_keys():
    vault = APIKeyVault()
    return {"keys": vault.get_all()}

@app.get("/api_keys/meta")
def get_api_keys_meta():
    vault = APIKeyVault()
    return {"meta": vault.get_known_key_metadata()}

@app.post("/api_keys")
async def set_api_key(request: Dict[str, Any]):
    key_name = request.get("key_name")
    value = request.get("value")
    if not key_name:
        return {"error": "key_name required"}
    vault = APIKeyVault()
    vault.set(key_name, value or "")
    return {"status": "success"}

@app.delete("/api_keys")
async def delete_api_key(request: Dict[str, Any]):
    key_name = request.get("key_name")
    if not key_name:
        return {"error": "key_name required"}
    vault = APIKeyVault()
    # Assuming we add unset to vault; for now, implement directly
    if key_name in vault._keys:
        del vault._keys[key_name]
    if key_name in os.environ:
        del os.environ[key_name]
    dotenv_path = find_dotenv()
    if dotenv_path:
        unset_key(dotenv_path, key_name)
    return {"status": "success"}

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
                # Validate required keys
                vault = APIKeyVault()
                required_keys = vault.get_required_for_graph(graph_data)
                missing = [k for k in required_keys if not vault.get(k)]
                if missing:
                    await websocket.send_json({
                        "type": "error",
                        "code": "MISSING_API_KEYS",
                        "missing_keys": missing,
                        "message": f"Missing API keys: {', '.join(missing)}. Please set them in the settings menu."
                    })
                    continue
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
        print(f"ERROR_TRACE: Exception in execute_endpoint: {type(e).__name__}: {str(e)}")
        import traceback
        traceback.print_exc()
        try:
            await websocket.send_json({"type": "error", "message": str(e)})
        except Exception as send_error:
            print(f"ERROR_TRACE: Failed to send error message: {type(send_error).__name__}: {str(send_error)}")
            pass
    finally:
        pass

# Mount the built frontend at root as well, so the app is served from '/'
if 'PYTEST_CURRENT_TEST' not in os.environ:
    app.mount("/", StaticFiles(directory=os.path.join(os.path.dirname(__file__), "static", "dist"), html=True), name="root_static")

if __name__ == "__main__":
    import uvicorn
    # Allow configuring host/port via environment variables
    host = os.environ.get("HOST", "0.0.0.0")
    port_str = os.environ.get("PORT", "8000")
    try:
        port = int(port_str)
    except ValueError:
        port = 8000
    uvicorn.run(app, host=host, port=port)
