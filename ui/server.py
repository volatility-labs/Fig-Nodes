import sys
import os
import asyncio
from typing import cast
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
import pandas as pd

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from typing import Dict, Any, List
from core.graph_executor import GraphExecutor
from nodes.base.base_node import BaseNode
import importlib.util
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from core.node_registry import NODE_REGISTRY
import typing
from core.types_utils import parse_type  # New import
from starlette.websockets import WebSocketState

app = FastAPI()

# Queue-based execution manager (single-worker, ComfyUI-like)
class ExecutionJob:
    def __init__(self, job_id: int, websocket: WebSocket, graph_data: Dict[str, Any]):
        self.id = job_id
        self.websocket = websocket
        self.graph_data = graph_data
        self.cancel_event = asyncio.Event()
        self.done_event = asyncio.Event()


class ExecutionQueue:
    def __init__(self):
        self._queue: asyncio.Queue[ExecutionJob] = asyncio.Queue()
        self._pending: List[ExecutionJob] = []
        self._running: typing.Optional[ExecutionJob] = None
        self._id_seq = 0
        self._lock = asyncio.Lock()

    async def enqueue(self, websocket: WebSocket, graph_data: Dict[str, Any]) -> ExecutionJob:
        async with self._lock:
            job = ExecutionJob(self._id_seq, websocket, graph_data)
            self._id_seq += 1
            self._pending.append(job)
            await self._queue.put(job)
            return job

    async def get_next(self) -> ExecutionJob:
        job = await self._queue.get()
        async with self._lock:
            if job in self._pending:
                self._pending.remove(job)
            self._running = job
        return job

    async def mark_done(self, job: ExecutionJob):
        async with self._lock:
            if self._running is job:
                self._running = None
        self._queue.task_done()

    async def position(self, job: ExecutionJob) -> int:
        async with self._lock:
            if self._running is job:
                return 0
            try:
                return self._pending.index(job)
            except ValueError:
                return 0


EXECUTION_QUEUE = ExecutionQueue()
_WORKER_TASKS: List[asyncio.Task] = []


def _serialize_value(v: Any):
    if isinstance(v, list):
        return [_serialize_value(item) for item in v]
    if isinstance(v, dict):
        return {str(key): _serialize_value(val) for key, val in v.items()}
    if hasattr(v, 'to_dict'):
        return v.to_dict()
    if isinstance(v, pd.DataFrame):
        return v.to_dict(orient='records')
    return str(v)


def _serialize_results(results: Dict[int, Dict[str, Any]]):
    return {str(node_id): {out: _serialize_value(val) for out, val in node_res.items()} for node_id, node_res in results.items()}


async def _execution_worker():
    while True:
        job = await EXECUTION_QUEUE.get_next()
        websocket = job.websocket
        executor: typing.Optional[GraphExecutor] = None
        try:
            print("Worker: Creating GraphExecutor")
            executor = GraphExecutor(job.graph_data, NODE_REGISTRY)
            print(f"Worker: GraphExecutor created, is_streaming={executor.is_streaming}")
            try:
                await websocket.send_json({"type": "status", "message": "Starting execution"})
            except Exception:
                pass

            if executor.is_streaming:
                print("Worker: Executing streaming path")
                try:
                    await websocket.send_json({"type": "status", "message": "Stream starting..."})
                except Exception:
                    pass
                stream_generator = executor.stream()
                try:
                    print("Worker: Getting initial results from stream generator")
                    initial_results = await anext(stream_generator)
                    print(f"Worker: Got initial results: {list(initial_results.keys())}")
                except StopAsyncIteration:
                    print("Worker: Stream generator exhausted on first anext()")
                    initial_results = {}
                try:
                    await websocket.send_json({"type": "data", "results": _serialize_results(initial_results), "stream": False})
                except Exception:
                    pass

                async def monitor_cancel():
                    while True:
                        await asyncio.sleep(0.5)
                        if job.cancel_event.is_set() or websocket.client_state in (WebSocketState.CLOSED, WebSocketState.DISCONNECTED):
                            print("Worker: Detected cancel or disconnect in monitor, stopping executor")
                            await executor.stop()
                            break

                monitor_task = asyncio.create_task(monitor_cancel())

                try:
                    print("Worker: Starting stream loop")
                    while True:
                        try:
                            results = await anext(stream_generator)
                            print(f"Worker: Got stream result: {list(results.keys())}")
                        except StopAsyncIteration:
                            print("Worker: Stream generator exhausted (StopAsyncIteration)")
                            break
                        except Exception as e:
                            print(f"Worker: Unexpected exception in stream: {e}")
                            raise
                        try:
                            await websocket.send_json({"type": "data", "results": _serialize_results(results), "stream": True})
                        except Exception:
                            print("Worker: Exception sending stream data, stopping executor")
                            await executor.stop()
                            break
                finally:
                    monitor_task.cancel()
                    try:
                        print("Worker: Stream finished, sending final status")
                        await websocket.send_json({"type": "status", "message": "Stream finished"})
                    except Exception:
                        pass
            else:
                try:
                    await websocket.send_json({"type": "status", "message": "Executing batch"})
                except Exception:
                    pass
                results = await executor.execute()
                try:
                    await websocket.send_json({"type": "data", "results": _serialize_results(results)})
                    await websocket.send_json({"type": "status", "message": "Batch finished"})
                except Exception:
                    pass

        except WebSocketDisconnect:
            if executor and executor.is_streaming:
                try:
                    await executor.stop()
                except Exception:
                    pass
        except Exception as e:
            try:
                await websocket.send_json({"type": "error", "message": str(e)})
            except Exception:
                pass
        finally:
            try:
                if websocket.client_state not in (WebSocketState.DISCONNECTED, WebSocketState.CLOSED):
                    await websocket.close()
            except Exception:
                pass
            job.done_event.set()
            await EXECUTION_QUEUE.mark_done(job)


@app.on_event("startup")
async def _startup_queue_worker():
    # Only start worker tasks if not in testing mode
    import os
    if os.getenv("PYTEST_CURRENT_TEST") is None:
        task = asyncio.create_task(_execution_worker())
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
                None
            )
        }
    return {"nodes": nodes_meta}

@app.websocket("/execute")
async def execute_endpoint(websocket: WebSocket):
    await websocket.accept()
    job = None
    try:
        graph_data = await websocket.receive_json()
        
        # If no background worker is running (testing mode), execute directly
        import os
        pytest_test = os.getenv("PYTEST_CURRENT_TEST")
        print(f"Server: PYTEST_CURRENT_TEST = {pytest_test}")
        if pytest_test is not None:
            print("Server: Using direct execution (testing mode)")
            await _execute_job_directly(websocket, graph_data)
        else:
            print("Server: Using queued execution (production mode)")
            await websocket.send_json({"type": "status", "message": "Waiting for available slot..."})
            job = await EXECUTION_QUEUE.enqueue(websocket, graph_data)
            await job.done_event.wait()
    except WebSocketDisconnect:
        print("Client disconnected.")
        if job is not None:
            job.cancel_event.set()
    except Exception as e:
        try:
            await websocket.send_json({"type": "error", "message": str(e)})
        except Exception:
            pass
    finally:
        pass


async def _execute_job_directly(websocket: WebSocket, graph_data: Dict[str, Any]):
    """Execute job directly without queue (for testing)"""
    executor: typing.Optional[GraphExecutor] = None
    try:
        print("Server: Creating GraphExecutor")
        executor = GraphExecutor(graph_data, NODE_REGISTRY)
        print(f"Server: GraphExecutor created, is_streaming={executor.is_streaming}")
        await websocket.send_json({"type": "status", "message": "Starting execution"})

        if executor.is_streaming:
            print("Server: Executing streaming path")
            await websocket.send_json({"type": "status", "message": "Stream starting..."})
            stream_generator = executor.stream()
            try:
                print("Server: Getting initial results from stream generator")
                initial_results = await anext(stream_generator)
                print(f"Server: Got initial results: {list(initial_results.keys())}")
            except StopAsyncIteration:
                print("Server: Stream generator exhausted on first anext()")
                initial_results = {}
            await websocket.send_json({"type": "data", "results": _serialize_results(initial_results), "stream": False})

            async def monitor_cancel():
                while True:
                    await asyncio.sleep(0.5)
                    if websocket.client_state in (WebSocketState.CLOSED, WebSocketState.DISCONNECTED):
                        print("Server: Detected disconnect in monitor, stopping executor")
                        await executor.stop()
                        break

            monitor_task = asyncio.create_task(monitor_cancel())

            stream_finished_normally = True
            try:
                print("Server: Starting stream loop")
                while True:
                    try:
                        results = await anext(stream_generator)
                        print(f"Server: Got stream result: {list(results.keys())}")
                    except StopAsyncIteration:
                        print("Server: Stream generator exhausted (StopAsyncIteration)")
                        break
                    except Exception as e:
                        print(f"Server: Stream error: {e}")
                        stream_finished_normally = False
                        await websocket.send_json({"type": "error", "message": str(e)})
                        return
                    await websocket.send_json({"type": "data", "results": _serialize_results(results), "stream": True})
            finally:
                monitor_task.cancel()
                if stream_finished_normally:
                    print("Server: Stream finished normally")
                    await websocket.send_json({"type": "status", "message": "Stream finished"})
        else:
            await websocket.send_json({"type": "status", "message": "Executing batch"})
            results = await executor.execute()
            await websocket.send_json({"type": "data", "results": _serialize_results(results)})
            await websocket.send_json({"type": "status", "message": "Batch finished"})

    except Exception as e:
        await websocket.send_json({"type": "error", "message": str(e)})

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
