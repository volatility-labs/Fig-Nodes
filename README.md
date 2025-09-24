# Fig Nodes

Inspired by ComfyUI for AI and litegraph, Fig Nodes makes it easy to build professional grade trading bots with node based UI.

1. Intuitive plug and play UI to build asset universe scanning, trading, visualization, position management, and data services logic. 
2. Modular node design allowing any developer to build new nodes with custom logic with plug and play architecture. 
3. Lightweight design.

Created by Volatility Labs Inc. 

## Setup (pip + venv)

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements-dev.txt
```

## Testing

To run the unit tests:

```bash
pytest tests/unit/
``` 