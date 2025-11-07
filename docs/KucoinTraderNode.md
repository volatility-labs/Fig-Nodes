# KucoinTraderNode — usage guide

Places spot market orders on Kucoin for a list of crypto symbols.

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

## Parameters
- `side`: buy | sell (default: buy)
- `order_amount_mode`: quote | base
  - quote: spend a fixed quote amount; node fetches last price to compute base size
  - base: submit a fixed base quantity
- `amount`: numeric amount per symbol (as per mode)
- `default_quote_currency`: used when symbol lacks a quote (default: USDT)
- `convert_usd_to_usdt`: if true, USD is mapped to USDT
- `dry_run`: if true, simulate only (no orders sent)
- `concurrency`: max simultaneous order submissions

## Notes
- Symbol mapping used: `TICKER-QUOTE`, e.g., `BTC-USDT`.
- In quote mode, the node fetches ticker price via CCXT to compute base size.
- Errors per symbol are returned in `orders` for inspection.


