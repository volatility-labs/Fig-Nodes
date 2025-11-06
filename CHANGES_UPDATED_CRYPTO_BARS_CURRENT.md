# Updated Crypto Bars: Changes Summary

This branch/repo contains updates to fetch fresher crypto OHLCV bars from Massive (formerly Polygon).

Key changes
- Crypto snapshots: switch to single-ticker endpoint with apiKey query auth
  - File: `services/polygon_snapshot_service.py`
  - Endpoint used: `/v2/snapshot/locale/global/markets/crypto/tickers/X:<TICKER>`
- Aggregates: use millisecond timestamps up to "now"
  - File: `services/polygon_service.py`
  - Example: `/v2/aggs/ticker/X:BTCUSD/range/{multiplier}/{timespan}/{from_ms}/{to_ms}?apiKey=...`
- Crypto treated as 24/7 open when computing data status.
- Modest retry and higher timeout to reduce transient connect timeouts.
- Improved typing to satisfy linter; no new lints introduced.

Why this fixes delays
- Massive’s real-time availability is plan-gated. If your API key has real-time (Currencies Starter/Business), the aggregates endpoint returns up-to-date minute bars. We now request through current time using ms timestamps; otherwise we synthesize a current bar via snapshot.
- Snapshot fallback now reliably targets the exact ticker instead of scanning paginated lists.

Docs reference
- Massive Custom Bars (OHLC): `https://massive.com/docs/rest/crypto/aggregates/custom-bars`

Files changed (high level)
- `services/polygon_service.py`
  - from/to converted to ms timestamps
  - crypto market considered always open
  - small retry around `httpx` GET and increased timeout
  - safer parsing/typing of results
- `services/polygon_snapshot_service.py`
  - single-ticker crypto snapshot with `apiKey` query param
  - robust parsing and typing

Notes
- If you still observe delayed aggregates, verify your plan’s recency. Snapshot fallback provides a synthetic “current” bar (OHLC = current price, volume = 0) to maintain freshness in UIs/strategies.
