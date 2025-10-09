# Fig Nodes (Beta)

Fig Nodes makes it easy to build agentic finance and trading workflows.  

1. Intuitive plug and play UI to build asset universe scanning, trading, visualization, position management, and data services logic. 
2. Modular node design allowing any developer to build new nodes with custom logic with plug and play architecture. 
3. Lightweight design.

Created by Volatility Labs Inc. 

## Setup Ollama

For local LLM inference nodes, Fig Nodes *require* a local Ollama installation. Please see [Ollama installation instructions here](https://github.com/ollama/ollama).

After installing Ollama on your local computer, download models by

```bash
ollama pull qwen3:8b
ollama pull mistral
ollama pull phi3
```

You can find a library of all the models supported by Ollama [here](https://ollama.com/library).

For optimal results, consider the model size vs your local machine's available VRAM and GPU. 

## Run Fig Node

Requires Python 3.11 or later.

After Ollama has been installed and models are downloaded, create a virtual environment to avoid dependency conflicts with your system Python installation.

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

## Quick Start

Then start the development local server:

```bash
python main.py --dev
```

The default graph should load. Press `Execute` at the bottom right of the canvas. 

## Testing

To run the unit tests:

```bash
pytest tests/unit/
``` 

## Changelog
Oct 8, 2025
  - Added ATRX filtering and calculation nodes
  - Various bug fixes and minor improvements and code refactoring for better maintainability
  - Fixed a bug in which logging node is not displaying the text due to bug in saving output
  - Added SMA_n > sma_n (x-days ago) indicator filter
  - Added ATR filtering and indicator calculation nodes

- Oct 7, 2025
  - Enhanced Polygon Universe node to allow for filtering of tickers based on volume, price change and other 1d OHLCV bar
  - Enhanced Ollama Chat node to remove redundant tools/tool nodes
  - Added system process kill for inprogress Ollama Chat nodes that causes memory overflows
  - Simplified LLM Message Builder node to build standard LLM messages only without additional system messages etc
  - Additional bug fixes

- Oct 5, 2025
  - Added base indicator calculation, indicator filter nodes
  - Refactored `type_registry.py` for better maintainability by consolidating type aliases
  - Added additional types in `types_registry.py` for `IndicatorResult`, and `MuliAssetIndicatorResult` for filtering
  - Various bug fixes
  - Added additional unit tests

- Oct 4, 2025
  - Added CI workflow to run unit tests for both front and backend upon push / merge
  - Removed streaming mode from Ollama Chat Node 

- Oct 3, 2025
  - Added "New" button on the canvas bottom menu bar to create new blank graph
  - Added auto-save feature in which an unsaved graph is saved in browser local storage every 2 seconds to preserve workflow continuity on accidental refreshes
  - Removed `ollama_model_selector` node. Added the model selector node params to `ollama_chat_node`
  - General bug fixes
  - Backend server tests pass

- Oct 2, 2025:
  - Initial internal beta release of Fig Node
  - Added default graph upon initial dev server start up
  - Added deterministic type color mapping and override system for node types
  - Implemented frontend type string construction for complex/nested types
  - Improved process management for dev server (graceful shutdown, error handling)

Fig nodes is under **beta**. 

## Hardware Requirements

Minimum 16gb of VRAM on either a dedicated GPU or shared memory (Apple M series)

## License
Fig Nodes is licensed under the Apache License 2.0. See [LICENSE](LICENSE) for details.
