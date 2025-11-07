# KucoinTraderNode — usage guide

Places market buy orders on Kucoin for a list of crypto symbols (Fig-Nodes → Kucoin).

## Requirements
- Env vars set (via Settings → API Keys or .env):
  - `KUCOIN_API_KEY`
  - `KUCOIN_API_SECRET`
  - `KUCOIN_API_PASSPHRASE`
- CCXT installed if you intend to place live orders (dry_run does not need it).

## Wiring
- Input `symbols` expects `AssetSymbolList` (e.g., from `ExtractSymbols.symbols`).
- Output `orders` contains per-symbol results.

Typical chain:
- DuplicateSymbolFilter → ExtractSymbols → KucoinTraderNode → Logging

## Parameters (minimal, ICP-bot style)
- `risk_per_trade_usd`: Risk per trade in USD (quote sizing)
- `sl_buffer_percent_above_liquidation`: Stop-loss buffer % above liquidation (if applicable)
- `take_profit_percent`: Take-profit %
- `leverage`: Desired leverage (informational until futures mode is enabled)
- `max_concurrent_positions`: Maximum concurrent positions (also caps concurrency)
- `allow_scaling`: Permit additional entries for the same symbol
- `max_scale_entries`: Max number of entries per symbol (including the first)
- `scale_cooldown_s`: Minimum seconds between scale entries per symbol
- `persist_state`: Save scale counters and timestamps across restarts
- `state_path`: File to store state when `persist_state` is true (default `results/kucoin_trader_state.json`)

## Notes
- Symbol mapping: `TICKER-USDT` (e.g., `BTC-USDT`).
- Sizing: uses `risk_per_trade_usd` and latest price to compute base size.
- Duplicate protection / scaling:
  - If `allow_scaling` = false: skip any re-buy for symbols already entered this session/state.
  - If `allow_scaling` = true: enforce `max_scale_entries` and `scale_cooldown_s` per symbol.
- TP/SL: values are included in the result payload for external management; the node does not place follow-up TP/SL orders.


