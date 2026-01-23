# Fig Nodes (Beta)
Noded based workflow tool for traders to 

- Scan markets
- Research into ideas
- LLM integration for trading, filtering or reasoning decisions
- and more

## Examples 

(Example workflows will be posted here)


## Installation

Requires Python 3.11 or later. The repo runs on your local computer. 

Git clone the repo first

```bash
git clone https://github.com/volatility-labs/Fig-Nodes.git
```
Then install uv if not installed already:

```bash
# use brew
brew install uv

# or use pip
pip install uv

# setup venv
uv venv
source .venv/bin/activate

# install dependencies 
uv sync
uv sync --group dev
```
Then start the development local server:

```bash
uv run python main.py --dev
```

The default graph should load. Press `Execute` at the bottom right of the canvas. 

## Litegraph

The code base runs in a forked version of [ComfyOrg's Litegraph](https://github.com/Comfy-Org/litegraph.js) in the frontend directory. 




``` 
## License
Fig Nodes is licensed under the Apache License 2.0. See [LICENSE](LICENSE) for details.
