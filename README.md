# Fig Nodes (Beta)

Fig Nodes makes it easy to build agentic finance and trading workflows.  

1. Integrated Node UI + editor to build asset universe scanning, trading, visualization, position management, and data services logic. 
2. Plug and play node design with custom extensibility
3. Blazing fast with rustworkx network supporting graphs with 10k+ nodes

Created by Volatility Labs Inc. 

## Run Fig Node

Requires Python 3.11 or later.

After Ollama has been installed and models are downloaded, set up a virtual environment using uv.

```bash
# (macOS) Install uv if not already installed
brew install uv

# Create a virtual environment (creates .venv)
uv venv
# optional: choose a specific Python version
# uv venv --python 3.12

# Activate the venv (optional; uv can also run without activation)
source .venv/bin/activate

# Install project dependencies
uv sync
# include dev dependencies (tests, etc.)
uv sync --group dev
```

## Quick Start

Then start the development local server:

```bash
uv run python main.py --dev
```

The default graph should load. Press `Execute` at the bottom right of the canvas. 

## Litegraph

The code base runs in a forked version of [ComfyOrg's Litegraph](https://github.com/Comfy-Org/litegraph.js) in the frontend directory. 

## Testing

To run the unit tests:

```bash
uv run pytest tests/unit/
``` 
## License
Fig Nodes is licensed under the Apache License 2.0. See [LICENSE](LICENSE) for details.
