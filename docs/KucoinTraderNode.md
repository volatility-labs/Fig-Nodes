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

## Notes
- Symbol mapping: `TICKER-USDT` (e.g., `BTC-USDT`).
- Sizing: uses `risk_per_trade_usd` and latest price to compute base size.
- Duplicate protection: the node skips re-buying the same symbol within the current process/session.
- TP/SL: values are included in the result payload for external management; the node does not place follow-up TP/SL orders.


