# Fig Nodes (Beta)

Fig Nodes makes it easy to build agentic finance and trading workflows.  

1. Intuitive plug and play UI to build asset universe scanning, trading, visualization, position management, and data services logic. 
2. Modular node design allowing any developer to build new nodes with custom logic with plug and play architecture. 
3. Lightweight design.

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

### Node guide: DuplicateSymbolFilter
- See docs/DuplicateSymbolFilter.md for how to do single-feed dedupe and two-feed comparisons (intersection, A−B, B−A) in one node.

## (Optional) Setup Ollama

For local LLM inference nodes, Fig Nodes *require* a local Ollama installation. Please see [Ollama installation instructions here](https://github.com/ollama/ollama).

After installing Ollama on your local computer, download models by

```bash
ollama pull qwen3:8b
```

You can find a library of all the models supported by Ollama [here](https://ollama.com/library).

For optimal results, consider the model size vs your local machine's available VRAM and GPU. 


## Testing

To run the unit tests:

```bash
uv run pytest tests/unit/
``` 

## Recurring execution (schedule a saved graph)

You can run a saved workflow JSON on a fixed cadence using the recurring runner script:

```bash
uv run python scripts/recurring_runner.py --graph "/path/to/your-graph.json" --interval 5m
```

Supported intervals: `5m`, `15m`, `30m`, `1h`, `1d`. Optional: `--runs N` to limit runs (default infinite). Make sure the backend is running (e.g., `uv run python main.py --dev`).

## TODO
- Canvas grouping square for visual grouping of nodes on canvas
- OHLCV charting nodes

## License
Fig Nodes is licensed under the Apache License 2.0. See [LICENSE](LICENSE) for details.
