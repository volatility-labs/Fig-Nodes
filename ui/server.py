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

app = FastAPI()

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
            "uiModule": getattr(cls, 'ui_module', None) or ("TextInputNodeUI" if name == "TextInputNode" else "LoggingNodeUI" if name == "LoggingNode" else None)
        }
    return {"nodes": nodes_meta}

@app.websocket("/execute")
async def execute_endpoint(websocket: WebSocket):
    await websocket.accept()
    try:
        graph_data = await websocket.receive_json()
        executor = GraphExecutor(graph_data, NODE_REGISTRY)

        def serialize_value(v):
            if isinstance(v, list):
                return [serialize_value(item) for item in v]
            if isinstance(v, dict):
                return {str(key): serialize_value(val) for key, val in v.items()}  # Convert keys to str
            if hasattr(v, 'to_dict'):
                return v.to_dict()
            if isinstance(v, pd.DataFrame):
                return v.to_dict(orient='records')
            return str(v)  # Fallback

        def serialize_results(results):
            return {str(node_id): {out: serialize_value(val) for out, val in node_res.items()} for node_id, node_res in results.items()}

        if executor.is_streaming:
            # Handle long-running streaming execution
            await websocket.send_json({"type": "status", "message": "Stream starting..."})
            stream_generator = executor.stream()
            
            # Send the first chunk of (potentially empty) initial results
            initial_results = await anext(stream_generator)
            await websocket.send_json({"type": "data", "results": serialize_results(initial_results)})
            
            async for results in stream_generator:
                await websocket.send_json({"type": "data", "results": serialize_results(results)})
            
            await websocket.send_json({"type": "status", "message": "Stream finished"})
        else:
            # Handle short-lived batch execution
            await websocket.send_json({"type": "status", "message": "Executing batch"})
            results = await executor.execute()
            await websocket.send_json({"type": "data", "results": serialize_results(results)})
            await websocket.send_json({"type": "status", "message": "Batch finished"})

    except WebSocketDisconnect:
        print("Client disconnected.")
        if 'executor' in locals() and executor.is_streaming:
            await executor.stop()
    except Exception as e:
        await websocket.send_json({"type": "error", "message": str(e)})
    finally:
        await websocket.close()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
