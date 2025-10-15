
##  Changelog
Oct 15, 2025
  - Refactoring of backend `base_node.py`. Added pydantic type validation. Added uniform error handling at the class level, and improved overall code maintainability and robustness.
  - Added Link Mode on node UI for custom aesthetic choices

Oct 12, 2025
  - Consolidated API key management via UI interface - API Key Vault that abstracts management of api keys required by graphs via .env file IO
  - Removed various API key nodes - consolidated all API key management via `api_key_vault.py`
  - Added .env.example 

Oct 10, 2025
  - Bug fixes and minor improvements
  - Fixed Polygon universe node to allow for both positive % change as well as negative % change scans
  - Added ORB filtering node based on opening range calculations. [Link](https://www.sfi.ch/en/publications/n-24-98-a-profitable-day-trading-strategy-for-the-u.s.-equity-market)
  - Added progress check on all indicator filtering node base
  - Added Lod distance indicator filter node for measuring current price vs ATR range over last n bars

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