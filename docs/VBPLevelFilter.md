# VBP Level Filter

## Overview

The VBP Level Filter is a technical indicator filter that identifies significant support and resistance levels based on volume profile analysis. It filters assets based on their current price's proximity to these volume-based price levels.

## Installation

The VBP Level Filter is part of the Fig Nodes platform. Ensure you have:
- Python 3.11 or later
- Fig Nodes installed and configured
- Polygon API key configured in your environment

### Getting the Node

To use the VBP Level Filter, pull the branch containing the implementation:

```bash
git fetch origin
git checkout feature/vbp-level-filter-docs
```

The node files are already included:
- Backend: `nodes/core/market/filters/vbp_level_filter_node.py`
- Frontend: `ui/static/nodes/market/VBPLevelFilterNodeUI.ts`
- Registry: Automatically registered via the node registry system

## Node Information

### Node Class
```python
VBPLevelFilter
```

### Location
- **Backend**: `nodes/core/market/filters/vbp_level_filter_node.py`
- **Frontend UI**: `ui/static/nodes/market/VBPLevelFilterNodeUI.ts`

### Inputs
- `ohlcv_bundle`: Dictionary mapping `AssetSymbol` to list of `OHLCVBar` objects

### Outputs
- `filtered_ohlcv_bundle`: Dictionary containing only symbols that passed the filter

### Base Class
```python
from nodes.core.market.filters.base.base_indicator_filter_node import BaseIndicatorFilter
```

## What is Volume Profile?

Volume Profile (VBP) analyzes the distribution of trading volume across different price levels over a historical period. By identifying price levels where significant trading activity occurred, we can determine areas of:
- **Support**: Price levels where buying was concentrated (potential price floors)
- **Resistance**: Price levels where selling was concentrated (potential price ceilings)

## How the Filter Works

### 1. Data Collection
- Fetches historical OHLCV data for the specified lookback period
- Can use either:
  - **Daily bars** aggregated to weekly (default)
  - **Weekly bars** fetched directly from Polygon API (when `use_weekly=True`)

### 2. Volume Profile Calculation
- Divides the price range into bins (configurable via `bins` parameter)
- For each bar, calculates `volume_usd = volume × close` 
- Groups volume by closing price using histogram binning
- Identifies the top N most significant volume levels (configurable via `num_levels`)

### 3. Support/Resistance Identification
- **Support levels**: Volume peaks below the current price
- **Resistance levels**: Volume peaks above the current price
- Finds the closest support and resistance levels to the current price

### 4. Distance Calculation
- **Distance to Support**: `|current_price - closest_support| / current_price × 100`
- **Distance to Resistance**: `|closest_resistance - current_price| / current_price × 100`

### 5. Filter Logic
The filter passes an asset if:
1. **Within max distance to support**: Current price is within X% of the nearest support level
2. **At least min distance to resistance**: Current price is at least Y% away from the nearest resistance level
3. **Above all levels**: If price is above all identified resistance levels, automatically passes (regardless of resistance distance threshold)

## Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `bins` | number | 50 | Number of bins for volume histogram (10-200) |
| `lookback_years` | number | 2 | Number of years to look back for volume data (1-10) |
| `num_levels` | number | 5 | Number of significant volume levels to identify (1-20) |
| `max_distance_to_support` | number | 5.0 | Maximum % distance to nearest support level (0-50%) |
| `min_distance_to_resistance` | number | 5.0 | Minimum % distance to nearest resistance level (0-50%) |
| `use_weekly` | boolean | false | If true, fetch weekly bars from Polygon. If false, aggregate daily bars to weekly |

## Example Use Cases

### Finding Breakout Setups
```python
params = {
    "bins": 50,
    "lookback_years": 2,
    "num_levels": 5,
    "max_distance_to_support": 3.0,  # Close to support
    "min_distance_to_resistance": 10.0,  # Plenty of room to resistance
    "use_weekly": True
}
```
**Result**: Filters for stocks near support with significant upside to resistance

### Finding Oversold Conditions
```python
params = {
    "bins": 100,
    "lookback_years": 1,
    "num_levels": 3,
    "max_distance_to_support": 1.0,  # Very close to support
    "min_distance_to_resistance": 5.0,
    "use_weekly": False
}
```
**Result**: Filters for stocks that have fallen close to significant support levels

### Finding Strong Uptrends
```python
params = {
    "bins": 50,
    "lookback_years": 2,
    "num_levels": 5,
    "max_distance_to_support": 10.0,
    "min_distance_to_resistance": 5.0,
    "use_weekly": True
}
```
**Result**: Filters for stocks that are well above support and clear of resistance

## Technical Details

### Calculation Method
The filter uses the same methodology as traditional volume profile analysis:
1. Create price bins using the range: `price_min` to `price_max`
2. Bin size: `(price_max - price_min) / bins`
3. For each bar, assign volume to bin based on closing price
4. Sum volume_usd (volume × close) for each bin
5. Identify significant levels using highest volume bins

### Weekly Data Aggregation
When `use_weekly=False`, daily bars are aggregated to weekly using:
- **Open**: First bar's open of the week
- **High**: Maximum high of the week
- **Low**: Minimum low of the week
- **Close**: Last bar's close of the week
- **Volume**: Sum of all volume in the week

### "Above All Levels" Logic
If no resistance levels are found above the current price, the filter treats this as:
- Price is above all significant volume levels
- Strong bullish indication
- Automatically passes (bypasses `min_distance_to_resistance` check)

## Advantages

1. **Volume-Based**: Unlike price-only technical analysis, volume profile identifies levels where actual trading occurred
2. **Configurable Granularity**: Adjustable bins allow for different levels of precision
3. **Timeframe Flexibility**: Can use daily, weekly, or aggregated data
4. **Multiple Use Cases**: Suitable for both contrarian (mean reversion) and momentum strategies

## Limitations

1. **Historical Bias**: Based purely on past volume data
2. **Market Regime Changes**: Volume profiles may become outdated in rapidly changing markets
3. **Bin Size Impact**: Small changes in bin count can affect level identification
4. **Data Requirements**: Requires sufficient historical data for meaningful analysis

## Related Indicators

- **Support/Resistance Levels**: Traditional price-based levels
- **Volume Weighted Average Price (VWAP)**: Another volume-based analysis tool
- **Point of Control (POC)**: The price level with highest volume in VBP

## Usage Examples

### Basic Usage in a Graph

```python
from nodes.core.market.filters.vbp_level_filter_node import VBPLevelFilter
from core.types_registry import AssetSymbol, AssetClass

# Create filter instance
vbp_filter = VBPLevelFilter(
    id=1,
    params={
        "bins": 50,
        "lookback_years": 2,
        "num_levels": 5,
        "max_distance_to_support": 5.0,
        "min_distance_to_resistance": 5.0,
        "use_weekly": True
    }
)

# Process OHLCV bundle
results = await vbp_filter.execute({
    "ohlcv_bundle": {
        AssetSymbol("AAPL", AssetClass.STOCKS): ohlcv_data
    }
})

# Access filtered symbols
filtered_symbols = results["filtered_ohlcv_bundle"]
```

### Integration with Other Filters

The VBP Level Filter works well in combination with other filters:

```python
# Typical workflow:
# 1. Fetch universe of stocks
# 2. Get OHLCV data (PolygonBatchCustomBars)
# 3. Apply ATRX filter (volatility filter)
# 4. Apply VBP Level Filter (support/resistance filter)
# 5. Apply SMA filter (trend filter)
# 6. Extract symbols

workflow = [
    PolygonUniverseNode(id=1),
    PolygonBatchCustomBarsNode(id=2),
    AtrXFilterNode(id=3, params={"filter_condition": "inside", "upper_threshold": 6.0, "lower_threshold": 0}),
    VBPLevelFilterNode(id=4, params={"use_weekly": True, "lookback_years": 2}),
    SMAFilterNode(id=5, params={"period": 200, "prior_days": 1}),
    ExtractSymbolsNode(id=6)
]
```

### Custom Implementation

If you want to extend the VBP Level Filter:

```python
from nodes.core.market.filters.vbp_level_filter_node import VBPLevelFilter

class CustomVBPFilter(VBPLevelFilter):
    def _should_pass_filter(self, indicator_result):
        # Override filter logic with custom conditions
        result = super()._should_pass_filter(indicator_result)
        
        # Add additional custom logic
        if indicator_result.values.lines.get("num_levels", 0) < 3:
            return False  # Require at least 3 significant levels
        
        return result
```

## API Reference

### Methods

#### `_calculate_indicator(ohlcv_data: List[OHLCVBar]) -> IndicatorResult`
Calculates the volume profile levels and distances.

**Returns:**
- `IndicatorResult` with:
  - `current_price`: Current closing price
  - `closest_support`: Nearest support level
  - `closest_resistance`: Nearest resistance level
  - `distance_to_support`: Percentage distance to support
  - `distance_to_resistance`: Percentage distance to resistance
  - `num_levels`: Number of significant levels found
  - `has_resistance_above`: Boolean indicating if any resistance exists above price

#### `_should_pass_filter(indicator_result: IndicatorResult) -> bool`
Determines if the asset passes the filter based on distance thresholds.

**Returns:**
- `True` if within max distance to support AND at least min distance to resistance (or above all levels)
- `False` otherwise

#### `_fetch_weekly_bars(symbol: AssetSymbol, api_key: str) -> List[OHLCVBar]`
Fetches weekly bars directly from Polygon API when `use_weekly=True`.

#### `_aggregate_to_weekly(ohlcv_data: List[OHLCVBar]) -> List[OHLCVBar]`
Aggregates daily bars to weekly bars for analysis.

#### `_calculate_vbp_levels(ohlcv_data: List[OHLCVBar]) -> Dict[str, Any]`
Calculates volume profile levels using histogram binning.

## References

- Volume Profile is a widely used tool in professional trading
- Popularized by market profile analysis and market microstructure research
- Commonly found in platforms like TradingView, Bloomberg, and Interactive Brokers
