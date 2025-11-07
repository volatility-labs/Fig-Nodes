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
- `amount`: numeric amount per symbol (as per mode) — fallback when `risk_per_trade_usd` is 0
- `risk_per_trade_usd`: overrides `amount` and forces quote mode (mirrors "Risk per trade in USD")
- `default_quote_currency`: used when symbol lacks a quote (default: USDT)
- `convert_usd_to_usdt`: if true, USD is mapped to USDT
- `dry_run`: if true, simulate only (no orders sent)
- `concurrency`: max simultaneous order submissions (overridden by `max_concurrent_positions` if set)
- `max_concurrent_positions`: ICP-bot style "Maximum concurrent positions"
- `enable_bracket`: if true (and side=buy), submit TP/SL after market entry (spot only)
- `take_profit_percent`: TP distance in percent from entry (e.g., 3.0)
- `stop_loss_percent`: SL distance in percent (e.g., 1.5) when `sl_from = entry`
- `sl_from`: entry | liquidation (compute SL from entry or from a provided liquidation reference)
- `liquidation_price`: optional numeric reference used when `sl_from = liquidation`
- `sl_buffer_percent_above_liquidation`: when `sl_from = liquidation`, place SL at `liq * (1 + buffer%)` (else falls back to entry/liquidation mix)
- `leverage`: desired leverage (informational for spot; used when futures support is enabled)

## Notes
- Symbol mapping used: `TICKER-QUOTE`, e.g., `BTC-USDT`.
- In quote mode, the node fetches ticker price via CCXT to compute base size.
- Errors per symbol are returned in `orders` for inspection.
- Brackets: Kucoin spot TP is placed as a limit sell; SL is placed as a conditional stop-market sell. If exchange rejects the conditional format, the node returns a `bracket_error` but the entry may still be placed.


