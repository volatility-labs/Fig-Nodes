import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from fastapi import FastAPI, Body
from typing import Dict, Any, List
from ui.graph_executor import GraphExecutor
from nodes.base_node import BaseNode
import importlib.util
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from ui.node_registry import NODE_REGISTRY

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
        instance = cls("dummy", {})  # Dummy instance to get properties
        nodes_meta[name] = {
            "inputs": instance.inputs,
            "outputs": instance.outputs,
            "params": list(cls.default_params.keys())
        }
    return {"nodes": nodes_meta}

@app.post("/execute")
def execute_graph(graph: Dict[str, Any] = Body(...)):
    executor = GraphExecutor(graph, NODE_REGISTRY)
    results = executor.execute()
    return {"results": results}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000) 