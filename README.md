# Hello world.

## Setup and Running with Poetry

1. Install dependencies: `poetry install`
2. Activate virtual environment: `poetry shell`
3. Run the bot: `python main.py`
4. Run tests: `pytest tests/`

Alternatively, run directly with `poetry run python main.py` or `poetry run pytest tests/`. 

## Creating Custom Nodes and Plugins

To extend the bot with custom nodes:
1. Create a new .py file in `plugins/` (or subclass in `nodes/` for core).
2. Define a class subclassing `BaseNode` from `nodes.base_node`.
3. Implement `inputs`, `outputs`, and `execute` method.
4. Optionally, add params in `__init__`.

Example (`plugins/custom.py`):
```python
from nodes.base_node import BaseNode
from typing import Dict, Any, List

class CustomNode(BaseNode):
    @property
    def inputs(self) -> List[str]:
        return ['in']
    @property
    def outputs(self) -> List[str]:
        return ['out']
    def execute(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        return {'out': inputs['in'] + '_transformed'}
```
The node will auto-register on startup.

## Deployment

Build and run with Docker:
```bash
docker build -t hl-bot .
docker run -d -p 8000:8000 hl-bot
```
Access UI at http://localhost:8000/static/index.html 

## Using the UI Features
- **Saving and Loading Graphs**: Use the "Save Graph" and "Load Graph" buttons to store and retrieve workflows in local storage.
- **Right Menu Bar**: Lists available nodes; click "Add" or drag to canvas to add.
- **Canvas Drag and Drop**: Drag nodes around, connect outputs to inputs.
- **Editable Node Inputs**: Click text boxes on nodes to edit parameters.
- **Executing the Graph**: Click "Execute Graph" to send to backend; check console for results. 
- **Context Menus**: Right-click on a node for options like Clone, Remove, Properties. Right-click on the canvas background to access a menu for adding nodes by category. 
