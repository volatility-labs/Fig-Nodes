import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from fastapi import FastAPI, Body
from typing import Dict, Any, List
from ui.graph_executor import GraphExecutor
from nodes.base_node import BaseNode
import importlib.util
from fastapi.staticfiles import StaticFiles

from ui.node_registry import NODE_REGISTRY  # Import the registry

app = FastAPI()

app.mount("/static", StaticFiles(directory=os.path.join(os.path.dirname(__file__), "static")), name="static")

@app.get("/")
def read_root():
    return {"message": "Hello from the Trading Bot UI Backend"}

@app.get("/nodes")
def list_nodes():
    return {"nodes": list(NODE_REGISTRY.keys())}

@app.post("/execute")
def execute_graph(graph: Dict[str, Any] = Body(...)):
    executor = GraphExecutor(graph, NODE_REGISTRY)
    results = executor.execute()
    return {"results": results}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000) 