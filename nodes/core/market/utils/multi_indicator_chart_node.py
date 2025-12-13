"""
Multi-Indicator Chart Node

Generic chart node that combines OHLCV price data with multiple indicators
into a single "super-chart" image per symbol.

Creates professional charts with:
- Price candlesticks (top panel)
- Volume bars (middle panel)  
- Multiple indicators overlaid or in separate panels (bottom panels)

Optimized for vision-language models like Qwen3-VL that need clean, aligned
chart images with exact indicator values.

STANDARD INDICATOR DATA FORMAT:
--------------------------------
All indicator nodes should output data in one of these formats for full compatibility:

1. **Standard IndicatorResult Format** (Recommended):
   {
       "indicator_type": "rsi" | "thma" | "custom" | etc.,  # String identifier
       "values": {
           "lines": {  # For line indicators (most common)
               "line_name_1": [float | None, ...],  # Series of values
               "line_name_2": [float | None, ...],
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

2. **Per-Symbol Dictionary Format**:
   {
       "SYMBOL1": {  # Standard IndicatorResult format per symbol
           "indicator_type": "...",
           "values": {...},
           ...
       },
       "SYMBOL2": {...},
   }

3. **Special Visualization Formats** (for advanced indicators):
   - Heatmap: Include "heatmap_data" key in indicator_data
   - Fractal Resonance: Include "fr_bar_data" key in indicator_data

VISUALIZATION CLASSIFICATION:
------------------------------
The node automatically classifies indicators based on:
1. Explicit metadata (highest priority)
2. Data structure (heatmap_data, fr_bar_data, etc.)
3. Indicator type name patterns (fallback)

Indicators can specify visualization needs via metadata to override defaults.

Inputs:
- ohlcv_bundle: OHLCVBundle - Price/volume data
- indicator_data: Any (optional) - Primary indicator data
- indicator_data_1 through indicator_data_5: Any (optional) - Additional indicators

Outputs:
- images: ConfigDict - One chart image per symbol (base64 data URLs)
"""

import base64
import io
import logging
import sys
from datetime import datetime
from typing import TYPE_CHECKING, Any

import matplotlib

matplotlib.use("Agg")  # non-interactive backend for server-side rendering
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle

if TYPE_CHECKING:
    from matplotlib.axes import Axes
    from matplotlib.figure import Figure
else:
    from matplotlib.axes import Axes
    from matplotlib.figure import Figure

from core.types_registry import AssetClass, AssetSymbol, ConfigDict, NodeCategory, OHLCVBar, OHLCVBundle, ProgressState, get_type
from nodes.base.base_node import Base
from services.time_utils import convert_timestamps_to_datetimes

logger = logging.getLogger(__name__)
logger.disabled = False  # Enable logger temporarily for debugging

def _debug_print(msg: str, force: bool = False):
    """Debug print helper that ensures output is visible"""
    try:
        print(msg, file=sys.stderr, flush=True)
        print(msg, file=sys.stdout, flush=True)  # Always print to both
        logger.error(msg)  # Also use logger.error which goes to stderr
    except Exception as e:
        try:
            print(f"DEBUG PRINT ERROR: {e}", file=sys.stderr, flush=True)
        except:
            pass

# Configure matplotlib for high-quality rendering
plt.rcParams.update({
    'figure.dpi': 200,
    'savefig.dpi': 200,
    'figure.facecolor': 'white',
    'axes.facecolor': 'white',
    'lines.antialiased': True,
    'patch.antialiased': True,
    'text.antialiased': True,
    'font.family': 'sans-serif',
    'font.sans-serif': ['Arial', 'DejaVu Sans', 'Liberation Sans', 'Helvetica', 'sans-serif'],
    'font.size': 9,
    'axes.labelsize': 9,
    'axes.titlesize': 10,
    'xtick.labelsize': 8,
    'ytick.labelsize': 8,
    'legend.fontsize': 7,
    'lines.linewidth': 1.5,
    'grid.alpha': 0.3,
    'grid.color': '#cccccc',
    'axes.grid': True,
    'axes.axisbelow': True,
})


def _encode_fig_to_data_url(fig: "Figure", dpi: int = 200) -> str:
    """Encode matplotlib figure to base64 data URL."""
    buf = io.BytesIO()
    fig.savefig(
        buf,
        format="png",
        bbox_inches="tight",
        pad_inches=0.1,
        dpi=dpi,
        facecolor='#ffffff',
        edgecolor='none',
        transparent=False,
        metadata={'Software': None},
    )
    plt.close(fig)
    buf.seek(0)
    b64 = base64.b64encode(buf.read()).decode("ascii")
    return f"data:image/png;base64,{b64}"


def _normalize_bars(bars: list[OHLCVBar]) -> tuple[list[tuple[int, float, float, float, float]], list[float]]:
    """Normalize bars to (OHLC tuples, volume list) sorted by timestamp."""
    timestamp_map: dict[int, tuple[int, float, float, float, float, float]] = {}
    
    for bar in bars:
        ts = int(bar["timestamp"])
        o = float(bar["open"])
        h = float(bar["high"])
        l = float(bar["low"])
        c = float(bar["close"])
        v = float(bar.get("volume", 0.0))
        timestamp_map[ts] = (ts, o, h, l, c, v)
    
    normalized = sorted(timestamp_map.values(), key=lambda x: x[0])
    ohlc_data = [(ts, o, h, l, c) for ts, o, h, l, c, _v in normalized]
    volume_data = [_v for _, _, _, _, _, _v in normalized]
    
    return ohlc_data, volume_data


def _classify_indicator(indicator_name: str, indicator_data: dict[str, Any] | None = None) -> dict[str, Any]:
    """
    Generic indicator classification based on data structure and metadata.
    
    Returns a dict with classification info:
    - visualization_type: "line" | "heatmap" | "fractal_resonance" | "stochastic_panel" | "custom"
    - panel_mode: "overlay" | "separate" | "dedicated"
    - requires_special_panel: bool
    
    This allows any indicator to specify its visualization needs via metadata,
    falling back to intelligent defaults based on data structure.
    """
    classification = {
        "visualization_type": "line",
        "panel_mode": "overlay",
        "requires_special_panel": False,
    }
    
    if indicator_data is None:
        indicator_data = {}
    
    # Check for explicit metadata first (highest priority)
    metadata = indicator_data.get("metadata", {})
    if isinstance(metadata, dict):
        viz_type = metadata.get("visualization_type")
        panel_mode = metadata.get("panel_mode")
        if viz_type:
            classification["visualization_type"] = viz_type
        if panel_mode:
            classification["panel_mode"] = panel_mode
        if metadata.get("requires_special_panel"):
            classification["requires_special_panel"] = True
    
    # Check indicator_data structure for special visualization data
    if "heatmap_data" in indicator_data or "heatmap" in indicator_data:
        classification["visualization_type"] = "heatmap"
        classification["requires_special_panel"] = True
        classification["panel_mode"] = "dedicated"
    elif "fr_bar_data" in indicator_data or "fractal_resonance" in indicator_data:
        classification["visualization_type"] = "fractal_resonance"
        classification["requires_special_panel"] = True
        classification["panel_mode"] = "dedicated"
    
    # Check indicator_type for hints
    indicator_type = indicator_data.get("indicator_type", "")
    if isinstance(indicator_type, str):
        indicator_type_lower = indicator_type.lower()
        # Generic pattern matching (not hardcoded to specific indicators)
        if "heatmap" in indicator_type_lower:
            classification["visualization_type"] = "heatmap"
            classification["requires_special_panel"] = True
        elif "fractal" in indicator_type_lower or "resonance" in indicator_type_lower:
            classification["visualization_type"] = "fractal_resonance"
            classification["requires_special_panel"] = True
        elif "stochastic" in indicator_type_lower:
            # Stochastic indicators often benefit from dedicated panel when fast+slow together
            classification["panel_mode"] = "dedicated"
    
    # Check indicator name patterns (fallback, but prefer metadata)
    name_lower = indicator_name.lower()
    if "stochastic" in name_lower and ("fast" in name_lower or "slow" in name_lower):
        # Only use dedicated panel if we detect both fast and slow (handled elsewhere)
        classification["panel_mode"] = "dedicated"
    
    return classification


def _extract_indicator_series(indicator_data: Any, symbol: AssetSymbol) -> dict[str, list[float | None]]:
    """Extract indicator series values from various data formats."""
    indicator_series: dict[str, list[float | None]] = {}

    if indicator_data is None:
        return indicator_series

    # Handle list of IndicatorResult
    if isinstance(indicator_data, list):
        for item in indicator_data:
            if isinstance(item, dict) and "indicator_type" in item:
                indicator_series.update(_extract_indicator_series(item, symbol))
        return indicator_series

    # Handle IndicatorResult format
    if isinstance(indicator_data, dict) and "indicator_type" in indicator_data:
        values = indicator_data.get("values", {})
        indicator_type_raw = indicator_data.get("indicator_type", "")
        if hasattr(indicator_type_raw, "name"):
            indicator_type = indicator_type_raw.name.lower()
        elif hasattr(indicator_type_raw, "value"):
            indicator_type = str(indicator_type_raw.value).lower()
        elif isinstance(indicator_type_raw, str):
            indicator_type = indicator_type_raw.lower()
        else:
            indicator_type = str(indicator_type_raw).lower()

        if isinstance(values, dict):
            # Prefer full series if present
            series = values.get("series")
            if isinstance(series, list) and series:
                first_item = series[0]
                if isinstance(first_item, dict):
                    for key in first_item.keys():
                        if key in ("timestamp", "date"):
                            continue
                        indicator_name = f"{indicator_type}_{key}" if indicator_type else key
                        extracted: list[float] = []
                        for item in series:
                            if not isinstance(item, dict):
                                continue
                            val = item.get(key)
                            if val is None:
                                continue
                            try:
                                extracted.append(float(val))
                            except (ValueError, TypeError):
                                continue
                        if extracted:
                            indicator_series[indicator_name] = extracted
                else:
                    extracted: list[float] = []
                    for v in series:
                        if v is None:
                            continue
                        try:
                            extracted.append(float(v))
                        except (ValueError, TypeError):
                            continue
                    if extracted:
                        indicator_series[indicator_type] = extracted

            # Lines may be either series (list) or scalars. We convert scalars to flat lines.
            lines = values.get("lines")
            if isinstance(lines, dict):
                for key, val in lines.items():
                    indicator_name = f"{indicator_type}_{key}" if indicator_type else key
                    if isinstance(val, list) and len(val) > 1:
                        try:
                            # Preserve None values instead of converting to 0.0
                            # This allows the plotting function to properly filter them out
                            converted_values = [
                                float(v) if v is not None else None for v in val
                            ]
                            indicator_series[indicator_name] = converted_values
                        except Exception as e:
                            print(f"      Error extracting line '{indicator_name}': {e}", file=sys.stderr)
                            pass
                    elif isinstance(val, (int, float)):
                        # Convert single numeric line to flat series; length will be trimmed later
                        indicator_series[indicator_name] = [float(val)]

            # Single value fallback -> flat line
            single_val = values.get("single")
            if isinstance(single_val, (int, float)):
                indicator_series[indicator_type] = [float(single_val)]

    # Handle dict of series format (common for multi-indicator outputs)
    elif isinstance(indicator_data, dict):
        first_value = next(iter(indicator_data.values())) if indicator_data else None

        if isinstance(first_value, dict) and not isinstance(first_value, list):
            # Per-symbol structure
            symbol_keys = [
                symbol,
                str(symbol),
                symbol.ticker if hasattr(symbol, "ticker") else None,
            ]
            if hasattr(symbol, "ticker"):
                symbol_keys.append(symbol.ticker.upper())
                symbol_keys.append(symbol.ticker.lower())

            symbol_data = None
            for key in symbol_keys:
                if key and key in indicator_data:
                    symbol_data = indicator_data[key]
                    break

            if symbol_data is None:
                all_keys_look_like_indicators = True
                for key in indicator_data.keys():
                    if key != "metadata":
                        key_str = str(key)
                        if "/" in key_str or len(key_str) <= 6:
                            all_keys_look_like_indicators = False
                            break
                if all_keys_look_like_indicators:
                    symbol_data = indicator_data
                else:
                    for key, value in indicator_data.items():
                        if key != "metadata" and isinstance(value, dict):
                            symbol_data = value
                            break

            if isinstance(symbol_data, dict):
                if "indicator_type" in symbol_data:
                    indicator_series.update(_extract_indicator_series(symbol_data, symbol))
                else:
                    for key, value in symbol_data.items():
                        if key == "metadata":
                            continue
                        if isinstance(value, list):
                            numeric_values: list[float] = []
                            for v in value:
                                if isinstance(v, (int, float)):
                                    numeric_values.append(float(v))
                                elif isinstance(v, dict):
                                    for k in ["value", "close", "val", "atr", "rsi", "macd"]:
                                        if k in v and isinstance(v[k], (int, float)):
                                            numeric_values.append(float(v[k]))
                                            break
                            if numeric_values:
                                indicator_series[key] = numeric_values
        else:
            # Single symbol structure - values are lists
            for key, value in indicator_data.items():
                if key == "metadata":
                    continue
                if isinstance(value, list):
                    numeric_values: list[float] = []
                    for v in value:
                        if isinstance(v, (int, float)):
                            numeric_values.append(float(v))
                        elif isinstance(v, dict):
                            for k in ["value", "close", "val", "atr", "rsi", "macd", "signal", "histogram"]:
                                if k in v and isinstance(v[k], (int, float)):
                                    numeric_values.append(float(v[k]))
                                    break
                    if numeric_values:
                        indicator_series[key] = numeric_values

    return indicator_series


def _plot_candles(ax: "Axes", series: list[tuple[int, float, float, float, float]]) -> None:
    """Plot candlesticks."""
    if not series:
        ax.set_axis_off()
        return
    
    for i, (_ts, o, h, l, c) in enumerate(series):
        color = "#26a69a" if c >= o else "#ef5350"  # teal for up, red for down
        # Wick
        ax.vlines(i, l, h, colors=color, linewidth=1)
        # Body
        height = max(abs(c - o), 1e-9)
        bottom = min(o, c)
        ax.add_patch(Rectangle((i - 0.3, bottom), 0.6, height, color=color, alpha=0.9))
    
    ax.set_xlim(-1, len(series))
    lows = [l for (_ts, _o, _h, l, _c) in series]
    highs = [h for (_ts, _o, h, _l, _c) in series]
    y_min = min(lows) if lows else 0
    y_max = max(highs) if highs else 1
    pad = (y_max - y_min) * 0.05 or 1.0
    ax.set_ylim(y_min - pad, y_max + pad)


def _plot_volume(ax: "Axes", volumes: list[float]) -> None:
    """Plot volume bars."""
    if not volumes:
        ax.set_axis_off()
        return
    
    x_indices = list(range(len(volumes)))
    colors = ["#26a69a" if i == 0 or volumes[i] >= volumes[i-1] else "#ef5350" for i in range(len(volumes))]
    ax.bar(x_indices, volumes, color=colors, alpha=0.6, width=0.8)
    ax.set_xlim(-1, len(volumes))
    ax.set_ylim(0, max(volumes) * 1.1 if volumes else 1)


def _plot_indicator_line(ax: "Axes", values: list[float | None], label: str, color: str, align_offset: int = 0) -> None:
    """Plot indicator as a line, handling alignment offset."""
    if not values:
        return
    
    # Align from end if offset is positive
    if align_offset > 0:
        # Pad with None at the beginning
        padded_values = [None] * align_offset + values
    else:
        padded_values = values
    
    # Filter out None values for plotting
    valid_indices = []
    valid_values = []
    for i, v in enumerate(padded_values):
        if v is not None:
            valid_indices.append(i)
            valid_values.append(v)
    
    if valid_indices and valid_values:
        try:
            ax.plot(valid_indices, valid_values, color=color, linewidth=1.5, label=label, alpha=0.8)
        except Exception as e:
            _debug_print(f"      _plot_indicator_line ERROR plotting '{label}': {e}", force=True)
            raise


def _align_to_length(values: list[float | None], target_len: int) -> list[float | None]:
    """Right-align a series to the target length, padding with None on the left."""
    if not values or target_len <= 0:
        return []
    if len(values) == 1 and target_len > 1:
        # Expand a single value into a flat line across all bars
        return [values[0]] * target_len
    if len(values) >= target_len:
        return list(values[-target_len:])
    pad = [None] * (target_len - len(values))
    return pad + list(values)


def _plot_stochastic_heatmap(
    ax: "Axes",
    stochastics: dict[str, list[float | None]],
    colors: dict[str, list[str]],
    plot_number: int,
    x_indices: list[int],
) -> None:
    """Plot Stochastic Heatmap as horizontal colored lines stacked vertically."""
    ax.set_facecolor('#1a1a1a')  # Dark background like TradingView
    line_width = 3.5
    
    # Plot each stochastic as a horizontal line with colors
    for idx in range(1, min(plot_number, 28) + 1):
        idx_str = str(idx)
        if idx_str not in stochastics or idx_str not in colors:
            continue
        
        stoch_vals = stochastics[idx_str]
        color_list = colors[idx_str]
        
        # Plot line segments with different colors
        y_pos = idx - 1  # Position from 0 to plot_number-1
        
        # Group consecutive bars with same color and plot segments
        current_color = None
        segment_start = None
        
        for i, (val, color) in enumerate(zip(stoch_vals, color_list)):
            if val is not None:
                if color != current_color:
                    # End previous segment
                    if current_color is not None and segment_start is not None:
                        ax.plot(
                            x_indices[segment_start:i],
                            [y_pos] * (i - segment_start),
                            color=current_color,
                            linewidth=line_width,
                            solid_capstyle='round',
                            alpha=0.9,
                        )
                    # Start new segment
                    current_color = color
                    segment_start = i
                elif segment_start is None:
                    # Start first segment
                    current_color = color
                    segment_start = i
            else:
                # End segment if we hit None
                if current_color is not None and segment_start is not None:
                    ax.plot(
                        x_indices[segment_start:i],
                        [y_pos] * (i - segment_start),
                        color=current_color,
                        linewidth=line_width,
                        solid_capstyle='round',
                        alpha=0.9,
                    )
                current_color = None
                segment_start = None
        
        # Plot final segment
        if current_color is not None and segment_start is not None:
            ax.plot(
                x_indices[segment_start:],
                [y_pos] * (len(x_indices) - segment_start),
                color=current_color,
                linewidth=line_width,
                solid_capstyle='round',
                alpha=0.9,
            )
    
    # Set axis limits and labels
    ax.set_xlim(0, len(x_indices) - 1)
    ax.set_ylim(-0.5, plot_number - 0.5)
    # Set label - ensure it's visible (white text on dark background)
    # Use labelpad to ensure label isn't clipped
    ax.set_ylabel("Stochastic Heatmap", fontsize=10, fontweight='bold', color='white', labelpad=5)
    ax.tick_params(colors='white', labelsize=8)
    ax.grid(True, alpha=0.2, color='white')
    # Ensure background is dark for visibility
    ax.set_facecolor('#000000')
    # Explicitly set ylabel properties to ensure visibility
    ax.yaxis.label.set_color('white')
    ax.yaxis.label.set_fontsize(10)
    ax.yaxis.label.set_fontweight('bold')
    ax.yaxis.label.set_visible(True)


def _plot_fractal_resonance_bars(
    ax: "Axes",
    colors: dict[str, list[str]],
    block_colors: dict[str, list[str]],
    x_indices: list[int],
    ribbon_line_width: int = 8,
) -> None:
    """Plot Fractal Resonance Bar indicator as horizontal bars stacked vertically."""
    # Use light gray background so white bars are visible
    ax.set_facecolor('#f5f5f5')
    
    # Timeframes: 1, 2, 4, 8, 16, 32, 64, 128
    TIMEFRAMES = ["1", "2", "4", "8", "16", "32", "64", "128"]
    
    # Calculate Y positions for each row (use positive values, stacked from top)
    total_rows = len(TIMEFRAMES) * 2
    start_y = total_rows * ribbon_line_width
    
    y_positions_regular: list[float] = []
    y_positions_block: list[float] = []
    
    for idx, tf in enumerate(TIMEFRAMES):
        # Regular color row (top row for this timeframe)
        y_pos_regular = start_y - (idx * 2 + 1) * ribbon_line_width
        y_positions_regular.append(y_pos_regular)
        # Block color row (bottom row for this timeframe)
        y_pos_block = start_y - (idx * 2 + 2) * ribbon_line_width
        y_positions_block.append(y_pos_block)
    
    # Collect all bars to draw efficiently
    bars_to_draw: list[dict[str, Any]] = []
    
    # Draw horizontal bars for each timeframe
    for idx, tf in enumerate(TIMEFRAMES):
        y_pos_regular = y_positions_regular[idx]
        y_pos_block = y_positions_block[idx]
        
        regular_colors = colors.get(tf, [])
        block_colors_tf = block_colors.get(tf, [])
        
        # Draw horizontal bars for each time point
        for i in range(len(x_indices)):
            if i < len(regular_colors):
                regular_color = regular_colors[i]
                if regular_color:  # Only skip if None
                    bars_to_draw.append({
                        'y': y_pos_regular,
                        'left': i - 0.5,
                        'width': 1.0,
                        'height': ribbon_line_width,
                        'color': regular_color,
                        'zorder': 2,
                    })
            
            if i < len(block_colors_tf):
                block_color = block_colors_tf[i]
                if block_color:  # Only skip if None
                    bars_to_draw.append({
                        'y': y_pos_block,
                        'left': i - 0.5,
                        'width': 1.0,
                        'height': ribbon_line_width,
                        'color': block_color,
                        'zorder': 2,
                    })
    
    # Draw bars
    if bars_to_draw:
        for bar in bars_to_draw:
            # For white bars, use a light gray color instead so they're visible
            if bar['color'] == '#ffffff':
                face_color = '#e8e8e8'  # Light gray instead of white
                edge_color = '#d0d0d0'  # Slightly darker border
                edge_width = 0.5
            else:
                face_color = bar['color']
                edge_color = 'none'
                edge_width = 0.0
            
            rect = Rectangle(
                (bar['left'], bar['y'] - bar['height'] / 2),
                bar['width'],
                bar['height'],
                facecolor=face_color,
                edgecolor=edge_color,
                linewidth=edge_width,
                alpha=1.0,
                zorder=bar['zorder'],
            )
            ax.add_patch(rect)
    
    # Draw separator line at top
    ax.axhline(y=start_y, color='#000000', linewidth=1.5, zorder=3)
    
    # Add Y-axis labels for timeframes
    y_tick_positions = []
    y_tick_labels = []
    for idx, tf in enumerate(TIMEFRAMES):
        y_pos = (y_positions_regular[idx] + y_positions_block[idx]) / 2
        y_tick_positions.append(y_pos)
        y_tick_labels.append(f"WT{tf}")
    
    ax.set_yticks(y_tick_positions)
    ax.set_yticklabels(y_tick_labels, color='#000000', fontsize=9)
    ax.tick_params(colors='#000000')
    
    # Set Y-axis limits
    ax.set_ylim(0, start_y + ribbon_line_width)
    ax.set_ylabel("Fractal Resonance", fontsize=9)


class MultiIndicatorChart(Base):
    """
    Generic multi-indicator chart node.
    
    Creates one "super-chart" per symbol combining:
    - Price candlesticks
    - Volume bars
    - Multiple indicators (5-8 indicators overlaid or in separate panels)
    
    Optimized for vision-language models that need clean, aligned chart images.
    """

    inputs = {
        "ohlcv_bundle": get_type("OHLCVBundle") | None,
        "indicator_data": Any | None,
        **{f"indicator_data_{i}": Any | None for i in range(1, 6)},
    }

    outputs = {
        "images": get_type("ConfigDict"),
        "debug_info": get_type("ConfigDict"),
    }

    CATEGORY = NodeCategory.MARKET

    default_params = {
        "max_bars": 200,  # Maximum bars to display
        "max_symbols": 50,  # Maximum symbols to process
        "show_volume": True,  # Show volume panel
        "indicator_panel_mode": "overlay",  # "overlay" or "separate" panels
        "max_indicators": 8,  # Maximum indicators to plot
        "dpi": 200,  # Image resolution
    }

    params_meta = [
        {
            "name": "max_bars",
            "type": "number",
            "default": 200,
            "min": 10,
            "max": 1000,
            "step": 10,
            "label": "Max Bars",
            "description": "Maximum bars to display per symbol",
        },
        {
            "name": "max_symbols",
            "type": "number",
            "default": 50,
            "min": 1,
            "max": 100,
            "step": 1,
            "label": "Max Symbols",
            "description": "Maximum symbols to process",
        },
        {
            "name": "show_volume",
            "type": "combo",
            "default": True,
            "options": [True, False],
            "label": "Show Volume",
            "description": "Display volume panel",
        },
        {
            "name": "indicator_panel_mode",
            "type": "combo",
            "default": "overlay",
            "options": ["overlay", "separate"],
            "label": "Indicator Mode",
            "description": "Overlay indicators on price panel or use separate panels",
        },
        {
            "name": "max_indicators",
            "type": "number",
            "default": 8,
            "min": 1,
            "max": 20,
            "step": 1,
            "label": "Max Indicators",
            "description": "Maximum indicators to plot per chart",
        },
        {
            "name": "dpi",
            "type": "number",
            "default": 200,
            "min": 100,
            "max": 400,
            "step": 50,
            "label": "DPI",
            "description": "Image resolution (higher = better quality, larger file)",
        },
        {
            "name": "price_panel_height",
            "type": "number",
            "default": 2.5,
            "min": 1.0,
            "max": 6.0,
            "step": 0.5,
            "label": "Price Panel Height",
            "description": "Height of price panel (smaller = more space for indicators)",
        },
        {
            "name": "volume_panel_height",
            "type": "number",
            "default": 1.0,
            "min": 0.5,
            "max": 3.0,
            "step": 0.5,
            "label": "Volume Panel Height",
            "description": "Height of volume panel",
        },
        {
            "name": "indicator_panel_height",
            "type": "number",
            "default": 1.5,
            "min": 1.0,
            "max": 4.0,
            "step": 0.5,
            "label": "Indicator Panel Height",
            "description": "Height of regular indicator line panels (for separate mode or fast/slow stochastic lines)",
        },
        {
            "name": "special_visualization_height",
            "type": "number",
            "default": 4.0,
            "min": 2.0,
            "max": 8.0,
            "step": 0.5,
            "label": "Special Visualization Height",
            "description": "Height for special visualizations (heatmaps, bar charts, etc.) - detected automatically from indicator data structure",
        },
    ]

    async def _execute_impl(self, inputs: dict[str, Any]) -> dict[str, Any]:
        """Execute the multi-indicator chart node.
        
        IMPORTANT: This node only plots charts for symbols that exist in ohlcv_bundle.
        If indicator_data contains more symbols (e.g., from indicator nodes that calculated
        for all symbols before filtering), only indicators for symbols in ohlcv_bundle
        will be extracted and plotted. This allows you to:
        
        1. Connect indicator nodes that calculated for ALL symbols
        2. Connect filtered OHLCV bundle (with fewer symbols)
        3. Charts will only be generated for filtered symbols with their indicators
        
        This solves the filter pipeline problem where each filter stage reduces the symbol set.
        """
        # CRITICAL DEBUG - Print immediately, before anything else
        try:
            import sys
            sys.stderr.write("\n" + "="*80 + "\n")
            sys.stderr.write("MultiIndicatorChart._execute_impl START\n")
            sys.stderr.write(f"Node ID: {getattr(self, 'id', 'UNKNOWN')}\n")
            sys.stderr.write(f"Input keys: {list(inputs.keys()) if inputs else 'NO INPUTS'}\n")
            sys.stderr.write("="*80 + "\n")
            sys.stderr.flush()
            sys.stdout.write("\n" + "="*80 + "\n")
            sys.stdout.write("MultiIndicatorChart._execute_impl START\n")
            sys.stdout.write(f"Node ID: {getattr(self, 'id', 'UNKNOWN')}\n")
            sys.stdout.write(f"Input keys: {list(inputs.keys()) if inputs else 'NO INPUTS'}\n")
            sys.stdout.write("="*80 + "\n")
            sys.stdout.flush()
        except Exception as e:
            pass  # Don't fail if debug fails
        
        # Debug FIRST - before any early returns, so we can see what's happening
        _debug_print(f"\n{'='*60}", force=True)
        _debug_print(f"MultiIndicatorChart._execute_impl START (node_id={self.id})", force=True)
        _debug_print(f"{'='*60}", force=True)
        _debug_print(f"ALL input keys received: {list(inputs.keys())}", force=True)
        
        # Check graph context to see what links exist
        incoming_links_info = []
        try:
            links = self.graph_context.get("links", []) if hasattr(self, 'graph_context') else []
            current_node_id = self.graph_context.get("current_node_id", self.id) if hasattr(self, 'graph_context') else self.id
            incoming_links = [l for l in links if l.get("target_id") == current_node_id]
            _debug_print(f"Incoming links to this node: {len(incoming_links)}", force=True)
            
            # Try to determine output slot names from node definitions
            node_definitions = {}
            if hasattr(self, 'graph_context') and 'nodes' in self.graph_context:
                for node_data in self.graph_context.get('nodes', []):
                    node_id = node_data.get('id')
                    node_type = node_data.get('type', '')
                    # Try to get output slot names from node registry if available
                    node_definitions[node_id] = {
                        'type': node_type,
                        'id': node_id,
                    }
            
            for link in incoming_links[:10]:  # Show more links
                origin_id = link.get("origin_id")
                origin_slot = link.get("origin_slot")
                target_slot = link.get("target_slot")
                target_key = list(self.inputs.keys())[target_slot] if target_slot < len(self.inputs) else f"slot_{target_slot}"
                
                # Try to determine what output key this maps to
                origin_node_info = node_definitions.get(origin_id, {})
                origin_type = origin_node_info.get('type', 'unknown')
                
                # Common output slot names for filter nodes
                if origin_slot == 0:
                    output_slot_name = "filtered_ohlcv_bundle"
                elif origin_slot == 1:
                    output_slot_name = "indicator_data"
                else:
                    output_slot_name = f"slot_{origin_slot}"
                
                link_info = f"  Link: node {origin_id} ({origin_type}) output slot {origin_slot} ({output_slot_name}) -> {target_key} (input slot {target_slot})"
                _debug_print(link_info, force=True)
                incoming_links_info.append((origin_id, origin_slot, target_key, origin_type))
        except Exception as e:
            _debug_print(f"  Error checking graph context: {e}", force=True)
        
        ohlcv_bundle = inputs.get("ohlcv_bundle") or {}
        max_bars = int(self.params.get("max_bars", 200))
        max_symbols = int(self.params.get("max_symbols", 50))
        show_volume = self.params.get("show_volume", True)
        panel_mode = str(self.params.get("indicator_panel_mode", "overlay"))
        max_indicators = int(self.params.get("max_indicators", 8))
        dpi = int(self.params.get("dpi", 200))
        _debug_print(f"  Panel mode: {panel_mode}, max_indicators: {max_indicators}", force=True)
        
        # Collect all indicator data FIRST - check even if OHLCV bundle is empty
        indicator_data_list: list[Any] = []
        
        # Check ALL possible indicator input keys, even if None or empty
        all_indicator_keys = ["indicator_data"] + [f"indicator_data_{i}" for i in range(1, 6)]
        _debug_print(f"\nChecking indicator inputs:", force=True)
        # Don't print full inputs dict as it might be huge - just show what we're looking for
        for key in all_indicator_keys:
            if key in inputs:
                value = inputs[key]
                if isinstance(value, dict):
                    dict_info = f"dict with {len(value)} keys" if value else "empty dict"
                    if value:
                        sample_keys = list(value.keys())[:3]
                        dict_info += f" (sample keys: {sample_keys})"
                    _debug_print(f"  ✓ {key}: present, type={type(value).__name__}, {dict_info}", force=True)
                else:
                    _debug_print(f"  ✓ {key}: present, type={type(value).__name__}, value={value}", force=True)
                # Include even empty dicts - they might be valid but empty
                if value is not None:
                    indicator_data_list.append(value)
            else:
                _debug_print(f"  ✗ {key}: NOT IN INPUTS DICT (key missing entirely)", force=True)
        
        _debug_print(f"\nTotal indicator inputs collected: {len(indicator_data_list)}", force=True)
        if ohlcv_bundle:
            symbols_preview = list(ohlcv_bundle.keys())[:5]
            _debug_print(f"OHLCV bundle: {len(ohlcv_bundle)} symbols (first 5: {symbols_preview})", force=True)
        else:
            _debug_print(f"OHLCV bundle: EMPTY - no symbols to chart", force=True)
        
        # Early return if no OHLCV bundle (upstream nodes likely failed)
        if not ohlcv_bundle:
            _debug_print(f"\n⚠️  EARLY RETURN: No OHLCV bundle - cannot generate charts", force=True)
            _debug_print(f"   Indicator inputs found: {len(indicator_data_list)}", force=True)
            
            # Try to extract symbols from indicator data to provide helpful error message
            indicator_symbols = set()
            for ind_data in indicator_data_list:
                if isinstance(ind_data, dict):
                    # Indicator data is typically keyed by symbol string
                    for key in ind_data.keys():
                        if isinstance(key, str):
                            indicator_symbols.add(key)
            
            if indicator_symbols:
                _debug_print(f"   Symbols found in indicator data: {len(indicator_symbols)} (sample: {list(indicator_symbols)[:5]})", force=True)
            
            if incoming_links_info:
                print(f"\n   Expected inputs from links:", file=sys.stderr)
                ohlcv_link_found = False
                for link_info in incoming_links_info:
                    if len(link_info) == 4:
                        origin_id, origin_slot, target_key, origin_type = link_info
                    else:
                        origin_id, origin_slot, target_key = link_info[:3]
                        origin_type = "unknown"
                    if target_key == "ohlcv_bundle":
                        ohlcv_link_found = True
                        print(f"     ✗ {target_key} from node {origin_id} ({origin_type}) slot {origin_slot} - MISSING", file=sys.stderr)
                        print(f"        → Connect the 'filtered_ohlcv_bundle' output from a filter node to this input!", file=sys.stderr)
                    elif target_key.startswith("indicator_data"):
                        print(f"     ✓ {target_key} from node {origin_id} ({origin_type}) slot {origin_slot} - CONNECTED", file=sys.stderr)
                
                if not ohlcv_link_found:
                    print(f"\n   ❌ NO CONNECTION FOUND for 'ohlcv_bundle' input!", file=sys.stderr)
                    print(f"   → ACTION REQUIRED: Connect 'filtered_ohlcv_bundle' output from THMAFilter (node 107) or FractalResonanceFilter (node 85)", file=sys.stderr)
                    print(f"      to the 'ohlcv_bundle' input of MultiIndicatorChart (node {self.id})", file=sys.stderr)
            
            print(f"\n   DIAGNOSIS: The chart node needs OHLCV price data to generate charts.", file=sys.stderr)
            print(f"   Without 'ohlcv_bundle', no charts can be created even if indicators are connected.", file=sys.stderr)
            print(f"{'='*60}\n", file=sys.stderr)
            return {"images": {}, "debug_info": {"error": "No OHLCV bundle received - connect filtered_ohlcv_bundle output from a filter node to ohlcv_bundle input"}}
        
        images: dict[str, str] = {}
        debug_info: dict[str, Any] = {}
        symbol_list = list(ohlcv_bundle.items())[:max_symbols]
        
        # Keep logging minimal to avoid UI clutter
        
        # Color palette for indicators
        indicator_colors = [
            "#2196F3", "#FF9800", "#4CAF50", "#F44336", "#9C27B0",
            "#00BCD4", "#FFC107", "#795548", "#607D8B", "#E91E63",
        ]
        
        for idx, (symbol, bars) in enumerate(symbol_list):
            if not bars:
                continue
            
            # Normalize bars
            ohlc_data, volume_data = _normalize_bars(bars)
            
            # Limit to max_bars
            if len(ohlc_data) > max_bars:
                ohlc_data = ohlc_data[-max_bars:]
                volume_data = volume_data[-max_bars:]
            
            if len(ohlc_data) < 10:
                logger.debug(f"MultiIndicatorChart: Skipping {symbol} - insufficient bars ({len(ohlc_data)})")
                continue
            
            # Extract all indicator series for this symbol
            # Note: Indicator data may contain more symbols than ohlcv_bundle (from filter stages)
            # We only extract indicators for symbols that exist in the OHLCV bundle
            all_indicators: dict[str, list[float | None]] = {}
            symbol_debug: dict[str, Any] = {
                "indicator_inputs": len(indicator_data_list),
                "indicators_found": [],
            }
            
            # Special visualization data (heatmap, FR bars)
            heatmap_data: dict[str, Any] | None = None
            fr_bar_data: dict[str, Any] | None = None
            
            symbol_str = str(symbol)
            symbol_ticker = symbol.ticker if hasattr(symbol, 'ticker') else None
            
            for idx, indicator_data in enumerate(indicator_data_list):
                if indicator_data is None:
                    continue
                
                # Debug: Print what we're trying to extract
                _debug_print(f"\n  Processing indicator input {idx} for symbol {symbol_str}")
                if isinstance(indicator_data, dict):
                    _debug_print(f"    Dict keys: {list(indicator_data.keys())[:10]}")
                    if symbol_str in indicator_data:
                        _debug_print(f"    Found symbol key '{symbol_str}' in dict")
                
                # First, try to extract directly
                symbol_indicators = _extract_indicator_series(indicator_data, symbol)
                symbol_indicator_data = None  # Will be set if we find symbol-specific data
                
                # If no indicators found, check if indicator_data is a dict with symbol strings as keys
                # This is the format filter nodes output: {str(symbol): IndicatorResult_dict}
                if not symbol_indicators and isinstance(indicator_data, dict):
                    # Check if this is a per-symbol dict (keys are symbol strings)
                    # Filter nodes output: {str(symbol): IndicatorResult_dict}
                    if symbol_str in indicator_data:
                        # Found symbol as string key - extract from that value
                        symbol_indicator_data = indicator_data[symbol_str]
                        _debug_print(f"    Extracting from symbol key, data type: {type(symbol_indicator_data)}")
                        symbol_indicators = _extract_indicator_series(symbol_indicator_data, symbol)
                    elif symbol_ticker and symbol_ticker in indicator_data:
                        # Try ticker as key
                        symbol_indicator_data = indicator_data[symbol_ticker]
                        _debug_print(f"    Extracting from ticker key '{symbol_ticker}'")
                        symbol_indicators = _extract_indicator_series(symbol_indicator_data, symbol)
                    elif symbol in indicator_data:
                        # Try AssetSymbol object as key
                        symbol_indicator_data = indicator_data[symbol]
                        _debug_print(f"    Extracting from AssetSymbol key")
                        symbol_indicators = _extract_indicator_series(symbol_indicator_data, symbol)
                
                if symbol_indicators:
                    _debug_print(f"    Extracted {len(symbol_indicators)} indicators: {list(symbol_indicators.keys())}")
                    # Debug THMA indicators specifically
                    for key, vals in symbol_indicators.items():
                        if "thma" in key.lower():
                            valid_count = len([v for v in vals if v is not None])
                            _debug_print(f"      THMA indicator '{key}': total={len(vals)}, valid={valid_count}, sample={vals[-5:] if len(vals) >= 5 else vals}", force=True)
                else:
                    _debug_print(f"    No indicators extracted")
                
                # Check for special visualization data (heatmap, FR bars)
                # Use symbol_indicator_data if we already extracted it, otherwise fetch it
                if symbol_indicator_data is None and isinstance(indicator_data, dict) and symbol_str in indicator_data:
                    symbol_indicator_data = indicator_data[symbol_str]
                
                if symbol_indicator_data is not None and isinstance(symbol_indicator_data, dict):
                    # Check for stochastic heatmap data
                    if "heatmap_data" in symbol_indicator_data:
                        heatmap_data = symbol_indicator_data["heatmap_data"]
                        print(f"    ✓ Found stochastic heatmap data", file=sys.stderr)
                    # Check for fractal resonance bar data
                    if "fr_bar_data" in symbol_indicator_data:
                        fr_bar_data = symbol_indicator_data["fr_bar_data"]
                        print(f"    ✓ Found fractal resonance bar data", file=sys.stderr)
                
                # Merge into all_indicators (handle name conflicts) and align to OHLC length
                for key, values in symbol_indicators.items():
                    if key in all_indicators:
                        base_key = key
                        counter = 1
                        while key in all_indicators:
                            key = f"{base_key}_{counter}"
                            counter += 1
                    aligned_values = _align_to_length(values, len(ohlc_data))
                    all_indicators[key] = aligned_values
            
            if all_indicators:
                symbol_debug["indicators_found"] = list(all_indicators.keys())
                symbol_debug["indicator_lengths"] = {
                    k: len([v for v in vals if v is not None]) for k, vals in all_indicators.items()
                }
            else:
                symbol_debug["indicators_found"] = []
            
            debug_info[str(symbol)] = symbol_debug
            
            # No debug logging here to keep UI clean
            
            # Separate fast/slow stochastic lines from regular indicators
            # These will get their own dedicated panel above the heatmap
            stochastic_fast_slow: dict[str, list[float | None]] = {}
            plottable_indicators: dict[str, list[float | None]] = {}
            filtered_out: list[str] = []
            metadata_keywords = [
                "has_", "total_", "last_", "checked_", "max_", "valid_", "min_required",
                "custom_has_", "custom_total_", "custom_last_", "custom_checked_",
                "custom_max_", "custom_valid_", "custom_min_", "custom_"
            ]
            
            for ind_name, ind_values in all_indicators.items():
                # Skip metadata fields
                if any(ind_name.lower().startswith(keyword) for keyword in metadata_keywords):
                    filtered_out.append(f"{ind_name} (metadata)")
                    continue
                
                # Skip single values (unless they're meaningful like a level)
                if len(ind_values) == 1:
                    filtered_out.append(f"{ind_name} (single value)")
                    continue
                
                # Skip if all values are None or identical (no variation)
                valid_values = [v for v in ind_values if v is not None]
                if len(valid_values) < 2:
                    filtered_out.append(f"{ind_name} (<2 valid values)")
                    continue
                
                # Check if there's meaningful variation (not all the same value)
                if len(set(valid_values)) == 1:
                    filtered_out.append(f"{ind_name} (no variation)")
                    continue
                
                # Classify indicator to determine panel placement
                # Try to get indicator data for classification (may not always be available)
                indicator_classification = _classify_indicator(ind_name, None)
                
                # Separate indicators that need dedicated panels (e.g., stochastic fast/slow pairs)
                # This is detected generically via classification, not hardcoded names
                if indicator_classification["panel_mode"] == "dedicated":
                    # Check if this is a stochastic fast/slow pair (common pattern)
                    if "stochastic" in ind_name.lower() and ("fast" in ind_name.lower() or "slow" in ind_name.lower()):
                        stochastic_fast_slow[ind_name] = ind_values
                    else:
                        # Other indicators requiring dedicated panels go to regular plottable
                        plottable_indicators[ind_name] = ind_values
                else:
                    plottable_indicators[ind_name] = ind_values
            
            if filtered_out:
                _debug_print(f"  Filtered out {len(filtered_out)} non-plottable indicators: {filtered_out[:10]}", force=True)
            if plottable_indicators:
                _debug_print(f"  ✓ {len(plottable_indicators)} plottable indicators: {list(plottable_indicators.keys())}", force=True)
            
            # Limit indicators
            indicator_items = list(plottable_indicators.items())[:max_indicators]
            
            # Get panel height parameters (generic - works with any indicators)
            price_height = float(self.params.get("price_panel_height", 2.5))
            volume_height = float(self.params.get("volume_panel_height", 1.0))
            indicator_height = float(self.params.get("indicator_panel_height", 1.5))
            special_viz_height = float(self.params.get("special_visualization_height", 4.0))
            
            # Fast/slow stochastic lines use regular indicator height (they're line indicators)
            stoch_lines_height = indicator_height
            
            # Special visualizations (heatmap, FR bars, etc.) use special visualization height
            # This is detected generically by checking for special data structures in indicator_data
            # Any indicator with special visualization data will automatically use this height
            
            # Build panel list and height ratios
            panel_heights: list[float] = []
            panel_types: list[str] = []  # Track panel types for reference
            
            # Price panel (always first)
            panel_heights.append(price_height)
            panel_types.append("price")
            
            # Volume panel (if enabled)
            if show_volume:
                panel_heights.append(volume_height)
                panel_types.append("volume")
            
            # Regular indicator panels (if separate mode)
            if panel_mode == "separate" and indicator_items:
                for _ in indicator_items:
                    panel_heights.append(indicator_height)
                    panel_types.append("indicator")
            
            # Fast/slow stochastic lines panel (uses regular indicator height)
            if stochastic_fast_slow:
                panel_heights.append(stoch_lines_height)
                panel_types.append("stoch_lines")
            
            # Special visualization panels (detected generically from indicator data structure)
            # Any indicator input that contains special visualization data structures will
            # automatically use the special_visualization_height parameter
            
            # Heatmap panel (detected by presence of heatmap_data in any indicator_data input)
            if heatmap_data:
                panel_heights.append(special_viz_height)
                panel_types.append("heatmap")
            
            # Fractal resonance panel (detected by presence of fr_bar_data in any indicator_data input)
            if fr_bar_data:
                panel_heights.append(special_viz_height)
                panel_types.append("fr")
            
            # Note: Any future special visualizations can be added here by detecting
            # their data structure (e.g., if "custom_viz_data" in indicator_data)
            # and they will automatically use special_viz_height
            # This makes the sizing system generic and extensible for any indicator type
            
            num_panels = len(panel_heights)
            total_height = sum(panel_heights)
            
            # Create figure with gridspec for height control
            from matplotlib import gridspec
            fig = plt.figure(figsize=(12, total_height))
            gs = gridspec.GridSpec(num_panels, 1, height_ratios=panel_heights, hspace=0.3)
            
            panel_idx = 0
            
            # Panel 1: Price with indicators (if overlay mode)
            ax_price = fig.add_subplot(gs[panel_idx])
            _plot_candles(ax_price, ohlc_data)
            ax_price.set_ylabel("Price", fontsize=9)
            ax_price.set_title(str(symbol), fontsize=10, fontweight="bold")
            ax_price.grid(True, alpha=0.3)
            
            # Overlay indicators on price panel (exclude fast/slow stochastic lines - they get their own panel)
            if panel_mode == "overlay" and indicator_items:
                plotted_count = 0
                _debug_print(f"  Attempting to plot {len(indicator_items)} indicators in overlay mode for {symbol_str}", force=True)
                for i, (ind_name, ind_values) in enumerate(indicator_items):
                    # Skip fast/slow stochastic lines - they get their own dedicated panel
                    if "stochastic" in ind_name.lower() and ("fast" in ind_name.lower() or "slow" in ind_name.lower()):
                        _debug_print(f"    Skipping {ind_name} (stochastic - gets own panel)", force=True)
                        continue
                    if ind_values and len(ind_values) > 0:
                        try:
                            # Calculate alignment offset
                            offset = len(ohlc_data) - len(ind_values)
                            color = indicator_colors[i % len(indicator_colors)]
                            valid_count = len([v for v in ind_values if v is not None])
                            _debug_print(f"    Plotting {ind_name}: total={len(ind_values)}, valid={valid_count}, offset={offset}, color={color}", force=True)
                            _plot_indicator_line(ax_price, ind_values, ind_name, color, offset)
                            plotted_count += 1
                        except Exception as e:
                            error_msg = f"MultiIndicatorChart: Failed to plot indicator {ind_name} for {symbol_str}: {e}"
                            _debug_print(f"    ✗ ERROR plotting {ind_name}: {e}", force=True)
                            logger.debug(error_msg)
                            import traceback
                            _debug_print(f"      Traceback: {traceback.format_exc()}", force=True)
                
                _debug_print(f"  Plotted {plotted_count} indicators on price panel for {symbol_str}", force=True)
                if plotted_count > 0:
                    ax_price.legend(loc="upper left", fontsize=7, framealpha=0.7)
                else:
                    _debug_print(f"    ⚠️  No indicators plotted for {symbol_str}!", force=True)
            
            panel_idx += 1
            
            # Panel 2: Volume (if enabled)
            if show_volume:
                ax_volume = fig.add_subplot(gs[panel_idx], sharex=ax_price)
                _plot_volume(ax_volume, volume_data)
                ax_volume.set_ylabel("Volume", fontsize=9)
                ax_volume.grid(True, alpha=0.3)
                panel_idx += 1
            
            # Additional panels: Separate indicator panels (if separate mode)
            if panel_mode == "separate" and indicator_items:
                _debug_print(f"  Attempting to plot {len(indicator_items)} indicators in separate panels for {symbol_str}", force=True)
                for i, (ind_name, ind_values) in enumerate(indicator_items):
                    ax_ind = fig.add_subplot(gs[panel_idx], sharex=ax_price)
                    panel_idx += 1
                    
                    if ind_values and len(ind_values) > 0:
                        try:
                            offset = len(ohlc_data) - len(ind_values)
                            color = indicator_colors[i % len(indicator_colors)]
                            valid_count = len([v for v in ind_values if v is not None])
                            _debug_print(f"    Plotting {ind_name} in separate panel: total={len(ind_values)}, valid={valid_count}, offset={offset}, color={color}", force=True)
                            _plot_indicator_line(ax_ind, ind_values, ind_name, color, offset)
                        except Exception as e:
                            error_msg = f"MultiIndicatorChart: Failed to plot indicator {ind_name} for {symbol_str}: {e}"
                            _debug_print(f"    ✗ ERROR plotting {ind_name} in separate panel: {e}", force=True)
                            logger.debug(error_msg)
                            import traceback
                            _debug_print(f"      Traceback: {traceback.format_exc()}", force=True)
                    
                    ax_ind.set_ylabel(ind_name, fontsize=9)
                    ax_ind.grid(True, alpha=0.3)
            
            # Panel: Fast/Slow Stochastic Lines (dedicated panel above heatmap)
            if stochastic_fast_slow:
                ax_stoch_lines = fig.add_subplot(gs[panel_idx], sharex=ax_price)
                panel_idx += 1
                plotted_stoch = 0
                for i, (ind_name, ind_values) in enumerate(sorted(stochastic_fast_slow.items())):
                    if ind_values and len(ind_values) > 0:
                        try:
                            offset = len(ohlc_data) - len(ind_values)
                            color = indicator_colors[i % len(indicator_colors)]
                            # Clean up label: "stochastic_heatmap_fast_line" -> "Fast Stochastic"
                            clean_label = ind_name.replace("stochastic_heatmap_", "").replace("_", " ").title()
                            if "fast" in clean_label.lower():
                                clean_label = "Fast Stochastic"
                            elif "slow" in clean_label.lower():
                                clean_label = "Slow Stochastic"
                            _plot_indicator_line(ax_stoch_lines, ind_values, clean_label, color, offset)
                            plotted_stoch += 1
                        except Exception as e:
                            print(f"  Failed to plot stochastic line {ind_name}: {e}", file=sys.stderr)
                
                if plotted_stoch > 0:
                    ax_stoch_lines.legend(loc="upper left", fontsize=7, framealpha=0.7)
                ax_stoch_lines.set_ylabel("Stochastic Lines", fontsize=9)
                ax_stoch_lines.grid(True, alpha=0.3)
            
            # Panel: Stochastic Heatmap (if available)
            if heatmap_data:
                ax_heatmap = fig.add_subplot(gs[panel_idx], sharex=ax_price)
                panel_idx += 1
                x_indices = list(range(len(ohlc_data)))
                stochastics_raw = heatmap_data.get("stochastics", {})
                colors_raw = heatmap_data.get("colors", {})
                plot_number = heatmap_data.get("plot_number", 28)
                
                # Align heatmap data to OHLC length (right-align, take last N values)
                stochastics: dict[str, list[float | None]] = {}
                colors: dict[str, list[str]] = {}
                for idx_str in stochastics_raw.keys():
                    stoch_vals = stochastics_raw[idx_str]
                    color_vals = colors_raw.get(idx_str, [])
                    if len(stoch_vals) > len(ohlc_data):
                        stochastics[idx_str] = stoch_vals[-len(ohlc_data):]
                        colors[idx_str] = color_vals[-len(ohlc_data):] if len(color_vals) >= len(ohlc_data) else color_vals
                    else:
                        stochastics[idx_str] = stoch_vals
                        colors[idx_str] = color_vals
                
                try:
                    _plot_stochastic_heatmap(ax_heatmap, stochastics, colors, plot_number, x_indices)
                    # Ensure label is set correctly and visible (set after plotting, before tight_layout)
                    ax_heatmap.set_ylabel("Stochastic Heatmap", fontsize=10, fontweight='bold', color='white', labelpad=5)
                    # Ensure ylabel is visible by setting it explicitly
                    ax_heatmap.yaxis.label.set_color('white')
                    ax_heatmap.yaxis.label.set_fontsize(10)
                    ax_heatmap.yaxis.label.set_fontweight('bold')
                    ax_heatmap.yaxis.label.set_visible(True)
                except Exception as e:
                    print(f"  Failed to plot stochastic heatmap: {e}", file=sys.stderr)
            
            # Panel: Fractal Resonance Bars (if available)
            if fr_bar_data:
                ax_fr = fig.add_subplot(gs[panel_idx], sharex=ax_price)
                panel_idx += 1
                x_indices = list(range(len(ohlc_data)))
                colors_raw = fr_bar_data.get("colors", {})
                block_colors_raw = fr_bar_data.get("block_colors", {})
                
                # Align FR bar data to OHLC length (right-align, take last N values)
                colors: dict[str, list[str]] = {}
                block_colors: dict[str, list[str]] = {}
                TIMEFRAMES = ["1", "2", "4", "8", "16", "32", "64", "128"]
                for tf in TIMEFRAMES:
                    if tf in colors_raw:
                        color_vals = colors_raw[tf]
                        if len(color_vals) > len(ohlc_data):
                            colors[tf] = color_vals[-len(ohlc_data):]
                        else:
                            colors[tf] = color_vals
                    if tf in block_colors_raw:
                        block_vals = block_colors_raw[tf]
                        if len(block_vals) > len(ohlc_data):
                            block_colors[tf] = block_vals[-len(ohlc_data):]
                        else:
                            block_colors[tf] = block_vals
                
                try:
                    _plot_fractal_resonance_bars(ax_fr, colors, block_colors, x_indices)
                    # Ensure label is set correctly (plot function sets it, but ensure it's visible)
                    ax_fr.set_ylabel("Fractal Resonance", fontsize=9)
                except Exception as e:
                    print(f"  Failed to plot fractal resonance bars: {e}", file=sys.stderr)
            
            # Format x-axis with timestamps
            if ohlc_data:
                timestamps = [bar[0] for bar in ohlc_data]
                # Use time conversion utility
                try:
                    asset_class = symbol.asset_class if hasattr(symbol, 'asset_class') else AssetClass.CRYPTO
                    local_dates = convert_timestamps_to_datetimes(timestamps, asset_class)
                    
                    # Show evenly spaced labels
                    num_labels = min(10, len(local_dates))
                    step = max(1, len(local_dates) // num_labels)
                    tick_positions = list(range(0, len(local_dates), step))
                    tick_labels = [local_dates[i].strftime("%m/%d") for i in tick_positions]
                    
                    ax_price.set_xticks(tick_positions)
                    ax_price.set_xticklabels(tick_labels, rotation=45, ha='right', fontsize=8)
                except Exception:
                    pass
            
            plt.tight_layout()
            
            # Encode to image
            try:
                image_data = _encode_fig_to_data_url(fig, dpi=dpi)
                images[str(symbol)] = image_data
                # Don't emit partial results to avoid UI logging noise
            except Exception as e:
                # Only log actual errors, not debug info
                print(f"ERROR MultiIndicatorChart: Failed to generate chart for {symbol}: {e}", file=sys.stderr)
        
        # Final summary
        print(f"\n{'='*60}", file=sys.stderr)
        print(f"MultiIndicatorChart._execute_impl COMPLETE", file=sys.stderr)
        print(f"  Charts generated: {len(images)}", file=sys.stderr)
        print(f"  Indicator inputs received: {len(indicator_data_list)}", file=sys.stderr)
        total_indicators_found = sum(len(info.get('indicators_found', [])) for info in debug_info.values())
        print(f"  Total indicators found across all symbols: {total_indicators_found}", file=sys.stderr)
        if debug_info:
            symbols_with_indicators = [s for s, info in debug_info.items() if info.get('indicators_found')]
            print(f"  Symbols with indicators: {len(symbols_with_indicators)}/{len(debug_info)}", file=sys.stderr)
        print(f"{'='*60}\n", file=sys.stderr)
        
        return {"images": images, "debug_info": debug_info}

