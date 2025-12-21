# Green Expansion Rising Filter Node

## Overview

A dedicated filter node specifically designed to filter symbols showing **green expansion rising** signals from the Squeeze-Expansion indicator. This node matches TradingView's "Squeeze - Expansion Indicator - JD" behavior for detecting bullish expansion signals.

## Purpose

This node was created to provide a focused, dedicated filter for green expansion rising signals, making it easier to find symbols like UNI that show green expansion rising on specific timeframes (e.g., 15-minute charts).

## Filter Modes

### 1. `green_expansion_rising` (Default)
**Any green expansion rising** - Matches both bright and dim green expansion lines that are rising.

**TradingView Logic:**
- Bright green: `rising(top,1) AND top>sq AND price>=0`
- Dim green: `falling(sq,1) AND price>=0` (when top is also rising)

**Use Case:** Catches all green expansion rising signals, including both strong and weak bullish expansion.

### 2. `green_expansion_rising_strong_only`
**Only strong/bright green expansion rising** - Excludes dim green signals.

**TradingView Logic:**
- Only bright green: `rising(top,1) AND top>sq AND price>=0`

**Use Case:** More selective filter - only catches strong bullish expansion signals.

## Key Differences from Deviation Magnet Filter

| Feature | Deviation Magnet Filter | Green Expansion Rising Filter |
|---------|------------------------|-------------------------------|
| **Focus** | All deviation magnet signals | Only green expansion rising |
| **Filter Options** | 20+ filter conditions | 2 focused modes |
| **Simplicity** | Complex, many options | Simple, focused |
| **Use Case** | General deviation magnet filtering | Specifically for green expansion rising |

## Parameters

- **anchor**: Anchor type (1 = SMA, 2 = EMA)
- **bblength**: Bollinger Band length period (default: 50)
- **mult**: Bollinger Band multiplier (default: 2.0)
- **timeframe_multiplier**: Timeframe multiplier for calculation
- **filter_mode**: `green_expansion_rising` or `green_expansion_rising_strong_only`
- **check_last_bar_only**: Check only last bar vs lookback window
- **lookback_bars**: Number of bars to check if check_last_bar_only is False
- **max_symbols**: Maximum symbols to pass through
- **enable_multi_timeframe**: Enable multi-timeframe filtering
- **timeframe_multiplier_1-5**: Multi-timeframe multipliers
- **multi_timeframe_mode**: "all", "any", or "majority"

## Example Usage

### Finding UNI on 15-minute charts with green expansion rising:

1. Set up the filter node
2. Set `filter_mode` to `green_expansion_rising` (or `green_expansion_rising_strong_only` for stronger signals)
3. Ensure your OHLCV data is 15-minute bars
4. Run the filter

The node will return symbols that show green expansion rising signals matching TradingView's behavior.

## Technical Details

- Uses the same underlying `calculate_deviation_magnet` function as Deviation Magnet Filter
- Checks `expansion_bullish_rising_any` for `green_expansion_rising` mode
- Checks `expansion_bullish_rising` for `green_expansion_rising_strong_only` mode
- Supports multi-timeframe filtering
- Outputs indicator data for charting

## TradingView Compatibility

This filter matches TradingView's Pine Script logic:

```pinescript
top_color = rising(top, 1) ? top > sq ? price >= 0 ? color_3 : color_4 : 
   falling_2 ? price >= 0 ? color_5 : color_6 : color.orange : color.orange
```

Where:
- `color_3` = bright green (lime) - `rising(top,1) AND top>sq AND price>=0`
- `color_5` = dim green - `falling(sq,1) AND price>=0`

The filter detects when `top_color` is green AND the expansion line is rising.

