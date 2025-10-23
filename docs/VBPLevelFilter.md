# VBP Level Filter

## Overview

The VBP Level Filter is a technical indicator filter that identifies significant support and resistance levels based on volume profile analysis. It filters assets based on their current price's proximity to these volume-based price levels.

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

## References

- Volume Profile is a widely used tool in professional trading
- Popularized by market profile analysis and market microstructure research
- Commonly found in platforms like TradingView, Bloomberg, and Interactive Brokers

