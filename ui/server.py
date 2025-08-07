import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from fastapi import FastAPI, Body
from typing import Dict, Any, List
from core.graph_executor import GraphExecutor
from nodes.base_node import BaseNode
import importlib.util
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from core.node_registry import NODE_REGISTRY

app = FastAPI()

# Serve Vite's build output
app.mount("/static", StaticFiles(directory=os.path.join(os.path.dirname(__file__), "static/dist")), name="static")

@app.get("/")
def read_root():
    return FileResponse(os.path.join(os.path.dirname(__file__), "static/dist", "index.html"))

@app.get("/nodes")
def list_nodes():
    nodes_meta = {}
    for name, cls in NODE_REGISTRY.items():
        inputs_meta = cls.inputs if isinstance(cls.inputs, list) else {k: v.__name__ for k, v in cls.inputs.items()}
        outputs_meta = cls.outputs if isinstance(cls.outputs, list) else {k: v.__name__ for k, v in cls.outputs.items()}
        nodes_meta[name] = {
            "inputs": inputs_meta,
            "outputs": outputs_meta,
            "params": list(cls.default_params.keys()),
            "category": "data_source" if "Universe" in name or "Data" in name else "logic",
            "uiModule": "LoggingNodeUI" if name == "LoggingNode" else None
        }
    return {"nodes": nodes_meta}

@app.post("/execute")
async def execute_graph(graph: Dict[str, Any] = Body(...)):
    executor = GraphExecutor(graph, NODE_REGISTRY)
    results = await executor.execute()
    return {"results": results}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000) 