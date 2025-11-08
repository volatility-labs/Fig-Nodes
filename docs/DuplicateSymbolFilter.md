# DuplicateSymbolFilter — usage guide

This node handles single-feed deduplication and multi-feed comparisons (up to 3 inputs) in one place.

## Inputs
- `ohlcv_bundle` (optional): Use for single-feed/global dedupe.
- `input_1` (optional): First input for multi-input set operations.
- `input_2` (optional): Second input for multi-input set operations.
- `input_3` (optional): Third input for multi-input set operations.

Only connect what you need:
- Single-feed: connect `ohlcv_bundle` only.
- Multi-feed: connect any combination of `input_1`, `input_2`, and/or `input_3` (leave `ohlcv_bundle` disconnected).

## Output
- `filtered_ohlcv_bundle`: The filtered OHLCV bundle to pass downstream (e.g., into `ExtractSymbols` → `Logging`/`Discord`).

## Parameters
- `pair_mode`:
  - `global` (default): Use single-feed/global mode (uses `ohlcv_bundle`).
  - `intersection_1_2`: Keep symbols present in BOTH `input_1` and `input_2`.
  - `intersection_1_2_3`: Keep symbols present in ALL three inputs (`input_1`, `input_2`, and `input_3`).
  - `only_1_minus_2`: Keep symbols present in `input_1` but NOT in `input_2`.
  - `only_2_minus_1`: Keep symbols present in `input_2` but NOT in `input_1`.
  - `only_3_minus_1_2`: Keep symbols present in `input_3` but NOT in `input_1` or `input_2`.
  - `union_1_2_minus_3`: Keep symbols present in `input_1` OR `input_2` but NOT in `input_3`.

- `mode` (single-feed only; ignored in pairwise):
  - `unique`: Keep the first occurrence per symbol key.
  - `duplicates_only`: Keep only items whose symbol key appears more than once.

- `compare_by`:
  - `ticker`: Compare on base ticker (recommended for crypto pairs sharing the same quote, e.g., USD).
  - `symbol_string`: Compare on the full symbol string (e.g., exchange-qualified).

- `case_insensitive`: true/false (recommended: true).

## Common recipes
1) Show duplicates BETWEEN two feeds (e.g., overlap)
   - Connect: `input_1` ← Feed A, `input_2` ← Feed B
   - Set: `pair_mode = intersection_1_2`
   - `compare_by = ticker`, `case_insensitive = true`
   - Wire: `filtered_ohlcv_bundle` → `ExtractSymbols.ohlcv_bundle` → `Logging.input`

2) Show symbols only in A and not in B
   - Connect: `input_1` ← A, `input_2` ← B
   - Set: `pair_mode = only_1_minus_2`

3) Show symbols present in all three feeds
   - Connect: `input_1` ← Feed A, `input_2` ← Feed B, `input_3` ← Feed C
   - Set: `pair_mode = intersection_1_2_3`

4) Show symbols in C but not in A or B
   - Connect: `input_1` ← A, `input_2` ← B, `input_3` ← C
   - Set: `pair_mode = only_3_minus_1_2`

5) Show symbols in A or B but not in C
   - Connect: `input_1` ← A, `input_2` ← B, `input_3` ← C
   - Set: `pair_mode = union_1_2_minus_3`

6) Deduplicate WITHIN one feed (keep only unique by first occurrence)
   - Connect: `ohlcv_bundle` ← Feed
   - Set: `pair_mode = global`, `mode = unique`

7) Keep only duplicates WITHIN one merged feed
   - If you merged multiple sources upstream into one `ohlcv_bundle`,
   - Set: `pair_mode = global`, `mode = duplicates_only`

## Notes
- In multi-input modes, `mode` is ignored. Only `pair_mode` controls the operation.
- Intersection operations return the instances from `input_1` when matches are found.
- All inputs are optional - connect only what you need for your specific use case.
- If your two feeds use different quote currencies or naming, try `compare_by = symbol_string`.


