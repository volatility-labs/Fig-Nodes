# Indicator Compatibility Guide for MultiIndicatorChart

This guide explains how to ensure your indicator nodes are fully compatible with the `MultiIndicatorChart` node without requiring custom code changes.

## Overview

The `MultiIndicatorChart` node is designed to be **fully generic** and work with any indicator node that follows the standard data format. No hardcoded checks or custom code should be needed for new indicators.

## Standard Indicator Data Format

### Format 1: Standard IndicatorResult (Recommended)

```python
{
    "indicator_type": "rsi" | "thma" | "macd" | "custom" | etc.,  # String identifier
    "values": {
        "lines": {  # For line indicators (most common)
            "line_name_1": [float | None, float | None, ...],  # Series of values
            "line_name_2": [float | None, float | None, ...],
        },
        "series": [...],  # Optional: time-series format
        "single": float,  # Optional: single value
    },
    "timestamp": int | None,  # Optional timestamp
    "params": {...},  # Optional: indicator parameters
    "metadata": {  # Optional: visualization hints
        "visualization_type": "line" | "heatmap" | "fractal_resonance" | "custom",
        "panel_mode": "overlay" | "separate" | "dedicated",
        "requires_special_panel": bool,
    }
}
```

### Format 2: Per-Symbol Dictionary

For filter nodes that output data for multiple symbols:

```python
{
    "SYMBOL1": {  # Standard IndicatorResult format per symbol
        "indicator_type": "...",
        "values": {
            "lines": {
                "indicator_line_1": [...],
                "indicator_line_2": [...],
            }
        },
        ...
    },
    "SYMBOL2": {...},
}
```

## Key Requirements

### 1. **Preserve None Values**

Always preserve `None` values in your indicator series. The chart node uses `None` to:
- Skip plotting during warm-up periods
- Properly align indicators with different lengths
- Filter out invalid data

**✅ Correct:**
```python
thma_values = [None, None, 0.5, 0.6, 0.7, ...]  # None for warm-up
```

**❌ Incorrect:**
```python
thma_values = [0.0, 0.0, 0.5, 0.6, 0.7, ...]  # Don't use 0.0 for missing data
```

### 2. **Use Descriptive Line Names**

Line names should be descriptive and unique. They'll appear in the chart legend.

**✅ Good:**
```python
"lines": {
    "thma": [...],
    "thma_shifted": [...],
    "volatility": [...],
}
```

**❌ Avoid:**
```python
"lines": {
    "line1": [...],
    "line2": [...],
}
```

### 3. **Include indicator_type**

Always include an `indicator_type` field. This helps with:
- Classification
- Debugging
- Future extensibility

```python
"indicator_type": "thma"  # Use lowercase, descriptive name
```

## Optional: Visualization Metadata

You can optionally specify visualization preferences via metadata:

```python
"metadata": {
    "visualization_type": "line",  # Default: "line"
    "panel_mode": "overlay",  # Default: "overlay" (or "separate" for separate panels)
    "requires_special_panel": False,  # Default: False
}
```

### Visualization Types

- **"line"**: Standard line plot (default for most indicators)
- **"heatmap"**: Heatmap visualization (requires `heatmap_data` in indicator_data)
- **"fractal_resonance"**: Fractal resonance bars (requires `fr_bar_data` in indicator_data)
- **"custom"**: Custom visualization (implemented separately)

### Panel Modes

- **"overlay"**: Plot on price chart (default)
- **"separate"**: Plot in separate panel below price
- **"dedicated"**: Plot in dedicated panel (e.g., stochastic fast/slow pairs)

## Example: THMA Filter Node

Here's how the THMA filter node outputs data (fully compatible):

```python
indicator_dict = {
    "indicator_type": "thma",
    "values": {
        "lines": {
            "thma": thma_result["thma"],  # List[float | None]
            "thma_shifted": thma_result["thma_shifted"],
            "volatility": thma_result["volatility"],
        },
        "series": [],
    },
    "timestamp": None,
    "params": {
        "thma_length": thma_length,
        "volatility_length": volatility_length,
    },
}
indicator_data_output[str(symbol)] = indicator_dict
```

## Special Visualizations

### Heatmap Indicators

Include `heatmap_data` in your indicator_data:

```python
indicator_data = {
    "indicator_type": "stochastic_heatmap",
    "heatmap_data": {
        "values": [...],  # Heatmap values
        "colors": {...},  # Color mapping
    },
    ...
}
```

### Fractal Resonance Indicators

Include `fr_bar_data` in your indicator_data:

```python
indicator_data = {
    "indicator_type": "fractal_resonance",
    "fr_bar_data": {
        "colors": {...},  # Color data
        "block_colors": {...},  # Block color data
    },
    ...
}
```

## Automatic Classification

The chart node automatically classifies indicators based on:

1. **Explicit metadata** (highest priority) - Use metadata to override defaults
2. **Data structure** - Detects `heatmap_data`, `fr_bar_data`, etc.
3. **Indicator type patterns** - Falls back to name-based detection

## Best Practices

1. **Always use the standard format** - Don't create custom formats
2. **Preserve None values** - Don't convert None to 0.0
3. **Use descriptive names** - Make line names clear and unique
4. **Include metadata when needed** - Only if you need special visualization
5. **Test with MultiIndicatorChart** - Verify your indicator displays correctly

## Troubleshooting

### Indicator not showing?

1. Check that `indicator_type` is included
2. Verify `values.lines` contains lists (not scalars)
3. Ensure None values are preserved (not converted to 0.0)
4. Check that line names don't match metadata filter keywords

### Indicator in wrong panel?

1. Add `metadata.panel_mode` to specify desired panel
2. Check that `indicator_panel_mode` param matches your needs
3. Verify classification logic isn't overriding your preferences

### Indicator values look wrong?

1. Verify None values are preserved
2. Check alignment offset calculation
3. Ensure values are floats (not strings)

## Summary

The `MultiIndicatorChart` node is designed to work with **any** indicator that follows the standard format. No custom code is needed - just ensure your indicator outputs data in the correct structure, and the chart node will handle the rest automatically.

