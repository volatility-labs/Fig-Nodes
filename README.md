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


## Hardware Requirements

Minimum 16gb of VRAM on either a dedicated GPU or shared memory (Apple M series)

## License
Fig Nodes is licensed under the Apache License 2.0. See [LICENSE](LICENSE) for details.
