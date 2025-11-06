# DuplicateSymbolFilter — usage guide

This node handles BOTH single-feed deduplication and two-feed comparisons in one place.

## Inputs
- `ohlcv_bundle` (optional): Use for single-feed/global dedupe.
- `left_bundle` (optional): Feed A for pairwise set operations.
- `right_bundle` (optional): Feed B for pairwise set operations.

Only connect what you need:
- Single-feed: connect `ohlcv_bundle` only.
- Two-feed: connect `left_bundle` and `right_bundle` (leave `ohlcv_bundle` disconnected).

## Output
- `filtered_ohlcv_bundle`: The filtered OHLCV bundle to pass downstream (e.g., into `ExtractSymbols` → `Logging`/`Discord`).

## Parameters
- `pair_mode`:
  - `global` (default): Use single-feed/global mode (uses `ohlcv_bundle`).
  - `intersection_1_2`: Keep symbols present in BOTH `left_bundle` and `right_bundle`.
  - `left_only_1_minus_2`: Keep symbols present in `left_bundle` but NOT in `right_bundle` (A − B).
  - `right_only_2_minus_1`: Keep symbols present in `right_bundle` but NOT in `left_bundle` (B − A).

- `mode` (single-feed only; ignored in pairwise):
  - `unique`: Keep the first occurrence per symbol key.
  - `duplicates_only`: Keep only items whose symbol key appears more than once.

- `compare_by`:
  - `ticker`: Compare on base ticker (recommended for crypto pairs sharing the same quote, e.g., USD).
  - `symbol_string`: Compare on the full symbol string (e.g., exchange-qualified).

- `case_insensitive`: true/false (recommended: true).

## Common recipes
1) Show duplicates BETWEEN two feeds (e.g., overlap)
   - Connect: `left_bundle` ← Feed A, `right_bundle` ← Feed B
   - Set: `pair_mode = intersection_1_2`
   - `compare_by = ticker`, `case_insensitive = true`
   - Wire: `filtered_ohlcv_bundle` → `ExtractSymbols.ohlcv_bundle` → `Logging.input`

2) Show symbols only in A and not in B
   - Connect: `left_bundle` ← A, `right_bundle` ← B
   - Set: `pair_mode = left_only_1_minus_2`

3) Deduplicate WITHIN one feed (keep only unique by first occurrence)
   - Connect: `ohlcv_bundle` ← Feed
   - Set: `pair_mode = global`, `mode = unique`

4) Keep only duplicates WITHIN one merged feed
   - If you merged multiple sources upstream into one `ohlcv_bundle`,
   - Set: `pair_mode = global`, `mode = duplicates_only`

## Notes
- In pairwise modes, `mode` is ignored. Only `pair_mode` controls the operation.
- Intersection returns the instances from `left_bundle` when matches are found.
- If your two feeds use different quote currencies or naming, try `compare_by = symbol_string`.


