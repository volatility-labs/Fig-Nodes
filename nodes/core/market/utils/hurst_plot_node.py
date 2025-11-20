"""
Hurst Spectral Analysis Oscillator Plot Node

Creates combined chart with price OHLC bars and Hurst bandpass waves.
"""

import base64
import io
import logging
from datetime import datetime
from typing import TYPE_CHECKING, Any

import matplotlib
import matplotlib.ticker

matplotlib.use("Agg")  # non-interactive backend for server-side rendering
import matplotlib.pyplot as plt

# Configure matplotlib for StockCharts-quality rendering
# These settings ensure crisp, professional-looking charts similar to StockCharts
plt.rcParams.update({
    # High-quality rendering
    'figure.dpi': 250,  # High base DPI for crisp rendering
    'savefig.dpi': 250,  # Save at high DPI
    'figure.facecolor': 'white',
    'axes.facecolor': 'white',
    
    # Anti-aliasing for smooth lines and text
    'lines.antialiased': True,
    'patch.antialiased': True,
    'text.antialiased': True,
    # Note: 'font.antialiased' is not a valid rcParam - text.antialiased handles font rendering
    
    # Font rendering for crisp text
    'font.family': 'sans-serif',
    'font.sans-serif': ['Arial', 'DejaVu Sans', 'Liberation Sans', 'Helvetica', 'sans-serif'],
    'font.size': 10,
    'axes.labelsize': 10,
    'axes.titlesize': 12,
    'xtick.labelsize': 9,
    'ytick.labelsize': 9,
    'legend.fontsize': 8,
    
    # Line rendering
    'lines.linewidth': 1.5,
    'lines.markeredgewidth': 0.5,
    'patch.linewidth': 0.5,
    
    # Grid and axes - StockCharts-style clean grid (clearly visible)
    'axes.grid': True,
    'axes.axisbelow': True,
    'grid.alpha': 0.7,  # More visible grid
    'grid.color': '#c0c0c0',  # Darker gray for better visibility
    'grid.linewidth': 0.8,  # Thicker grid lines
    'grid.linestyle': '-',  # Solid lines
    'axes.edgecolor': '#cccccc',  # Lighter edge color for subtle panel separation
    'axes.linewidth': 0.8,  # Thinner axes edges
    'xtick.color': '#666666',  # Clean tick colors
    'ytick.color': '#666666',
    
    # Image rendering quality
    'image.interpolation': 'bilinear',
    'image.resample': True,
    
    # Backend-specific optimizations
    'agg.path.chunksize': 10000,  # Optimize path rendering
})

if TYPE_CHECKING:
    from matplotlib.axes import Axes
    from matplotlib.figure import Figure
else:
    from matplotlib.axes import Axes
    from matplotlib.figure import Figure

from core.api_key_vault import APIKeyVault
from core.types_registry import AssetSymbol, NodeCategory, NodeValidationError, OHLCVBar, get_type
from nodes.base.base_node import Base
from services.indicator_calculators.cco_calculator import calculate_cco
from services.indicator_calculators.ema_calculator import calculate_ema
from services.indicator_calculators.hurst_calculator import calculate_hurst_oscillator
from services.indicator_calculators.mesa_stochastic_calculator import (
    calculate_mesa_stochastic_multi_length,
)
from services.polygon_service import fetch_current_snapshot

logger = logging.getLogger(__name__)


def _encode_fig_to_data_url(fig: "Figure", dpi: int = 250) -> str:
    """Encode matplotlib figure to base64 data URL with StockCharts-quality rendering.
    
    Uses configurable DPI (default 250) with optimized PNG compression to achieve crisp, 
    professional charts similar to StockCharts while keeping file sizes reasonable.
    
    Args:
        fig: Matplotlib figure to encode
        dpi: DPI for image rendering (default 250). Lower values (150-200) reduce file size
             for API calls, higher values (250-300) provide better quality for display.
    """
    buf = io.BytesIO()
    # StockCharts-quality settings:
    # - Configurable DPI: 250 default for high quality, can be reduced to 150-200 for API calls
    # - metadata={'Software': None}: Remove metadata to reduce size
    # - bbox_inches='tight': Remove extra whitespace
    # - pad_inches=0.1: Small padding for clean edges
    # - facecolor='white': Clean white background
    # - edgecolor='none': No border
    # - transparent=False: Solid background for better compression
    fig.savefig(
        buf,
        format="png",
        bbox_inches="tight",
        pad_inches=0.1,
        dpi=dpi,  # Configurable DPI (default 250 for quality, can reduce to 150-200 for API)
        facecolor='#ffffff',
        edgecolor='none',
        transparent=False,
        metadata={'Software': None},  # Remove metadata
    )
    # Note: PNG optimization is handled automatically by matplotlib's PNG writer
    # The 'optimize' parameter is not available in savefig() for Agg backend
    plt.close(fig)
    buf.seek(0)
    b64 = base64.b64encode(buf.read()).decode("ascii")
    return f"data:image/png;base64,{b64}"


def _normalize_bars(bars: list[OHLCVBar]) -> tuple[list[tuple[int, float, float, float, float]], list[float]]:
    """Return tuple of (OHLC data, volume data) sorted by ts.
    
    OHLC data: list of tuples (ts, open, high, low, close)
    Volume data: list of volume values
    
    If duplicate timestamps exist, keeps the LAST occurrence (which should be the snapshot bar).
    """
    # Use dict to deduplicate by timestamp, keeping last occurrence
    timestamp_map: dict[int, tuple[int, float, float, float, float, float]] = {}
    duplicates_found = []
    
    for i, bar in enumerate(bars):
        ts = int(bar["timestamp"])
        open_price = float(bar["open"])
        high_price = float(bar["high"])
        low_price = float(bar["low"])
        close_price = float(bar["close"])
        volume = float(bar.get("volume", 0.0))
        
        # Check if this timestamp already exists
        if ts in timestamp_map:
            old_price = timestamp_map[ts][4]
            duplicates_found.append((ts, old_price, close_price, i))
            logger.warning(f"⚠️ Duplicate timestamp {ts}: overwriting old price ${old_price:.4f} with new price ${close_price:.4f} (bar index {i})")
        
        # Store/overwrite - last occurrence wins (snapshot bar should be last)
        timestamp_map[ts] = (ts, open_price, high_price, low_price, close_price, volume)
    
    if duplicates_found:
        logger.warning(f"🔍 Found {len(duplicates_found)} duplicate timestamp(s), kept last occurrence for each")
    
    # Convert to list and sort by timestamp
    normalized = list(timestamp_map.values())
    normalized.sort(key=lambda x: x[0])
    
    # Separate OHLC and volume
    ohlc_data = [(ts, o, h, l, c) for ts, o, h, l, c, _v in normalized]
    volume_data = [_v for _, _, _, _, _, _v in normalized]
    
    # Log the last bar to verify snapshot is included
    if len(ohlc_data) > 0:
        last_ts, _last_o, _last_h, _last_l, last_c = ohlc_data[-1]
        logger.warning(f"🔍 Normalized bars: Last bar ts={last_ts}, price=${last_c:.4f} (should be snapshot)")
    
    return ohlc_data, volume_data


def _plot_candles(ax: "Axes", series: list[tuple[int, float, float, float, float]], volumes: list[float] | None = None, ema_10: list[float | None] | None = None, ema_30: list[float | None] | None = None, ema_100: list[float | None] | None = None, show_current_price: bool = True, current_price_override: float | None = None, show_volume_by_price: bool = False, volume_by_price_bars: int = 12, volume_by_price_color_volume: bool = False, volume_by_price_opacity: float = 0.3) -> None:
    """Plot OHLC bars, volume bars, and EMAs on the given axes.
    
    Args:
        ax: Matplotlib axes to plot on
        series: List of (timestamp, open, high, low, close) tuples
        volumes: Optional list of volume values (same length as series)
        ema_10: Optional pre-calculated EMA 10 values (same length as series)
        ema_30: Optional pre-calculated EMA 30 values (same length as series)
        ema_100: Optional pre-calculated EMA 100 values (same length as series)
        show_current_price: Whether to show price annotation
        current_price_override: Optional fresh price to use for annotation (overrides last bar's close)
    """
    if not series:
        return
    
    opens = [x[1] for x in series]
    highs = [x[2] for x in series]
    lows = [x[3] for x in series]
    closes = [x[4] for x in series]
    
    # Light background for better AI visibility
    ax.set_facecolor('#ffffff')
    
    # Plot EMAs (10, 30, 100 periods) if provided (pre-calculated with warm-up)
    # Use thicker, more distinct lines with higher contrast for better AI vision model accuracy
    ema_data = [
        (ema_10, '#1565c0', 'EMA 10', 2.0),      # Darker blue
        (ema_30, '#ef5350', 'EMA 30', 2.0),      # Red
        (ema_100, '#4caf50', 'EMA 100', 2.5)     # Green - thickest line (most important reference)
    ]
    ema_lines = []
    
    for ema_values, color, label, linewidth in ema_data:
        if ema_values and len(ema_values) == len(series):
            # Filter out None values and plot
            valid_ema = [(i, v) for i, v in enumerate(ema_values) if v is not None]
            if valid_ema:
                valid_indices = [x[0] for x in valid_ema]
                valid_values = [x[1] for x in valid_ema]
                # Use solid lines with full opacity for maximum visibility
                # zorder 4: above VBP bars (2) and grid (0), but below candles (5)
                line, = ax.plot(valid_indices, valid_values, color=color, linewidth=linewidth, alpha=1.0, label=label, linestyle='-', zorder=4)
                ema_lines.append(line)
    
    # Detect EMA crosses (recent crosses are particularly positive signals)
    recent_crosses: list[str] = []
    lookback_bars = 20  # Check last 20 bars for recent crosses
    
    if ema_10 and ema_30 and len(ema_10) == len(series) and len(ema_30) == len(series):
        # Check for EMA 10 crossing above EMA 30
        for i in range(max(1, len(series) - lookback_bars), len(series)):
            if (ema_10[i-1] is not None and ema_10[i] is not None and 
                ema_30[i-1] is not None and ema_30[i] is not None):
                # Bullish cross: EMA 10 was below EMA 30, now above
                if ema_10[i-1] <= ema_30[i-1] and ema_10[i] > ema_30[i]:
                    bars_ago = len(series) - 1 - i
                    recent_crosses.append(f"EMA 10↑30 ({bars_ago} bar{'s' if bars_ago != 1 else ''} ago)")
                    # Mark cross point with a small circle
                    cross_price = (ema_10[i] + ema_30[i]) / 2
                    ax.plot(i, cross_price, 'o', color='#4caf50', markersize=6, zorder=10, alpha=0.8)
    
    if ema_30 and ema_100 and len(ema_30) == len(series) and len(ema_100) == len(series):
        # Check for EMA 30 crossing above EMA 100
        for i in range(max(1, len(series) - lookback_bars), len(series)):
            if (ema_30[i-1] is not None and ema_30[i] is not None and 
                ema_100[i-1] is not None and ema_100[i] is not None):
                # Bullish cross: EMA 30 was below EMA 100, now above
                if ema_30[i-1] <= ema_100[i-1] and ema_30[i] > ema_100[i]:
                    bars_ago = len(series) - 1 - i
                    recent_crosses.append(f"EMA 30↑100 ({bars_ago} bar{'s' if bars_ago != 1 else ''} ago)")
                    # Mark cross point with a small circle
                    cross_price = (ema_30[i] + ema_100[i]) / 2
                    ax.plot(i, cross_price, 'o', color='#4caf50', markersize=6, zorder=10, alpha=0.8)
    
    if ema_10 and ema_100 and len(ema_10) == len(series) and len(ema_100) == len(series):
        # Check for EMA 10 crossing above EMA 100 (less common but significant)
        for i in range(max(1, len(series) - lookback_bars), len(series)):
            if (ema_10[i-1] is not None and ema_10[i] is not None and 
                ema_100[i-1] is not None and ema_100[i] is not None):
                # Bullish cross: EMA 10 was below EMA 100, now above
                if ema_10[i-1] <= ema_100[i-1] and ema_10[i] > ema_100[i]:
                    bars_ago = len(series) - 1 - i
                    recent_crosses.append(f"EMA 10↑100 ({bars_ago} bar{'s' if bars_ago != 1 else ''} ago)")
                    # Mark cross point with a small circle
                    cross_price = (ema_10[i] + ema_100[i]) / 2
                    ax.plot(i, cross_price, 'o', color='#4caf50', markersize=6, zorder=10, alpha=0.8)
    
    # Add recent crosses annotation if any detected - limit to max 3 and position at bottom left
    # This prevents layout issues and keeps charts symmetrical
    if ema_lines and len(series) > 0 and recent_crosses:
        # Limit to 3 most recent crosses to prevent annotation from extending
        limited_crosses = recent_crosses[:3]
        crosses_text = "Recent Crosses: " + ", ".join(limited_crosses)
        
        # Position at bottom left corner, fixed position to maintain grid symmetry
        price_min = min(closes) if closes else 0
        ax.annotate(
            crosses_text,
            xy=(0, price_min),  # Bottom left corner
            xytext=(8, 8),  # Small offset from corner
            textcoords="offset points",
            fontsize=8,  # Slightly smaller to fit better
            color='#4caf50',
            fontweight='bold',
            bbox=dict(boxstyle="round,pad=0.3", facecolor='#e8f5e9', edgecolor='#4caf50', alpha=0.95, linewidth=1.2),
            ha='left',
            va='bottom'  # Anchor to bottom
        )
    
    # Get price range for volume scaling
    all_prices = lows + highs
    price_min = min(all_prices) if all_prices else 0
    price_max = max(all_prices) if all_prices else 1
    price_range = price_max - price_min if price_max > price_min else 1
    
    # Track volume MA line for legend
    volume_ma_line = None
    
    # Plot volume bars at bottom if provided
    if volumes and len(volumes) == len(series):
        # Calculate volume moving average (20-period)
        volume_ma_period = 20
        volume_ma: list[float | None] = []
        for i in range(len(volumes)):
            if i < volume_ma_period - 1:
                volume_ma.append(None)
            else:
                ma_value = sum(volumes[i - volume_ma_period + 1:i + 1]) / volume_ma_period
                volume_ma.append(ma_value)
        
        # Scale volume to fit in bottom 20% of price chart
        max_volume = max(volumes) if volumes else 1
        volume_scale = (price_range * 0.20) / max_volume if max_volume > 0 else 0
        volume_bottom = price_min
        
        # Plot volume moving average line
        if volume_ma and any(v is not None for v in volume_ma):
            valid_ma_indices = [i for i, v in enumerate(volume_ma) if v is not None]
            valid_ma_values = [volume_ma[i] * volume_scale + volume_bottom for i in valid_ma_indices]
            volume_ma_line, = ax.plot(valid_ma_indices, valid_ma_values, color='#ff9800', linewidth=1.5, alpha=0.7, linestyle='--', label='Vol MA(20)')
        
        for i, volume in enumerate(volumes):
            volume_height = volume * volume_scale
            # StockCharts style: gray volume bars (not color-coded by price direction)
            from matplotlib.patches import Rectangle
            volume_rect = Rectangle(
                (i - 0.4, volume_bottom),
                0.8,
                volume_height,
                facecolor="#808080",  # Gray color for StockCharts style
                edgecolor="#808080",
                alpha=0.4,  # Semi-transparent gray volume bars
                linewidth=0.5,
            )
            ax.add_patch(volume_rect)
    
        # Annotate current volume relative to average (only if meaningful)
        if len(volumes) > 0 and volume_ma and volume_ma[-1] is not None:
            current_volume = volumes[-1]
            avg_volume = volume_ma[-1]
            if avg_volume > 0 and current_volume >= 0:
                volume_ratio = current_volume / avg_volume
                
                # Only show annotation if ratio is meaningful (not essentially zero)
                # Hide if ratio is less than 0.001 (essentially zero or rounding error)
                if volume_ratio >= 0.001:
                    # Format volume annotation with appropriate precision
                    if volume_ratio < 1.0:
                        # Less than average - show 2 decimal places
                        volume_text = f"Vol: {volume_ratio:.2f}x avg"
                    elif volume_ratio < 10.0:
                        # Normal range - show 2 decimal places
                        volume_text = f"Vol: {volume_ratio:.2f}x avg"
                    else:
                        # Very high ratio - show 1 decimal place
                        volume_text = f"Vol: {volume_ratio:.1f}x avg"
                    
                    # Position volume annotation above volume bars, near the price area for better visibility
                    # Use a position that's above the volume bars but below price annotations
                    volume_annotation_y = volume_bottom + (price_range * 0.25)  # Position in lower 25% of price range
                    ax.annotate(
                        volume_text,
                        xy=(len(series) - 1, volume_annotation_y),
                        xytext=(8, 0),
                        textcoords="offset points",
                        fontsize=9,
                        color='#ff9800',
                        fontweight='bold',
                        bbox=dict(boxstyle="round,pad=0.3", facecolor='white', edgecolor='#ff9800', alpha=0.95, linewidth=1.5),
                        ha='left',
                        va='center'
        )
    
    # Plot OHLC bars - StockCharts style: vertical line with horizontal ticks
    # Vertical line: high to low
    # Left tick: open
    # Right tick: close
    # StockCharts color scheme: black for up (close >= open), red for down (close < open)
    tick_length = 0.15  # Length of horizontal ticks for open/close
    
    for i, (open, close, high, low) in enumerate(zip(opens, closes, highs, lows)):
        # StockCharts style: black for up bars, red for down bars
        color = "black" if close >= open else "#ef5350"  # Black for up, red for down
        
        # Plot vertical line (high to low) with higher zorder so candles appear above VBP bars
        ax.plot([i, i], [low, high], color=color, linewidth=1.5, alpha=1.0, solid_capstyle='round', solid_joinstyle='round', zorder=5)
        
        # Plot left tick (open)
        ax.plot([i - tick_length, i], [open, open], color=color, linewidth=1.5, alpha=1.0, solid_capstyle='round', solid_joinstyle='round', zorder=5)
        
        # Plot right tick (close)
        ax.plot([i, i + tick_length], [close, close], color=color, linewidth=1.5, alpha=1.0, solid_capstyle='round', solid_joinstyle='round', zorder=5)
    
    # Add generous padding on the right to ensure the last OHLC bar is fully visible
    # Last bar is at index len(series) - 1, with tick extending to (len(series) - 1) + tick_length
    # Increased padding from 0.5 to 1.5 for better visibility and AI analysis
    # This ensures the last bar and price annotation are clearly visible
    ax.set_xlim(-0.5, len(series) + 1.5)
    
    # Annotate current price - use fresh snapshot if provided, otherwise use last bar's close
    if show_current_price and len(closes) > 0:
        # Use fresh price if provided, otherwise use last bar's close
        current_price = current_price_override if current_price_override is not None else closes[-1]
        current_index = len(closes) - 1
        
        # Draw horizontal dotted line at current price for better visibility
        ax.axhline(
            y=current_price,
            color='#ef5350',  # Red color for price line
            linestyle='--',  # Dotted line
            linewidth=1.5,
            alpha=0.7,
            zorder=5,  # Above grid but below OHLC bars/EMAs
            label=None  # Don't add to legend
        )
        
        # Increased fontsize and padding for better visibility of current price
        ax.annotate(
            f"${current_price:.4f}",
            xy=(current_index, current_price),
            xytext=(8, 12),  # Increased from (5, 10) for more space from OHLC bar
            textcoords="offset points",
            bbox=dict(boxstyle="round,pad=0.4", facecolor="yellow", alpha=0.9, linewidth=2.0),  # Thicker border, more padding
            fontsize=12,  # Increased from 10 to 12 for better AI readability
            fontweight="bold",
            color="black",
            ha="left",
            va="bottom"
        )
    
    # Plot Volume-by-Price on the left side if enabled (BEFORE candles so candles appear on top)
    if show_volume_by_price and volumes and len(volumes) == len(series):
        _plot_volume_by_price(
            ax,
            closes,
            volumes,
            num_bars=volume_by_price_bars,
            separate_up_down=volume_by_price_color_volume,
            opacity=volume_by_price_opacity,
        )
    
    # StockCharts-style grid - clearer but still subtle
    ax.grid(True, alpha=0.7, linestyle='-', linewidth=0.8, color='#c0c0c0', zorder=0)
    ax.set_axisbelow(True)
    # Enhance axes edges for better panel separation
    for spine in ax.spines.values():
        spine.set_color('#cccccc')
        spine.set_linewidth(0.8)
    
    # Add legend for EMAs and volume MA if any were plotted
    # Note: EMA values are already included in legend labels from the code above
    legend_handles = list(ema_lines) if ema_lines else []
    legend_labels = []
    
    # Get EMA labels (already updated with values above)
    if ema_lines and len(series) > 0:
        last_index = len(series) - 1
        for ema_values, color, label, _linewidth in ema_data:
            if ema_values and len(ema_values) == len(series) and ema_values[last_index] is not None:
                ema_value = ema_values[last_index]
                if isinstance(ema_value, (int, float)):
                    legend_labels.append(f"{label}: ${ema_value:.4f}")
                else:
                    legend_labels.append(label)
            else:
                legend_labels.append(label)
    
    # Add volume MA to legend
    if volume_ma_line:
        legend_handles.append(volume_ma_line)
        legend_labels.append('Vol MA(20)')
    
    if legend_handles:
        # Use updated labels if we have them, otherwise use default
        if legend_labels and len(legend_labels) == len(legend_handles):
            ax.legend(handles=legend_handles, labels=legend_labels, loc='upper left', fontsize=8, framealpha=0.9, fancybox=False, shadow=False, frameon=True)
        else:
            ax.legend(handles=legend_handles, loc='upper left', fontsize=8, framealpha=0.9, fancybox=False, shadow=False, frameon=True)
    
    # Light background color
    ax.set_facecolor('#ffffff')


def _calculate_volume_by_price(
    closes: list[float],
    volumes: list[float],
    num_bars: int = 12,
    separate_up_down: bool = False,
) -> tuple[list[tuple[float, float, float, float]], float, float]:
    """
    Calculate Volume-by-Price bars based on closing prices and volumes.
    
    Args:
        closes: List of closing prices
        volumes: List of volume values (same length as closes)
        num_bars: Number of Volume-by-Price bars (default 12)
        separate_up_down: Whether to separate up volume and down volume
    
    Returns:
        Tuple of (bars, price_min, price_max) where bars is a list of
        (zone_low, zone_high, total_volume, up_volume) tuples
    """
    if not closes or not volumes or len(closes) != len(volumes):
        return [], 0.0, 0.0
    
    # Find price range for closing prices
    price_min = min(closes)
    price_max = max(closes)
    price_range = price_max - price_min
    
    if price_range == 0:
        return [], price_min, price_max
    
    # Calculate zone size
    zone_size = price_range / num_bars
    
    # Initialize zones
    zones: list[list[float]] = [[] for _ in range(num_bars)]  # Store volumes for each zone
    zone_up_volumes: list[float] = [0.0] * num_bars
    zone_down_volumes: list[float] = [0.0] * num_bars
    
    # Determine if each day was up or down
    up_days: list[bool] = []
    for i in range(len(closes)):
        if i == 0:
            up_days.append(True)  # First day is considered "up" by default
        else:
            up_days.append(closes[i] >= closes[i-1])
    
    # Assign each closing price to a zone and accumulate volume
    for i, (close, volume, is_up) in enumerate(zip(closes, volumes, up_days)):
        # Calculate which zone this price belongs to
        if close == price_max:
            zone_idx = num_bars - 1  # Highest price goes to last zone
        else:
            zone_idx = int((close - price_min) / zone_size)
            zone_idx = min(zone_idx, num_bars - 1)  # Ensure within bounds
        
        zones[zone_idx].append(volume)
        if separate_up_down:
            if is_up:
                zone_up_volumes[zone_idx] += volume
            else:
                zone_down_volumes[zone_idx] += volume
    
    # Create bars: (zone_low, zone_high, total_volume, up_volume)
    bars: list[tuple[float, float, float, float]] = []
    for i in range(num_bars):
        zone_low = price_min + i * zone_size
        zone_high = price_min + (i + 1) * zone_size
        total_volume = sum(zones[i]) if zones[i] else 0.0
        up_volume = zone_up_volumes[i] if separate_up_down else total_volume
        
        bars.append((zone_low, zone_high, total_volume, up_volume))
    
    return bars, price_min, price_max


def _plot_volume_by_price(
    ax: "Axes",
    closes: list[float],
    volumes: list[float],
    num_bars: int = 12,
    separate_up_down: bool = False,
    opacity: float = 0.5,
    max_width_fraction: float = 0.25,
) -> None:
    """
    Plot Volume-by-Price bars extending into the chart area (StockCharts-style).
    
    Args:
        ax: Matplotlib axes to plot on
        closes: List of closing prices
        volumes: List of volume values
        num_bars: Number of Volume-by-Price bars (default 12)
        separate_up_down: Whether to use two colors (green for up, red for down)
        opacity: Opacity of the bars (0.0 to 1.0)
        max_width_fraction: Maximum width of Volume-by-Price bars as fraction of chart width
    """
    if not closes or not volumes or len(closes) != len(volumes):
        return
    
    # Calculate Volume-by-Price bars
    vbp_bars, _, _ = _calculate_volume_by_price(
        closes, volumes, num_bars, separate_up_down
    )
    
    if not vbp_bars:
        return
    
    # Get current axis limits to determine positioning
    xlim = ax.get_xlim()
    chart_width = xlim[1] - xlim[0]
    
    # Calculate maximum volume for scaling
    max_volume = max(bar[2] for bar in vbp_bars)  # Total volume
    if max_volume == 0:
        return
    
    # Position bars to extend into the chart area (StockCharts-style)
    # Bars start from left edge and extend into the chart
    bar_start_x = xlim[0] - chart_width * max_width_fraction  # Start outside chart
    bar_end_x = xlim[0] + chart_width * 0.15  # Extend well into chart area
    
    # Calculate bar width (total space available)
    bar_width = bar_end_x - bar_start_x
    
    # Plot each Volume-by-Price bar
    for zone_low, zone_high, total_volume, up_volume in vbp_bars:
        if total_volume == 0:
            continue
        
        # Calculate bar height (price range of the zone)
        bar_height = zone_high - zone_low
        
        # Calculate bar length (scaled by volume)
        bar_length = (total_volume / max_volume) * bar_width
        
        # Center the bar vertically within its price zone
        bar_center_y = (zone_low + zone_high) / 2
        bar_bottom_y = bar_center_y - bar_height / 2
        
        from matplotlib.patches import Rectangle
        
        # Use lower zorder so candles appear on top of VBP bars
        # zorder 2: above grid (0) and volume bars (1), but below EMAs (4) and candles (5)
        vbp_zorder = 2
        
        if separate_up_down and up_volume > 0:
            # Plot up volume (green) portion
            up_length = (up_volume / total_volume) * bar_length
            down_volume = total_volume - up_volume
            
            # Up volume starts from the left
            up_rect = Rectangle(
                (bar_start_x, bar_bottom_y),
                up_length,
                bar_height,
                facecolor='#4caf50',  # Green for up volume
                edgecolor='#2e7d32',
                linewidth=0.8,  # Thicker edge for better visibility
                alpha=opacity,
                zorder=vbp_zorder,
            )
            ax.add_patch(up_rect)
            
            # Down volume (red) portion
            if down_volume > 0:
                down_length = (down_volume / total_volume) * bar_length
                down_rect = Rectangle(
                    (bar_start_x + up_length, bar_bottom_y),
                    down_length,
                    bar_height,
                    facecolor='#ef5350',  # Red for down volume
                    edgecolor='#c62828',
                    linewidth=0.8,  # Thicker edge for better visibility
                    alpha=opacity,
                    zorder=vbp_zorder,
                )
                ax.add_patch(down_rect)
        else:
            # Single color (gray/pink) for all volume - StockCharts-style
            rect = Rectangle(
                (bar_start_x, bar_bottom_y),
                bar_length,
                bar_height,
                facecolor='#e91e63',  # Pink/magenta color similar to StockCharts
                edgecolor='#c2185b',
                linewidth=0.8,  # Thicker edge for better visibility
                alpha=opacity,
                zorder=vbp_zorder,
            )
            ax.add_patch(rect)
    
    # Adjust x-axis limits to accommodate Volume-by-Price bars extending into chart
    # Keep original right limit, extend left to show bars
    new_xlim = (bar_start_x - chart_width * 0.02, xlim[1])
    ax.set_xlim(new_xlim)


def _plot_hurst_waves(
    ax: "Axes",
    timestamps: list[int],
    bandpasses: dict[str, list[float | None]],
    composite: list[float | None],
    selected_periods: list[str] | None = None,
    show_composite: bool = True,
    y_axis_scale: str = "symlog",
) -> None:
    """Plot Hurst bandpass waves on the given axes - TradingView style."""
    if not timestamps:
        return
    
    # Light background for better AI visibility
    ax.set_facecolor('#ffffff')
    
    x_indices = list(range(len(timestamps)))
    
    # Color map for different periods (matching TradingView colors)
    period_colors = {
        "5_day": "#9c27b0",      # purple
        "10_day": "#2196f3",    # blue
        "20_day": "#00bcd4",    # aqua
        "40_day": "#4caf50",    # green
        "80_day": "#ffeb3b",    # yellow
        "20_week": "#ff9800",   # orange
        "40_week": "#f44336",   # red
        "18_month": "#856c44",  # brown
        "54_month": "#000000",  # black
        "9_year": "#9e9e9e",    # gray
        "18_year": "#ffffff",   # white
    }
    
    # Plot individual bandpasses if selected
    if selected_periods:
        for period_name in selected_periods:
            if period_name in bandpasses:
                values = bandpasses[period_name]
                color = period_colors.get(period_name, "#888888")
                # Only plot non-None values
                valid_indices = [i for i, v in enumerate(values) if v is not None]
                valid_values = [values[i] for i in valid_indices]
                valid_x = [x_indices[i] for i in valid_indices]
                if valid_x and len(valid_x) > 0:
                    # Check if wave has meaningful amplitude (not just noise)
                    wave_range = max(valid_values) - min(valid_values) if valid_values else 0
                    
                    # Thicker lines for better AI visibility and analysis
                    # Increased linewidths for optimal clarity in AI image analysis
                    if period_name in ["5_day", "10_day"]:
                        linewidth = 1.8  # Increased from 1.2 for better visibility
                        alpha = 0.95  # Increased opacity for better contrast
                    elif period_name in ["20_day", "40_day", "80_day"]:
                        linewidth = 1.5  # Increased from 1.0 for better visibility
                        alpha = 0.9  # Increased opacity
                    else:
                        linewidth = 1.3  # Increased from 0.9 for better visibility
                        alpha = 0.85  # Increased opacity
                    
                    # Plot all waves - don't filter by amplitude (let user see even small waves)
                    # TradingView shows all waves, even if they're small
                    ax.plot(valid_x, valid_values, color=color, linewidth=linewidth, alpha=alpha, label=period_name.replace("_", " ").title())
                    
                    # Log wave amplitude for debugging
                    if wave_range < 1e-6:
                        logger.debug(f"{period_name} has very small amplitude (range: {wave_range:.9f}) - may be hard to see")
    
    # Plot composite - thicker for better AI visibility
    if show_composite and composite:
        valid_indices = [i for i, v in enumerate(composite) if v is not None]
        valid_values = [composite[i] for i in valid_indices]
        valid_x = [x_indices[i] for i in valid_indices]
        if valid_x:
            # Increased linewidth from 1.5 to 2.0 for optimal AI analysis
            ax.plot(valid_x, valid_values, color="#ff6600", linewidth=2.0, alpha=0.95, label="Composite", zorder=10)
            
            # Add numeric annotation for composite oscillator current value
            if valid_indices:
                last_composite_idx = valid_indices[-1]
                last_index = len(x_indices) - 1
                composite_value = composite[last_composite_idx]
                if composite_value is not None:
                    ax.annotate(
                        f"Composite: {composite_value:.6f}",
                        xy=(last_index, float(composite_value)),
                        xytext=(8, 8),
                        textcoords="offset points",
                        fontsize=9,
                        color="#ff6600",
                        fontweight='bold',
                        bbox=dict(boxstyle="round,pad=0.3", facecolor='white', edgecolor="#ff6600", alpha=0.95, linewidth=1.5),
                        ha='left',
                        va='bottom'
        )
    
    # Set Y-axis scale for better wave visibility
    # symlog (symmetric log) is best for values near zero - shows small oscillations clearly
    if y_axis_scale == "symlog":
        # Symmetric log scale: linear near zero, logarithmic away from zero
        # linthresh sets the range around zero that is linear (0.01 = ±0.01 is linear)
        # linscale controls the size of the linear range
        ax.set_yscale('symlog', linthresh=0.01, linscale=0.5)
    elif y_axis_scale == "log":
        # Log scale (only works for positive values)
        # Use abs() to handle negative values, but this distorts the signal
        ax.set_yscale('log')
    else:
        # Linear scale (default)
        ax.set_yscale('linear')
    
    # Plot zero line
    ax.axhline(y=0, color="#888888", linestyle="--", linewidth=0.5, alpha=0.5)
    
    # StockCharts-style grid - clearer but still subtle
    ax.grid(True, alpha=0.7, linestyle='-', linewidth=0.8, color='#c0c0c0', zorder=0)
    ax.set_axisbelow(True)  # Grid behind data
    # Enhance axes edges for better panel separation
    for spine in ax.spines.values():
        spine.set_color('#cccccc')
        spine.set_linewidth(0.8)
    
    if selected_periods or show_composite:
        # TradingView-style compact legend - top left to avoid covering recent data
        ax.legend(fontsize=8, loc="upper left", framealpha=0.9, edgecolor="#cccccc", 
                 fancybox=False, shadow=False, frameon=True, ncol=1, columnspacing=0.5)


def _plot_mesa_stochastic(
    ax: "Axes",
    timestamps: list[int],
    mesa_values: dict[str, list[float]],
    trigger_length: int = 2,
) -> None:
    """Plot MESA Stochastic Multi Length indicator on the given axes."""
    if not timestamps or not mesa_values:
        return
    
    # Light background for better AI visibility
    ax.set_facecolor('#ffffff')
    
    x_indices = list(range(len(timestamps)))
    
    # Color map for different MESA Stochastic lengths
    mesa_colors = {
        "mesa1": "#2196f3",  # blue
        "mesa2": "#4caf50",  # green
        "mesa3": "#ff9800",  # orange
        "mesa4": "#f44336",  # red
    }
    
    # Plot each MESA Stochastic line - thicker for better AI visibility
    for key, values in mesa_values.items():
        if len(values) == len(timestamps):
            color = mesa_colors.get(key, "#888888")
            # Increased linewidth from 1.0 to 1.5 and alpha from 0.85 to 0.9 for better AI analysis
            ax.plot(x_indices, values, color=color, linewidth=1.5, alpha=0.9, label=key.upper())
            
            # Calculate and plot trigger (SMA of MESA Stochastic)
            if trigger_length > 0 and len(values) >= trigger_length:
                import numpy as np
                trigger = []
                for i in range(len(values)):
                    if i >= trigger_length - 1:
                        trigger.append(np.mean(values[i - trigger_length + 1:i + 1]))
                    else:
                        trigger.append(values[i])
                # Increased linewidth and alpha for better AI visibility
                ax.plot(x_indices, trigger, color="#2962ff", linewidth=1.3, alpha=0.8, linestyle="--", label=f"{key} Trigger")
    
    # Add numeric annotations for MESA Stochastic values and triggers - current values at rightmost bar
    if x_indices and mesa_values:
        last_index = len(x_indices) - 1
        annotation_y_offset = 0
        annotation_spacing = 14  # Vertical spacing between annotations (increased to fit MESA + trigger)
        
        # Iterate in order: MESA1, MESA2, MESA3, MESA4 for consistent annotation placement
        for key in ["mesa1", "mesa2", "mesa3", "mesa4"]:
            if key in mesa_values:
                values = mesa_values[key]
                if len(values) == len(x_indices) and last_index < len(values):
                    mesa_value = values[last_index]
                    if mesa_value is not None:
                        color = mesa_colors.get(key, "#888888")
                        
                        # Calculate trigger value if trigger_length > 0
                        trigger_value: float | None = None
                        if trigger_length > 0 and len(values) >= trigger_length:
                            import numpy as np
                            trigger_values = []
                            for i in range(len(values)):
                                if i >= trigger_length - 1:
                                    trigger_values.append(np.mean(values[i - trigger_length + 1:i + 1]))
                                else:
                                    trigger_values.append(values[i])
                            if last_index < len(trigger_values):
                                trigger_value = trigger_values[last_index]
                        
                        # Annotate MESA value with trigger if available
                        if trigger_value is not None:
                            diff = mesa_value - trigger_value
                            diff_symbol = "↑" if diff > 0 else "↓" if diff < 0 else "="
                            # Highlight extreme conditions (>1.0 or <0.0)
                            extreme_note = ""
                            if mesa_value >= 1.0:
                                extreme_note = " [OB]"
                            elif mesa_value <= 0.0:
                                extreme_note = " [OS]"
                            mesa_text = f"{key.upper()}: {mesa_value:.4f}{extreme_note} (Trig: {trigger_value:.4f} {diff_symbol}{abs(diff):.4f})"
                        else:
                            # Still check for extremes even without trigger
                            extreme_note = ""
                            if mesa_value >= 1.0:
                                extreme_note = " [OB]"
                            elif mesa_value <= 0.0:
                                extreme_note = " [OS]"
                            mesa_text = f"{key.upper()}: {mesa_value:.4f}{extreme_note}"
                        
                        # Annotate MESA value - position annotations vertically to avoid overlap
                        ax.annotate(
                            mesa_text,
                            xy=(last_index, float(mesa_value)),
                            xytext=(8, annotation_y_offset),
                            textcoords="offset points",
                            fontsize=8,
                            color=color,
                            fontweight='bold',
                            bbox=dict(boxstyle="round,pad=0.3", facecolor='white', edgecolor=color, alpha=0.95, linewidth=1.5),
                            ha='left',
                            va='center'
            )
                        annotation_y_offset -= annotation_spacing  # Move next annotation down
    
    # Set Y-axis limits (0 to 1 for stochastic)
    ax.set_ylim(-0.1, 1.1)
    
    # Plot zero line and 0.5 line
    ax.axhline(y=0, color="#888888", linestyle="--", linewidth=0.5, alpha=0.5)
    ax.axhline(y=0.5, color="#888888", linestyle="--", linewidth=0.5, alpha=0.5)
    ax.axhline(y=1, color="#888888", linestyle="--", linewidth=0.5, alpha=0.5)
    
    # StockCharts-style grid - clearer but still subtle
    ax.grid(True, alpha=0.7, linestyle='-', linewidth=0.8, color='#c0c0c0', zorder=0)
    ax.set_axisbelow(True)
    # Enhance axes edges for better panel separation
    for spine in ax.spines.values():
        spine.set_color('#cccccc')
        spine.set_linewidth(0.8)
    
    # Legend - top left to avoid covering recent data
    ax.legend(loc='upper left', fontsize=8, framealpha=0.9, fancybox=False, shadow=False, frameon=True, ncol=2, columnspacing=0.5)


def _plot_cco(
    ax: "Axes",
    timestamps: list[int],
    fast_osc: list[float | None],
    slow_osc: list[float | None],
) -> None:
    """Plot Cycle Channel Oscillator (CCO) on the given axes."""
    if not timestamps or not fast_osc or not slow_osc:
        return
    
    # Light background for better AI visibility
    ax.set_facecolor('#ffffff')
    
    x_indices = list(range(len(timestamps)))
    
    # Ensure arrays have same length
    min_len = min(len(fast_osc), len(slow_osc), len(timestamps))
    fast_osc = fast_osc[:min_len]
    slow_osc = slow_osc[:min_len]
    x_indices = x_indices[:min_len]
    
    # Plot reference lines (0.0, 0.5, 1.0)
    ax.axhline(y=0.0, color="#888888", linestyle="--", linewidth=0.5, alpha=0.5, label="LowerLine")
    ax.axhline(y=0.5, color="#888888", linestyle="--", linewidth=0.5, alpha=0.5, label="MidLine")
    ax.axhline(y=1.0, color="#888888", linestyle="--", linewidth=0.5, alpha=0.5, label="UpperLine")
    
    # Fill areas above and below midline
    ax.fill_between(x_indices, 0.0, 0.5, color='red', alpha=0.1, label="Lower Zone")
    ax.fill_between(x_indices, 0.5, 1.0, color='green', alpha=0.1, label="Upper Zone")
    
    # Plot histogram bars for extreme conditions (purple)
    # When slow_osc >= 1.0 or <= 0.0
    for i in range(min_len):
        if slow_osc[i] is not None:
            if slow_osc[i] >= 1.0:
                ax.bar(i, slow_osc[i] - 1.0, bottom=1.0, color='purple', alpha=0.6, width=0.8, label="MediumCycleOB" if i == 0 else "")
            elif slow_osc[i] <= 0.0:
                ax.bar(i, abs(slow_osc[i]), bottom=0.0, color='purple', alpha=0.6, width=0.8, label="MediumCycleOS" if i == 0 else "")
    
    # Plot histogram bars for fast oscillator extremes
    for i in range(min_len):
        if fast_osc[i] is not None:
            if fast_osc[i] >= 1.0:
                ax.bar(i, fast_osc[i] - 1.0, bottom=1.0, color='purple', alpha=0.4, width=0.6, label="ShortCycleOB" if i == 0 else "")
            elif fast_osc[i] <= 0.0:
                ax.bar(i, abs(fast_osc[i]), bottom=0.0, color='purple', alpha=0.4, width=0.6, label="ShortCycleOS" if i == 0 else "")
    
    # Plot oscillator lines
    valid_fast_indices = [i for i, v in enumerate(fast_osc) if v is not None]
    valid_slow_indices = [i for i, v in enumerate(slow_osc) if v is not None]
    
    if valid_fast_indices:
        valid_fast_x = [x_indices[i] for i in valid_fast_indices]
        valid_fast_values = [fast_osc[i] for i in valid_fast_indices]
        ax.plot(valid_fast_x, valid_fast_values, color='red', linewidth=2, alpha=0.9, label="FastOsc")
    
    if valid_slow_indices:
        valid_slow_x = [x_indices[i] for i in valid_slow_indices]
        valid_slow_values = [slow_osc[i] for i in valid_slow_indices]
        ax.plot(valid_slow_x, valid_slow_values, color='green', linewidth=2, alpha=0.9, label="SlowOsc")
    
    # Set Y-axis limits (0 to 1 for oscillator, with some padding for extremes)
    ax.set_ylim(-0.2, 1.4)
    
    # Add numeric annotations for AI analysis - current values at rightmost bar
    if valid_fast_indices and valid_slow_indices:
        last_index = len(x_indices) - 1
        
        # Get current values and previous values for trend detection
        last_fast_idx = valid_fast_indices[-1] if valid_fast_indices else None
        last_slow_idx = valid_slow_indices[-1] if valid_slow_indices else None
        
        # Find previous valid indices for trend detection
        prev_fast_idx = valid_fast_indices[-2] if len(valid_fast_indices) >= 2 else None
        prev_slow_idx = valid_slow_indices[-2] if len(valid_slow_indices) >= 2 else None
        
        if last_fast_idx is not None and fast_osc[last_fast_idx] is not None:
            fast_value = fast_osc[last_fast_idx]
            
            # Detect trend (compare with previous value)
            fast_trend = ""
            if prev_fast_idx is not None and fast_osc[prev_fast_idx] is not None:
                prev_fast = fast_osc[prev_fast_idx]
                if fast_value > prev_fast:
                    fast_trend = " ↑"
                elif fast_value < prev_fast:
                    fast_trend = " ↓"
            
            # Highlight extreme conditions
            extreme_note = ""
            if fast_value >= 1.0:
                extreme_note = " [OB]"
            elif fast_value <= 0.0:
                extreme_note = " [OS]"
            
            # Annotate Fast Osc value - red color to match line
            ax.annotate(
                f"FastOsc: {fast_value:.4f}{extreme_note}{fast_trend}",
                xy=(last_index, float(fast_value)),
                xytext=(8, 8),
                textcoords="offset points",
                fontsize=9,
                color='red',
                fontweight='bold',
                bbox=dict(boxstyle="round,pad=0.3", facecolor='white', edgecolor='red', alpha=0.95, linewidth=1.5),
                ha='left',
                va='bottom'
            )
        
        if last_slow_idx is not None and slow_osc[last_slow_idx] is not None:
            slow_value = slow_osc[last_slow_idx]
            
            # Detect trend (compare with previous value)
            slow_trend = ""
            if prev_slow_idx is not None and slow_osc[prev_slow_idx] is not None:
                prev_slow = slow_osc[prev_slow_idx]
                if slow_value > prev_slow:
                    slow_trend = " ↑"
                elif slow_value < prev_slow:
                    slow_trend = " ↓"
            
            # Highlight extreme conditions
            extreme_note = ""
            if slow_value >= 1.0:
                extreme_note = " [OB]"
            elif slow_value <= 0.0:
                extreme_note = " [OS]"
            
            # Annotate Slow Osc value - green color to match line
            ax.annotate(
                f"SlowOsc: {slow_value:.4f}{extreme_note}{slow_trend}",
                xy=(last_index, float(slow_value)),
                xytext=(8, -8),
                textcoords="offset points",
                fontsize=9,
                color='green',
                fontweight='bold',
                bbox=dict(boxstyle="round,pad=0.3", facecolor='white', edgecolor='green', alpha=0.95, linewidth=1.5),
                ha='left',
                va='top'
            )
    
    # StockCharts-style grid - clearer but still subtle
    ax.grid(True, alpha=0.7, linestyle='-', linewidth=0.8, color='#c0c0c0', zorder=0)
    ax.set_axisbelow(True)
    # Enhance axes edges for better panel separation
    for spine in ax.spines.values():
        spine.set_color('#cccccc')
        spine.set_linewidth(0.8)
    
    # Legend - top left to avoid covering recent data
    ax.legend(loc='upper left', fontsize=8, framealpha=0.9, fancybox=False, shadow=False, frameon=True, ncol=1, columnspacing=0.5)


class HurstPlot(Base):
    """
    Renders OHLCV data with Hurst Spectral Analysis Oscillator waves.
    
    Creates a combined chart with:
    - Top panel: Price OHLC bars
    - Bottom panel: Hurst bandpass waves (selected periods + composite)
    
    Inputs: 'ohlcv_bundle' (Dict[AssetSymbol, List[OHLCVBar]])
    Output: 'images' -> Dict[str, str] mapping label to data URL
    """

    inputs = {
        "ohlcv_bundle": get_type("OHLCVBundle") | None,
    }
    optional_inputs = ["ohlcv_bundle", "ohlcv"]

    outputs = {
        "images": get_type("ConfigDict"),
        "hurst_data": get_type("ConfigDict"),  # Calculated Hurst values (bandpasses, composite, metadata)
        "ohlcv_bundle": get_type("OHLCVBundle"),  # OHLCV bars used for calculation (for AI analysis)
        "mesa_data": get_type("ConfigDict"),  # MESA Stochastic data (when enabled)
        "cco_data": get_type("ConfigDict"),  # Cycle Channel Oscillator data (when enabled)
    }

    CATEGORY = NodeCategory.MARKET
    
    default_params = {
        "max_symbols": 12,
        "lookback_bars": None,
        "zoom_to_recent": False,  # Auto-zoom to last 300 bars for better visibility (~12 days hourly)
        "y_axis_scale": "symlog",  # "symlog" (default) shows full range, "linear" zooms to recent, "log" for exponential growth
        "show_current_price": True,  # Annotate current price on chart
        "source": "hl2",
        "bandwidth": 0.025,
        "dpi": 250,  # Image DPI: 250 for high quality (default), reduce to 150-200 for smaller API payloads
        # Show individual waves (all 11 cycles)
        # Default: Show first 5 cycles for good visibility without clutter
        "show_5_day": True,
        "show_10_day": True,
        "show_20_day": True,  # Changed to True - good for AI analysis
        "show_40_day": True,  # Changed to True - good for AI analysis
        "show_80_day": True,  # Changed to True - good for AI analysis
        "show_20_week": False,  # Enable if you want longer cycles visible
        "show_40_week": False,  # Enable if you want longer cycles visible
        "show_18_month": False,  # Usually too long to see clearly on chart
        "show_54_month": False,  # Usually too long to see clearly on chart
        "show_9_year": False,  # Usually too long to see clearly on chart
        "show_18_year": False,  # Usually too long to see clearly on chart
        "show_composite": True,
        # Composite selection (all 11 cycles)
        "composite_5_day": True,
        "composite_10_day": True,
        "composite_20_day": True,
        "composite_40_day": True,
        "composite_80_day": True,
        "composite_20_week": True,
        "composite_40_week": True,
        "composite_18_month": True,
        "composite_54_month": True,
        "composite_9_year": True,
        "composite_18_year": True,
        # Period parameters (all 11 cycles)
        "period_5_day": 4.3,
        "period_10_day": 8.5,
        "period_20_day": 17.0,
        "period_40_day": 34.1,
        "period_80_day": 68.2,
        "period_20_week": 136.4,
        "period_40_week": 272.8,
        "period_18_month": 545.6,
        "period_54_month": 1636.8,
        "period_9_year": 3273.6,
        "period_18_year": 6547.2,
        # MESA Stochastic parameters
        "show_mesa_stochastic": False,  # On/off switch for MESA Stochastic
        "mesa_length1": 50,  # First MESA Stochastic length
        "mesa_length2": 21,  # Second MESA Stochastic length
        "mesa_length3": 14,  # Third MESA Stochastic length
        "mesa_length4": 9,  # Fourth MESA Stochastic length
        "mesa_trigger_length": 2,  # Trigger SMA length
        # CCO (Cycle Channel Oscillator) parameters
        "show_cco": False,  # On/off switch for CCO
        "cco_short_cycle_length": 10,  # Short cycle length
        "cco_medium_cycle_length": 30,  # Medium cycle length
        "cco_short_cycle_multiplier": 1.0,  # Short cycle multiplier for ATR offset
        "cco_medium_cycle_multiplier": 3.0,  # Medium cycle multiplier for ATR offset
        # Volume-by-Price parameters
        "show_volume_by_price": False,  # On/off switch for Volume-by-Price
        "volume_by_price_bars": 12,  # Number of Volume-by-Price bars (default 12)
        "volume_by_price_color_volume": False,  # Separate up/down volume with colors
        "volume_by_price_opacity": 0.5,  # Opacity of Volume-by-Price bars (0.0 to 1.0) - increased for better visibility
    }
    
    params_meta = [
        {"name": "max_symbols", "type": "integer", "default": 12, "min": 1, "max": 64, "step": 4},
               {
                   "name": "lookback_bars",
                   "type": "number",
                   "default": None,
                   "description": "Number of bars to plot (None = all). Use this to zoom in on recent data while still calculating with full history. Recommended: 500-2000 for better wave visibility.",
                   "min": 10,
                   "max": 10000,
                   "step": 100,
               },
               {
                   "name": "zoom_to_recent",
                   "type": "combo",
                   "default": False,
                   "options": [True, False],
                   "description": "Auto-zoom to last 300 bars (~12 days hourly) for better wave visibility (still calculates with full history)",
               },
               {
                   "name": "y_axis_scale",
                   "type": "combo",
                   "default": "symlog",
                   "options": ["linear", "symlog", "log"],
                   "description": "Y-axis scale: 'symlog' (default) shows full price range, 'linear' zooms to recent prices, 'log' for exponential growth",
               },
               {
                   "name": "show_current_price",
                   "type": "combo",
                   "default": True,
                   "options": [True, False],
                   "description": "Annotate current price on chart for better visibility",
               },
               {
                   "name": "dpi",
                   "type": "number",
                   "default": 250,
                   "min": 100,
                   "max": 300,
                   "step": 50,
                   "description": "Image DPI (dots per inch): 250 for high quality (default), reduce to 150-200 for smaller API payloads when sending many charts",
               },
        {
            "name": "source",
            "type": "combo",
            "default": "hl2",
            "options": ["close", "hl2", "open", "high", "low"],
            "description": "Price source for bandpass filters",
        },
        {
            "name": "bandwidth",
            "type": "number",
            "default": 0.025,
            "min": 0.001,
            "max": 1.0,
            "step": 0.001,
            "description": "Bandwidth parameter",
        },
        {
            "name": "show_5_day",
            "type": "combo",
            "default": True,
            "options": [True, False],
            "description": "Show 5 Day wave",
        },
        {
            "name": "show_10_day",
            "type": "combo",
            "default": True,
            "options": [True, False],
            "description": "Show 10 Day wave",
        },
        {
            "name": "show_20_day",
            "type": "combo",
            "default": True,
            "options": [True, False],
            "description": "Show 20 Day wave",
        },
        {
            "name": "show_40_day",
            "type": "combo",
            "default": True,
            "options": [True, False],
            "description": "Show 40 Day wave",
        },
        {
            "name": "show_80_day",
            "type": "combo",
            "default": True,
            "options": [True, False],
            "description": "Show 80 Day wave",
        },
        {
            "name": "show_20_week",
            "type": "combo",
            "default": False,
            "options": [True, False],
            "description": "Show 20 Week wave",
        },
        {
            "name": "show_40_week",
            "type": "combo",
            "default": False,
            "options": [True, False],
            "description": "Show 40 Week wave",
        },
        {
            "name": "show_18_month",
            "type": "combo",
            "default": False,
            "options": [True, False],
            "description": "Show 18 Month wave",
        },
        {
            "name": "show_54_month",
            "type": "combo",
            "default": False,
            "options": [True, False],
            "description": "Show 54 Month wave",
        },
        {
            "name": "show_9_year",
            "type": "combo",
            "default": False,
            "options": [True, False],
            "description": "Show 9 Year wave",
        },
        {
            "name": "show_18_year",
            "type": "combo",
            "default": False,
            "options": [True, False],
            "description": "Show 18 Year wave",
        },
        {
            "name": "show_composite",
            "type": "combo",
            "default": True,
            "options": [True, False],
            "description": "Show composite wave",
        },
        # Composite selection (all 11 cycles)
        {
            "name": "composite_5_day",
            "type": "boolean",
            "default": True,
            "description": "Include 5 Day in composite",
        },
        {
            "name": "composite_10_day",
            "type": "boolean",
            "default": True,
            "description": "Include 10 Day in composite",
        },
        {
            "name": "composite_20_day",
            "type": "boolean",
            "default": True,
            "description": "Include 20 Day in composite",
        },
        {
            "name": "composite_40_day",
            "type": "boolean",
            "default": True,
            "description": "Include 40 Day in composite",
        },
        {
            "name": "composite_80_day",
            "type": "boolean",
            "default": True,
            "description": "Include 80 Day in composite",
        },
        {
            "name": "composite_20_week",
            "type": "boolean",
            "default": True,
            "description": "Include 20 Week in composite",
        },
        {
            "name": "composite_40_week",
            "type": "boolean",
            "default": True,
            "description": "Include 40 Week in composite",
        },
        {
            "name": "composite_18_month",
            "type": "boolean",
            "default": True,
            "description": "Include 18 Month in composite",
        },
        {
            "name": "composite_54_month",
            "type": "boolean",
            "default": True,
            "description": "Include 54 Month in composite",
        },
        {
            "name": "composite_9_year",
            "type": "boolean",
            "default": True,
            "description": "Include 9 Year in composite",
        },
        {
            "name": "composite_18_year",
            "type": "boolean",
            "default": True,
            "description": "Include 18 Year in composite",
        },
        # Period parameters (all 11 cycles)
        {
            "name": "period_5_day",
            "type": "number",
            "default": 4.3,
            "min": 2.0,
            "step": 0.1,
            "description": "5 Day period (bars)",
        },
        {
            "name": "period_10_day",
            "type": "number",
            "default": 8.5,
            "min": 2.0,
            "step": 0.1,
            "description": "10 Day period (bars)",
        },
        {
            "name": "period_20_day",
            "type": "number",
            "default": 17.0,
            "min": 2.0,
            "step": 0.1,
            "description": "20 Day period (bars)",
        },
        {
            "name": "period_40_day",
            "type": "number",
            "default": 34.1,
            "min": 2.0,
            "step": 0.1,
            "description": "40 Day period (bars)",
        },
        {
            "name": "period_80_day",
            "type": "number",
            "default": 68.2,
            "min": 2.0,
            "step": 0.1,
            "description": "80 Day period (bars)",
        },
        {
            "name": "period_20_week",
            "type": "number",
            "default": 136.4,
            "min": 2.0,
            "step": 0.1,
            "description": "20 Week period (bars)",
        },
        {
            "name": "period_40_week",
            "type": "number",
            "default": 272.8,
            "min": 2.0,
            "step": 0.1,
            "description": "40 Week period (bars)",
        },
        {
            "name": "period_18_month",
            "type": "number",
            "default": 545.6,
            "min": 2.0,
            "step": 0.1,
            "description": "18 Month period (bars)",
        },
        {
            "name": "period_54_month",
            "type": "number",
            "default": 1636.8,
            "min": 2.0,
            "step": 0.1,
            "description": "54 Month period (bars)",
        },
        {
            "name": "period_9_year",
            "type": "number",
            "default": 3273.6,
            "min": 2.0,
            "step": 0.1,
            "description": "9 Year period (bars)",
        },
        {
            "name": "period_18_year",
            "type": "number",
            "default": 6547.2,
            "min": 2.0,
            "step": 0.1,
            "description": "18 Year period (bars)",
        },
        # MESA Stochastic parameters
        {
            "name": "show_mesa_stochastic",
            "type": "combo",
            "default": False,
            "options": [True, False],
            "description": "Show MESA Stochastic indicator below Hurst waves",
        },
        # CCO (Cycle Channel Oscillator) parameters
        {
            "name": "show_cco",
            "type": "combo",
            "default": False,
            "options": [True, False],
            "description": "Show Cycle Channel Oscillator (CCO) indicator",
        },
        {
            "name": "cco_short_cycle_length",
            "type": "integer",
            "default": 10,
            "min": 2,
            "max": 100,
            "step": 1,
            "description": "CCO Short cycle length",
        },
        {
            "name": "cco_medium_cycle_length",
            "type": "integer",
            "default": 30,
            "min": 2,
            "max": 200,
            "step": 1,
            "description": "CCO Medium cycle length",
        },
        {
            "name": "cco_short_cycle_multiplier",
            "type": "number",
            "default": 1.0,
            "min": 0.1,
            "max": 10.0,
            "step": 0.1,
            "description": "CCO Short cycle multiplier for ATR offset",
        },
        {
            "name": "cco_medium_cycle_multiplier",
            "type": "number",
            "default": 3.0,
            "min": 0.1,
            "max": 10.0,
            "step": 0.1,
            "description": "CCO Medium cycle multiplier for ATR offset",
        },
        {
            "name": "mesa_length1",
            "type": "number",
            "default": 50,
            "min": 2,
            "max": 200,
            "step": 1,
            "description": "MESA Stochastic Length 1",
        },
        {
            "name": "mesa_length2",
            "type": "number",
            "default": 21,
            "min": 2,
            "max": 200,
            "step": 1,
            "description": "MESA Stochastic Length 2",
        },
        {
            "name": "mesa_length3",
            "type": "number",
            "default": 14,
            "min": 2,
            "max": 200,
            "step": 1,
            "description": "MESA Stochastic Length 3",
        },
        {
            "name": "mesa_length4",
            "type": "number",
            "default": 9,
            "min": 2,
            "max": 200,
            "step": 1,
            "description": "MESA Stochastic Length 4",
        },
        {
            "name": "mesa_trigger_length",
            "type": "number",
            "default": 2,
            "min": 1,
            "max": 20,
            "step": 1,
            "description": "MESA Stochastic Trigger SMA Length",
        },
        # Volume-by-Price parameters
        {
            "name": "show_volume_by_price",
            "type": "combo",
            "default": False,
            "options": [True, False],
            "description": "Show Volume-by-Price bars on the left side of the price chart",
        },
        {
            "name": "volume_by_price_bars",
            "type": "number",
            "default": 12,
            "min": 4,
            "max": 50,
            "step": 1,
            "description": "Number of Volume-by-Price bars (default 12, matching StockCharts)",
        },
        {
            "name": "volume_by_price_color_volume",
            "type": "combo",
            "default": False,
            "options": [True, False],
            "description": "Separate up volume (green) and down volume (red) in Volume-by-Price bars",
        },
        {
            "name": "volume_by_price_opacity",
            "type": "number",
            "default": 0.5,
            "min": 0.1,
            "max": 1.0,
            "step": 0.1,
            "description": "Opacity of Volume-by-Price bars (0.0 to 1.0) - higher values make bars more visible",
        },
    ]

    async def _execute_impl(self, inputs: dict[str, Any]) -> dict[str, Any]:
        bundle: dict[AssetSymbol, list[OHLCVBar]] | None = inputs.get("ohlcv_bundle")
        single_bundle: dict[AssetSymbol, list[OHLCVBar]] | None = inputs.get("ohlcv")

        # Merge both inputs if both provided
        if bundle and single_bundle:
            bundle = {**bundle, **single_bundle}
        elif single_bundle:
            bundle = single_bundle

        if not bundle:
            raise NodeValidationError(self.id, "Provide either 'ohlcv_bundle' or 'ohlcv'")

        lookback_raw = self.params.get("lookback_bars")
        lookback: int | None = None
        if lookback_raw is not None:
            if isinstance(lookback_raw, (int, float, str)):
                try:
                    lookback = int(lookback_raw)
                except (ValueError, TypeError):
                    lookback = None

        images: dict[str, str] = {}
        hurst_data_by_symbol: dict[str, dict[str, Any]] = {}  # Store Hurst data per symbol
        ohlcv_bundle_output: dict[AssetSymbol, list[OHLCVBar]] = {}  # Store bars used for calculation
        mesa_data_by_symbol: dict[str, dict[str, Any]] = {}  # Store MESA Stochastic data per symbol
        cco_data_by_symbol: dict[str, dict[str, Any]] = {}  # Store CCO data per symbol

        # Limit symbols for safety
        max_syms_raw = self.params.get("max_symbols") or 12
        max_syms = 12
        if isinstance(max_syms_raw, (int, float, str)):
            try:
                max_syms = int(max_syms_raw)
            except (ValueError, TypeError):
                max_syms = 12

        # Get Hurst parameters
        source_raw = self.params.get("source", "hl2")
        source = str(source_raw) if source_raw else "hl2"
        bandwidth_raw = self.params.get("bandwidth", 0.025)
        bandwidth = float(bandwidth_raw) if bandwidth_raw is not None else 0.025
        
        # Build periods dict (all 11 cycles)
        periods = {
            "5_day": float(self.params.get("period_5_day", 4.3)),
            "10_day": float(self.params.get("period_10_day", 8.5)),
            "20_day": float(self.params.get("period_20_day", 17.0)),
            "40_day": float(self.params.get("period_40_day", 34.1)),
            "80_day": float(self.params.get("period_80_day", 68.2)),
            "20_week": float(self.params.get("period_20_week", 136.4)),
            "40_week": float(self.params.get("period_40_week", 272.8)),
            "18_month": float(self.params.get("period_18_month", 545.6)),
            "54_month": float(self.params.get("period_54_month", 1636.8)),
            "9_year": float(self.params.get("period_9_year", 3273.6)),
            "18_year": float(self.params.get("period_18_year", 6547.2)),
        }
        
        # Build composite selection dict (all 11 cycles)
        composite_selection = {
            "5_day": bool(self.params.get("composite_5_day", True)),
            "10_day": bool(self.params.get("composite_10_day", True)),
            "20_day": bool(self.params.get("composite_20_day", True)),
            "40_day": bool(self.params.get("composite_40_day", True)),
            "80_day": bool(self.params.get("composite_80_day", True)),
            "20_week": bool(self.params.get("composite_20_week", True)),
            "40_week": bool(self.params.get("composite_40_week", True)),
            "18_month": bool(self.params.get("composite_18_month", True)),
            "54_month": bool(self.params.get("composite_54_month", True)),
            "9_year": bool(self.params.get("composite_9_year", True)),
            "18_year": bool(self.params.get("composite_18_year", True)),
        }
        
        # Determine which periods to show (all 11 cycles)
        # Use defaults from default_params to match the updated defaults
        show_periods = []
        if self.params.get("show_5_day", self.default_params.get("show_5_day", True)):
            show_periods.append("5_day")
        if self.params.get("show_10_day", self.default_params.get("show_10_day", True)):
            show_periods.append("10_day")
        if self.params.get("show_20_day", self.default_params.get("show_20_day", True)):
            show_periods.append("20_day")
        if self.params.get("show_40_day", self.default_params.get("show_40_day", True)):
            show_periods.append("40_day")
        if self.params.get("show_80_day", self.default_params.get("show_80_day", True)):
            show_periods.append("80_day")
        if self.params.get("show_20_week", self.default_params.get("show_20_week", False)):
            show_periods.append("20_week")
        if self.params.get("show_40_week", self.default_params.get("show_40_week", False)):
            show_periods.append("40_week")
        if self.params.get("show_18_month", self.default_params.get("show_18_month", False)):
            show_periods.append("18_month")
        if self.params.get("show_54_month", self.default_params.get("show_54_month", False)):
            show_periods.append("54_month")
        if self.params.get("show_9_year", self.default_params.get("show_9_year", False)):
            show_periods.append("9_year")
        if self.params.get("show_18_year", self.default_params.get("show_18_year", False)):
            show_periods.append("18_year")
        
        show_composite = bool(self.params.get("show_composite", True))

        items = list(bundle.items())[:max_syms]
        for sym, bars in items:
            if not bars:
                logger.warning(f"⚠️ HurstPlot: No bars provided for {sym}")
                continue
            
            logger.warning(f"🔵 HurstPlot: Processing {sym}: received {len(bars)} bars")
            
            # Log first and last bar timestamps to verify snapshot injection
            if len(bars) > 0:
                first_bar_ts = bars[0].get("timestamp", 0)
                last_bar_ts = bars[-1].get("timestamp", 0)
                first_bar_dt = datetime.fromtimestamp(first_bar_ts / 1000) if first_bar_ts else None
                last_bar_dt = datetime.fromtimestamp(last_bar_ts / 1000) if last_bar_ts else None
                current_time = datetime.now()
                if last_bar_dt:
                    age_minutes = (current_time - last_bar_dt.replace(tzinfo=None)).total_seconds() / 60
                    logger.warning(f"🔵 HurstPlot: {sym} input bars - First: {first_bar_dt}, Last: {last_bar_dt}, Age: {age_minutes:.1f} min")
                
            norm, volumes = _normalize_bars(bars)
            logger.warning(f"🔵 HurstPlot: Normalized {sym}: {len(norm)} bars after normalization")
            
            # Verify bars are sorted correctly (oldest to newest)
            if len(norm) > 1:
                first_ts = norm[0][0]
                last_ts = norm[-1][0]
                if first_ts > last_ts:
                    logger.error(f"Bars are NOT sorted correctly for {sym}! First timestamp {first_ts} > Last timestamp {last_ts}")
                    # Reverse to fix (shouldn't happen, but safety check)
                    norm = list(reversed(norm))
                    logger.warning(f"Reversed bars for {sym} to fix sorting")
                logger.info(f"Bar timestamp range for {sym}: {first_ts} to {last_ts} ({len(norm)} bars)")
            
            # Store full history for calculation
            full_norm = norm
            
            # Log first and last few bars to verify data correctness
            if len(norm) > 0:
                logger.info(f"Data verification for {sym}:")
                logger.info(f"  First 3 bars (oldest):")
                for i in range(min(3, len(norm))):
                    ts, o, h, l, c = norm[i]
                    ts_dt = datetime.fromtimestamp(ts / 1000)
                    logger.info(f"    Bar {i}: ts={ts} ({ts_dt}), O={o:.4f}, H={h:.4f}, L={l:.4f}, C={c:.4f}")
                logger.info(f"  Last 3 bars (newest):")
                for i in range(max(0, len(norm) - 3), len(norm)):
                    ts, o, h, l, c = norm[i]
                    ts_dt = datetime.fromtimestamp(ts / 1000)
                    logger.info(f"    Bar {i}: ts={ts} ({ts_dt}), O={o:.4f}, H={h:.4f}, L={l:.4f}, C={c:.4f}")
            
            # Apply lookback for display (zoom in) while keeping full history for calculation
            # IMPORTANT: Always ensure the most recent bar (which may be snapshot-injected) is included
            zoom_to_recent = bool(self.params.get("zoom_to_recent", False))
            
            # Log the snapshot bar BEFORE filtering to verify it exists
            if len(norm) > 0:
                snapshot_bar_ts = norm[-1][0]
                snapshot_bar_dt = datetime.fromtimestamp(snapshot_bar_ts / 1000)
                current_time = datetime.now()
                snapshot_age_minutes = (current_time - snapshot_bar_dt.replace(tzinfo=None)).total_seconds() / 60
                logger.warning(f"🔵 HurstPlot: BEFORE lookback filter - Last bar in norm: ts={snapshot_bar_ts} ({snapshot_bar_dt}), age={snapshot_age_minutes:.1f} min, price={norm[-1][4]:.4f}")
            
            # AUTOMATIC SMART LOOKBACK: Choose appropriate display window based on data amount
            # This ensures current prices are always visible regardless of total data amount
            if zoom_to_recent and len(norm) > 300:
                # Auto-zoom to last 300 bars for better visibility (~12 days of hourly data)
                display_norm = norm[-300:]
                # Verify we're getting the MOST RECENT 300 bars
                if len(display_norm) > 0:
                    first_display_ts = display_norm[0][0]
                    first_display_dt = datetime.fromtimestamp(first_display_ts / 1000)
                    logger.warning(f"🔧 Auto-zoom enabled: displaying last 300 bars (out of {len(norm)} total)")
                    logger.warning(f"🔧 Auto-zoom range: First={first_display_dt}, Last=current (should be ~12 days ago for 1hr bars)")
                else:
                    logger.warning(f"🔧 Auto-zoom enabled: displaying last 300 bars (out of {len(norm)} total)")
            elif lookback is not None and lookback > 0:
                # User-specified lookback
                if len(norm) > lookback:
                    display_norm = norm[-lookback:]
                else:
                    display_norm = norm
                logger.warning(f"🔧 User lookback: displaying last {len(display_norm)} bars (requested {lookback}, total {len(norm)})")
            else:
                # SMART DEFAULT: Auto-choose based on total bars to ensure current price visibility
                total_bars = len(norm)
                if total_bars <= 2500:
                    # Small to medium dataset (up to ~104 days of hourly): show ALL
                    # This covers typical 1-3 month lookback periods completely
                    display_norm = norm
                    logger.warning(f"🔧 Smart default: showing ALL {total_bars} bars (full dataset)")
                else:
                    # Very large dataset: cap at 2000 bars (~83 days of hourly)
                    display_norm = norm[-2000:]
                    logger.warning(f"🔧 Smart default (large): showing last 2000 bars (out of {total_bars} total)")
            
            # Always verify the snapshot bar is included (critical for current price visibility)
            # CRITICAL: Ensure snapshot bar is ALWAYS the last bar, removing only duplicates with same timestamp
            if len(display_norm) > 0 and len(norm) > 0:
                snapshot_bar = norm[-1]
                snapshot_ts = snapshot_bar[0]
                snapshot_price = snapshot_bar[4]
                
                # Remove only bars with the EXACT same timestamp as snapshot (duplicates)
                # Keep ALL other bars - they're valid historical data
                display_norm_filtered = [bar for bar in display_norm if bar[0] != snapshot_ts]
                
                # Detect large gaps between last API bar and snapshot bar
                if len(display_norm_filtered) > 0:
                    last_api_bar_ts = display_norm_filtered[-1][0]
                    last_api_bar_price = display_norm_filtered[-1][4]
                    last_api_bar_dt = datetime.fromtimestamp(last_api_bar_ts / 1000)
                    snapshot_dt = datetime.fromtimestamp(snapshot_ts / 1000)
                    gap_hours = (snapshot_ts - last_api_bar_ts) / (1000 * 3600)
                    
                    if gap_hours > 24:
                        logger.error(f"⚠️⚠️⚠️ {sym}: LARGE DATA GAP DETECTED!")
                        logger.error(f"  Last API bar: {last_api_bar_dt} (${last_api_bar_price:.4f})")
                        logger.error(f"  Snapshot bar: {snapshot_dt} (${snapshot_price:.4f})")
                        logger.error(f"  Gap: {gap_hours:.1f} hours ({gap_hours/24:.1f} days)")
                        logger.error(f"  This means Polygon/Massive.com API has no data for this period!")
                        logger.error(f"  Chart will show a jump from {last_api_bar_dt.strftime('%Y-%m-%d')} to {snapshot_dt.strftime('%Y-%m-%d')}")
                
                # Always append snapshot bar, then sort to ensure chronological order
                # (snapshot bar should be last, but sort ensures correctness)
                display_norm = display_norm_filtered + [snapshot_bar]
                display_norm.sort(key=lambda x: x[0])  # Sort by timestamp to ensure chronological order
                
                # Verify snapshot bar is now last
                if len(display_norm) > 0:
                    final_last_ts = display_norm[-1][0]
                    final_last_price = display_norm[-1][4]
                    if final_last_ts == snapshot_ts and final_last_price == snapshot_price:
                        logger.warning(f"✅ Snapshot bar confirmed as last: ts={snapshot_ts}, price=${snapshot_price:.4f}")
                    else:
                        logger.error(f"⚠️⚠️⚠️ SNAPSHOT BAR NOT LAST! Last bar: ts={final_last_ts}, price=${final_last_price:.4f}, Expected: ts={snapshot_ts}, price=${snapshot_price:.4f}")
                else:
                    logger.error(f"⚠️⚠️⚠️ DISPLAY_NORM IS EMPTY AFTER SNAPSHOT ENFORCEMENT!")
            
            # Use full history for Hurst calculation, but display only recent bars
            norm = display_norm
            
            if len(norm) < 10:
                logger.warning(f"Insufficient bars for {sym}: {len(norm)} bars (need at least 10)")
                continue
            
            # Log display range to verify we're showing recent data (WARNING level for visibility)
            if len(norm) > 0:
                display_first_ts = norm[0][0]
                display_last_ts = norm[-1][0]
                display_first_dt = datetime.fromtimestamp(display_first_ts / 1000)
                display_last_dt = datetime.fromtimestamp(display_last_ts / 1000)
                current_time = datetime.now()
                age_minutes = (current_time - display_last_dt.replace(tzinfo=None)).total_seconds() / 60
                logger.warning(f"🔵 HurstPlot: Display range for {sym}:")
                logger.warning(f"🔵   First bar: ts={display_first_ts} ({display_first_dt}), price={norm[0][4]:.4f}")
                logger.warning(f"🔵   Last bar: ts={display_last_ts} ({display_last_dt}), price={norm[-1][4]:.4f}, age={age_minutes:.1f} minutes")
                if age_minutes > 120:
                    logger.warning(f"⚠️⚠️⚠️ {sym}: Last displayed bar is {age_minutes:.1f} minutes old - current prices may not be visible!")
                elif age_minutes < 60:
                    logger.warning(f"✅ {sym}: Last displayed bar is {age_minutes:.1f} minutes old - current prices ARE visible!")
            
            logger.info(f"Calculating Hurst oscillator for {sym} with {len(full_norm)} bars (displaying {len(norm)} bars)")

            # Calculate Hurst oscillator with FULL history for accuracy
            # But only display recent bars for better visibility
            full_closes = [x[4] for x in full_norm]
            full_highs = [x[2] for x in full_norm]
            full_lows = [x[3] for x in full_norm]
            
            # Extract price data for display (recent bars only)
            timestamps = [x[0] for x in display_norm]
            closes = [x[4] for x in display_norm]
            highs = [x[2] for x in display_norm]
            lows = [x[3] for x in display_norm]

            # Calculate Hurst oscillator with FULL history (calculate once, use for both display and output)
            try:
                full_hurst_result = calculate_hurst_oscillator(
                    closes=full_closes,  # Use FULL history for calculation
                    highs=full_highs,
                    lows=full_lows,
                    source=source,
                    bandwidth=bandwidth,
                    periods=periods,
                    composite_selection=composite_selection,
                )
                
                # Store full Hurst data for AI analysis (before slicing for display)
                hurst_data_by_symbol[str(sym)] = {
                    "bandpasses": full_hurst_result.get("bandpasses", {}),
                    "composite": full_hurst_result.get("composite", []),
                    "peaks": full_hurst_result.get("peaks", []),
                    "troughs": full_hurst_result.get("troughs", []),
                    "wavelength": full_hurst_result.get("wavelength"),
                    "amplitude": full_hurst_result.get("amplitude"),
                    "timestamps": [x[0] for x in full_norm],  # Full timestamp range
                    "metadata": {
                        "source": source,
                        "bandwidth": bandwidth,
                        "periods": periods,
                        "composite_selection": composite_selection,
                        "total_bars": len(full_norm),
                        "display_bars": len(norm),
                    }
                }
                
                # Store bars used for calculation (full history)
                ohlcv_bundle_output[sym] = bars  # Original bars from input
                
                # Extract only the recent portion for display
                # IMPORTANT: Both full_norm and Hurst results are sorted by timestamp (oldest first)
                # So the LAST N bars in full_norm correspond to the LAST N values in Hurst results
                full_length = len(full_norm)
                display_length = len(norm)
                start_idx = max(0, full_length - display_length)
                
                # Verify we're slicing correctly - log timestamps to debug
                if full_length > 0 and display_length > 0:
                    full_first_ts = full_norm[0][0] if full_norm else 0
                    full_last_ts = full_norm[-1][0] if full_norm else 0
                    display_first_ts = norm[0][0] if norm else 0
                    display_last_ts = norm[-1][0] if norm else 0
                    logger.info(f"Timestamp alignment check for {sym}:")
                    logger.info(f"  Full history: first={full_first_ts}, last={full_last_ts} (length={full_length})")
                    logger.info(f"  Display range: first={display_first_ts}, last={display_last_ts} (length={display_length})")
                    logger.info(f"  Slicing Hurst results from index {start_idx} to end (should match display range)")
                    
                    # Verify display range matches the end of full range
                    if display_first_ts != full_norm[start_idx][0]:
                        logger.error(f"MISMATCH: Display first timestamp {display_first_ts} != Full[{start_idx}] timestamp {full_norm[start_idx][0]}")
                    if display_last_ts != full_last_ts:
                        logger.error(f"MISMATCH: Display last timestamp {display_last_ts} != Full last timestamp {full_last_ts}")
                
                # Slice bandpasses and composite to match display range (for chart only)
                # The Hurst results are in the same order as full_norm (oldest to newest)
                # So we take the last display_length values
                hurst_result = {
                    "bandpasses": {},
                    "composite": full_hurst_result.get("composite", [])[start_idx:] if "composite" in full_hurst_result else [],
                }
                for period_name in full_hurst_result.get("bandpasses", {}):
                    original_length = len(full_hurst_result["bandpasses"][period_name])
                    if original_length != full_length:
                        logger.warning(f"Length mismatch for {period_name}: Hurst result has {original_length} values but full_norm has {full_length}")
                    hurst_result["bandpasses"][period_name] = full_hurst_result["bandpasses"][period_name][start_idx:]
            except Exception as e:
                logger.error(f"Error calculating Hurst for {sym}: {e}", exc_info=True)
                continue

            bandpasses = hurst_result.get("bandpasses", {})
            composite = hurst_result.get("composite", [])
            
            # Log which bandpasses have valid data and their value ranges
            logger.info(f"Hurst calculation for {sym}:")
            logger.info(f"  Composite: {len(composite)} values ({sum(1 for v in composite if v is not None)} non-None)")
            for period_name, values in bandpasses.items():
                non_none_values = [v for v in values if v is not None]
                non_none_count = len(non_none_values)
                if non_none_count > 0:
                    min_val = min(non_none_values)
                    max_val = max(non_none_values)
                    mean_val = sum(non_none_values) / non_none_count
                    logger.info(f"  {period_name}: {len(values)} values ({non_none_count} non-None), range: [{min_val:.6f}, {max_val:.6f}], mean: {mean_val:.6f}")
                else:
                    logger.warning(f"  {period_name}: {len(values)} values (0 non-None) - NO VALID DATA!")
            
            logger.info(f"Showing periods: {show_periods}")
            logger.info(f"Showing composite: {show_composite}")
            
            # Warn if expected waves are missing
            expected_waves = ["5_day", "10_day", "20_day", "40_day", "80_day"]
            missing_waves = [w for w in expected_waves if w not in show_periods]
            if missing_waves:
                logger.warning(f"Expected waves not showing: {missing_waves}. Check node parameters show_*_day settings.")

            # Check if MESA Stochastic and CCO are enabled
            show_mesa = bool(self.params.get("show_mesa_stochastic", False))
            show_cco = bool(self.params.get("show_cco", False))
            
            # Create figure with appropriate number of subplots
            # Layout: Price -> Hurst -> MESA (if enabled) -> CCO (if enabled)
            ax3: "Axes | None" = None
            ax4: "Axes | None" = None
            
            num_subplots = 2  # Price + Hurst (always)
            if show_mesa:
                num_subplots += 1
            if show_cco:
                num_subplots += 1
            
            # Increased figure sizes for better detail and AI analysis
            # Larger width (12 vs 10) provides more horizontal space for last candle visibility
            # Maintain aspect ratios but with more pixels for sharper rendering
            # StockCharts-style spacing: increased hspace and better panel separation
            # Price chart (ax1) is 125% bigger than indicator panels (2.25 vs 1.0) for better visibility
            # Top spacing increased significantly to accommodate titles above charts (completely outside)
            if num_subplots == 2:
                fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 9.75), sharex=True, height_ratios=[2.25, 1.0])
                fig.subplots_adjust(hspace=0.20, top=0.88, bottom=0.07, left=0.08, right=0.95)  # More top space for titles
            elif num_subplots == 3:
                if show_mesa:
                    fig, (ax1, ax2, ax3) = plt.subplots(3, 1, figsize=(12, 11.5), sharex=True, height_ratios=[2.25, 1.0, 1.0])
                else:  # show_cco
                    fig, (ax1, ax2, ax4) = plt.subplots(3, 1, figsize=(12, 11.5), sharex=True, height_ratios=[2.25, 1.0, 1.0])
                fig.subplots_adjust(hspace=0.18, top=0.88, bottom=0.07, left=0.08, right=0.95)  # More top space for titles
            else:  # num_subplots == 4 (both MESA and CCO)
                fig, (ax1, ax2, ax3, ax4) = plt.subplots(4, 1, figsize=(12, 13.5), sharex=True, height_ratios=[2.25, 1.0, 1.0, 1.0])
                fig.subplots_adjust(hspace=0.15, top=0.88, bottom=0.07, left=0.08, right=0.95)  # More top space for titles
            
            # Apply StockCharts-style panel separation to all axes
            all_axes = [ax1, ax2]
            if ax3:
                all_axes.append(ax3)
            if ax4:
                all_axes.append(ax4)
            
            for ax in all_axes:
                # StockCharts-style clean panel boundaries
                for spine in ax.spines.values():
                    spine.set_color('#cccccc')
                    spine.set_linewidth(0.8)
                # Ensure grid is clearly visible and consistent
                ax.grid(True, alpha=0.7, linestyle='-', linewidth=0.8, color='#c0c0c0', zorder=0)
                ax.set_axisbelow(True)

            # Get Y-axis scale parameter BEFORE plotting
            y_axis_scale_raw = self.params.get("y_axis_scale", "linear")  # Default to linear
            y_axis_scale = str(y_axis_scale_raw) if y_axis_scale_raw else "linear"
            if y_axis_scale not in ["linear", "symlog", "log"]:
                y_axis_scale = "linear"  # Default to linear if invalid

            # Top panel: Price candlesticks
            # CRITICAL: Verify snapshot bar is last before plotting
            fresh_price: float | None = None
            if len(display_norm) > 0:
                last_bar_price = display_norm[-1][4]
                last_bar_ts = display_norm[-1][0]
                last_bar_dt = datetime.fromtimestamp(last_bar_ts / 1000)
                
                # Fetch fresh snapshot right before plotting to ensure current price
                try:
                    api_key = APIKeyVault().get("POLYGON_API_KEY")
                    if api_key:
                        fresh_price, _ = await fetch_current_snapshot(sym, api_key)
                        if fresh_price and fresh_price > 0:
                            logger.warning(f"🔄 Fresh snapshot for {sym}: ${fresh_price:.4f} (bar had ${last_bar_price:.4f})")
                        else:
                            logger.warning(f"⚠️ Failed to fetch fresh snapshot for {sym}, using bar price ${last_bar_price:.4f}")
                            fresh_price = None
                    else:
                        logger.warning(f"⚠️ No API key available for fresh snapshot, using bar price ${last_bar_price:.4f}")
                except Exception as e:
                    logger.warning(f"⚠️ Error fetching fresh snapshot for {sym}: {e}, using bar price ${last_bar_price:.4f}")
                    fresh_price = None
                
                # Log last 3 bars to see what's actually being plotted
                if len(display_norm) >= 3:
                    logger.warning(f"🎯 Plotting {sym}: Last 3 bars:")
                    for i, bar in enumerate(display_norm[-3:]):
                        bar_ts, _bar_o, _bar_h, _bar_l, bar_c = bar
                        bar_dt = datetime.fromtimestamp(bar_ts / 1000)
                        logger.warning(f"  Bar {len(display_norm)-3+i}: ts={bar_ts} ({bar_dt}), price=${bar_c:.4f}")
                logger.warning(f"🎯 Plotting {sym}: Last bar price=${last_bar_price:.4f}, ts={last_bar_ts} ({last_bar_dt}) (this should match current price)")
            
            show_current_price = bool(self.params.get("show_current_price", True))
            # Get corresponding volume data for display
            display_volumes = volumes[-len(display_norm):] if len(volumes) >= len(display_norm) else volumes
            
            # Calculate EMAs efficiently: use display bars + warm-up for longest EMA period
            # This ensures EMAs are initialized and visible from the start of displayed chart
            # IMPORTANT: StockCharts calculates EMAs on completed bars only
            # For hourly bars: if current time is 15:55, the last completed bar is 14:00-15:00 (timestamp 15:00:00)
            # The snapshot bar (if it exists) represents the current hour 15:00-16:00 and should NOT be used for EMA
            longest_ema_period = 100
            ema_warmup_bars = len(display_norm) + longest_ema_period  # Display bars + warm-up (e.g., 300 + 100 = 400)
            
            # Determine the last completed bar timestamp
            # StockCharts convention: For hourly bars, a bar with timestamp 15:00:00 represents hour 14:00-15:00 (completed at 15:00)
            # If current time is 15:55, the snapshot bar has timestamp 15:00:00 but represents the CURRENT hour (15:00-16:00) which is NOT completed
            # The last COMPLETED bar would be timestamp 14:00:00 (representing 13:00-14:00, completed at 14:00)
            # OR if the last API bar has timestamp 15:00:00, it might be the completed bar for 14:00-15:00
            # We need to check: if current time is within an hour (e.g., 15:55), bars with timestamp >= current_hour_start are NOT completed
            
            current_time = datetime.now()
            current_hour_start = current_time.replace(minute=0, second=0, microsecond=0)
            current_hour_start_ts = int(current_hour_start.timestamp() * 1000)
            
            # For hourly bars: if current time is 15:55 (within hour 15:00-16:00)
            # - Bars with timestamp 15:00:00 could be EITHER:
            #   1. Completed bar for 14:00-15:00 (if it came from API)
            #   2. Snapshot bar for current hour 15:00-16:00 (if it's a snapshot)
            # - We need to exclude snapshot bars (which are always the last bar if they exist)
            # - The safest approach: exclude the last bar if it has the same timestamp as current hour start
            #   AND if there are multiple bars with that timestamp, exclude all but the first one
            
            # Find completed bars: exclude bars that are clearly for future hours
            # AND exclude the last bar if it's a snapshot (has timestamp matching current hour start)
            completed_bars = []
            last_bar_ts = full_norm[-1][0] if len(full_norm) > 0 else None
            
            for i, bar in enumerate(full_norm):
                bar_ts = bar[0]
                # Exclude bars for future hours
                if bar_ts > current_hour_start_ts:
                    break
                
                # If this is the last bar AND it has timestamp matching current hour start, it's likely a snapshot
                # Exclude it from EMA calculation (StockCharts doesn't use intra-bar prices for EMA)
                if i == len(full_norm) - 1 and bar_ts == current_hour_start_ts:
                    # This is the snapshot bar - exclude it
                    break
                
                completed_bars.append(bar)
            
            # Fallback: if no bars found, use all bars except the last one
            if len(completed_bars) == 0:
                completed_bars = full_norm[:-1] if len(full_norm) > 1 else full_norm
            
            ema_calculation_bars = min(ema_warmup_bars, len(completed_bars))
            
            # Get the last N completed bars for EMA calculation
            ema_calc_norm = completed_bars[-ema_calculation_bars:] if len(completed_bars) > ema_calculation_bars else completed_bars
            ema_calc_closes = [bar[4] for bar in ema_calc_norm]
            
            # Calculate EMAs on this subset
            ema_10_result = calculate_ema(ema_calc_closes, period=10) if len(ema_calc_closes) >= 10 else {"ema": []}
            ema_30_result = calculate_ema(ema_calc_closes, period=30) if len(ema_calc_closes) >= 30 else {"ema": []}
            ema_100_result = calculate_ema(ema_calc_closes, period=100) if len(ema_calc_closes) >= 100 else {"ema": []}
            calc_ema_10 = ema_10_result.get("ema", [])
            calc_ema_30 = ema_30_result.get("ema", [])
            calc_ema_100 = ema_100_result.get("ema", [])
            
            # Slice EMAs to match display_norm (take last len(display_norm) values)
            # Since EMAs are calculated on completed bars (excluding snapshot), we need to handle the snapshot bar
            # StockCharts behavior: EMA stays at last completed bar's value until bar closes
            if len(display_norm) > 0:
                # Get EMA values for completed bars that match display_norm (excluding snapshot)
                completed_display_norm = display_norm[:-1] if len(display_norm) > 1 else []
                completed_display_count = len(completed_display_norm)
                
                if completed_display_count > 0:
                    # Get EMA values for the completed bars in display range
                    display_ema_10_completed = calc_ema_10[-completed_display_count:] if len(calc_ema_10) >= completed_display_count else []
                    display_ema_30_completed = calc_ema_30[-completed_display_count:] if len(calc_ema_30) >= completed_display_count else []
                    display_ema_100_completed = calc_ema_100[-completed_display_count:] if len(calc_ema_100) >= completed_display_count else []
                    
                    # Extend EMAs to include snapshot bar position (use last EMA value for snapshot bar)
                    # This matches StockCharts behavior: EMA stays at last completed bar's value until bar closes
                    display_ema_10 = display_ema_10_completed + ([display_ema_10_completed[-1]] if display_ema_10_completed else [None])
                    display_ema_30 = display_ema_30_completed + ([display_ema_30_completed[-1]] if display_ema_30_completed else [None])
                    display_ema_100 = display_ema_100_completed + ([display_ema_100_completed[-1]] if display_ema_100_completed else [None])
                else:
                    # No completed bars in display range, use empty lists
                    display_ema_10 = []
                    display_ema_30 = []
                    display_ema_100 = []
            else:
                display_ema_10 = []
                display_ema_30 = []
                display_ema_100 = []
            
            # Get Volume-by-Price parameters
            show_vbp = bool(self.params.get("show_volume_by_price", False))
            vbp_bars = int(self.params.get("volume_by_price_bars", 12))
            vbp_color_volume = bool(self.params.get("volume_by_price_color_volume", False))
            vbp_opacity = float(self.params.get("volume_by_price_opacity", 0.3))
            
            _plot_candles(
                ax1, display_norm, display_volumes, display_ema_10, display_ema_30, display_ema_100,
                show_current_price, current_price_override=fresh_price,
                show_volume_by_price=show_vbp,
                volume_by_price_bars=vbp_bars,
                volume_by_price_color_volume=vbp_color_volume,
                volume_by_price_opacity=vbp_opacity,
            )
            ax1.set_title(f"{str(sym)} Price Chart", fontsize=12, fontweight='bold', pad=10)
            ax1.set_ylabel("Price", fontsize=10)
            
            # Enable Y-axis ticks and format price labels with $ symbol
            ax1.tick_params(axis='y', labelsize=9, which='major', left=True, labelleft=True)
            
            # Format Y-axis price labels to be more readable (with $ symbol)
            # Show 4 decimal places for prices < $1, 2 decimal places for prices >= $1
            ax1.yaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda x, p: f'${x:.4f}' if x < 1 else f'${x:.2f}'))  # type: ignore
            
            # Ensure Y-axis ticks are visible
            ax1.yaxis.set_ticks_position('left')
            ax1.tick_params(axis='y', direction='out', length=4, width=1)
            
            # Apply Y-axis scale to price chart
            try:
                ax1.set_yscale(y_axis_scale)
            except Exception as e:
                logger.warning(f"Failed to set y_axis_scale '{y_axis_scale}': {e}. Using linear.")
                ax1.set_yscale("linear")
            
            # Set Y-axis limits with padding to ensure price visibility
            # STRATEGY: For linear scale, use recent bars to focus on current price
            #           For log/symlog scale, use FULL range to show all historical data
            if len(display_norm) > 0:
                # Get current price (last bar close) - this is the most recent snapshot price
                current_price = display_norm[-1][4]
                
                # Get full dataset range
                all_prices = [bar[1] for bar in display_norm] + [bar[2] for bar in display_norm] + [bar[3] for bar in display_norm] + [bar[4] for bar in display_norm]
                full_min = min(all_prices)
                full_max = max(all_prices)
                
                # Use different strategies based on Y-axis scale
                if y_axis_scale in ["log", "symlog"]:
                    # For logarithmic scales, use FULL range to show all bars
                    # Log scale naturally compresses high values and expands low values
                    padding = (full_max - full_min) * 0.05  # 5% padding on full range
                    y_min = max(full_min - padding, full_min * 0.95)
                    y_max = full_max + padding
                    
                    # Ensure positive values for log scale
                    if y_axis_scale == "log":
                        y_min = max(y_min, 0.01)
                    
                    logger.warning(f"📊 {str(sym)} Y-axis range: ${y_min:.4f} to ${y_max:.4f} (FULL range for {y_axis_scale} scale, current: ${current_price:.4f})")
                else:
                    # For linear scale, focus on recent bars to emphasize current price
                    # Use last 30 bars to establish recent price range (last ~30 hours for hourly data)
                    recent_bar_count = min(30, max(10, int(len(display_norm) * 0.05)))
                    recent_bars = display_norm[-recent_bar_count:]
                    
                    # Calculate recent price range
                    recent_prices = [bar[1] for bar in recent_bars] + [bar[2] for bar in recent_bars] + [bar[3] for bar in recent_bars] + [bar[4] for bar in recent_bars]
                    recent_min = min(recent_prices)
                    recent_max = max(recent_prices)
                    recent_range = recent_max - recent_min
                    
                    # Calculate Y-axis: Use recent range but ensure current price is visible
                    # If current price is near the top of recent range, extend upward
                    # If current price is below recent range, extend downward
                    if current_price >= recent_max * 0.95:
                        # Current price is near top - extend upward more
                        y_max = current_price * 1.10  # 10% above current
                        y_min = recent_min * 0.95  # 5% below recent min
                    elif current_price <= recent_min * 1.05:
                        # Current price is near bottom - extend downward more
                        y_min = current_price * 0.90  # 10% below current
                        y_max = recent_max * 1.05  # 5% above recent max
                    else:
                        # Current price is in middle - use recent range with padding
                        padding = max(recent_range * 0.20, current_price * 0.05)  # 20% of range or 5% of price
                        y_min = recent_min - padding
                        y_max = recent_max + padding
                    
                    # Ensure current price is always visible (add extra space if needed)
                    if current_price > y_max * 0.95:
                        y_max = current_price * 1.10
                    if current_price < y_min * 1.05:
                        y_min = current_price * 0.90
                    
                    # Ensure we don't go below 0
                    y_min = max(y_min, 0.01 * current_price)
                    
                    logger.warning(f"📊 {str(sym)} Y-axis range: ${y_min:.4f} to ${y_max:.4f} (current: ${current_price:.4f}, recent: ${recent_min:.4f}-${recent_max:.4f}, full: ${full_min:.4f}-${full_max:.4f}, using last {recent_bar_count} bars)")
                
                ax1.set_ylim(y_min, y_max)
            
            # Bottom panel: Hurst waves
            _plot_hurst_waves(ax2, timestamps, bandpasses, composite, show_periods, show_composite, y_axis_scale)
            ax2.set_title(f"{str(sym)} Hurst Spectral Analysis Oscillator", fontsize=12, fontweight='bold', pad=10)
            ax2.set_ylabel("Hurst Oscillator", fontsize=10)
            ax2.tick_params(labelsize=9)
            
            # Set time x-axis labels only on bottommost panel (will be shared via sharex=True)
            bottom_ax = ax4 if ax4 else (ax3 if ax3 else ax2)
            if len(display_norm) > 0:
                timestamps_for_labels = [x[0] for x in display_norm]
                try:
                    # Convert timestamps (ms) to datetime objects
                    dates = [datetime.fromtimestamp(ts / 1000) for ts in timestamps_for_labels]
                    
                    if len(dates) > 0:
                        # Use a subset of dates for labels to avoid crowding
                        num_labels = min(8, len(dates))  # Max 8 labels
                        if num_labels > 1:
                            step = max(1, len(dates) // num_labels)
                            label_indices = list(range(0, len(dates), step))
                            if len(dates) - 1 not in label_indices:
                                label_indices.append(len(dates) - 1)  # Always include last
                            
                            label_positions = label_indices
                            label_dates = [dates[i] for i in label_indices]
                            
                            # Format dates based on time range
                            time_span = (dates[-1] - dates[0]).total_seconds()
                            if time_span < 86400 * 2:  # Less than 2 days - show hours
                                date_labels = [d.strftime("%H:%M") for d in label_dates]
                            elif time_span < 86400 * 30:  # Less than 30 days - show day/month
                                date_labels = [d.strftime("%d/%m") for d in label_dates]
                            else:  # Longer - show month/year
                                date_labels = [d.strftime("%b %Y") for d in label_dates]
                            
                            # Set x-axis ticks and labels on bottommost axis (shared with all via sharex=True)
                            bottom_ax.set_xticks(label_positions)
                            bottom_ax.set_xticklabels(date_labels, fontsize=8, rotation=45, ha='right')
                            bottom_ax.set_xlabel("Time", fontsize=10)
                        else:
                            bottom_ax.set_xlabel("Time", fontsize=10)
                except Exception as e:
                    logger.warning(f"Failed to format time axis for {sym}: {e}")
                    bottom_ax.set_xlabel("Time", fontsize=10)
            
            # Auto-scale Y-axis to show all waves clearly
            # Get all valid values from all waves to set appropriate Y-axis limits
            all_wave_values: list[float] = []
            if show_composite and composite:
                all_wave_values.extend([v for v in composite if v is not None])
            if show_periods:
                for period_name in show_periods:
                    if period_name in bandpasses:
                        all_wave_values.extend([v for v in bandpasses[period_name] if v is not None])
            
            if all_wave_values:
                min_val = min(all_wave_values)
                max_val = max(all_wave_values)
                # Add padding for visibility
                padding = (max_val - min_val) * 0.1 if max_val != min_val else 1.0
                ax2.set_ylim(min_val - padding, max_val + padding)
            
            # Calculate and plot MESA Stochastic if enabled
            if show_mesa:
                try:
                    # Get MESA parameters
                    mesa_length1 = int(self.params.get("mesa_length1", 50))
                    mesa_length2 = int(self.params.get("mesa_length2", 21))
                    mesa_length3 = int(self.params.get("mesa_length3", 14))
                    mesa_length4 = int(self.params.get("mesa_length4", 9))
                    mesa_trigger_length = int(self.params.get("mesa_trigger_length", 2))
                    
                    # Calculate HL2 (high + low) / 2 for MESA Stochastic
                    # Use full history for calculation, then slice for display
                    full_hl2 = [(h + l) / 2.0 for h, l in zip(full_highs, full_lows)]
                    
                    # Calculate MESA Stochastic with full history
                    mesa_result = calculate_mesa_stochastic_multi_length(
                        prices=full_hl2,
                        length1=mesa_length1,
                        length2=mesa_length2,
                        length3=mesa_length3,
                        length4=mesa_length4,
        )
                    
                    # Store full MESA data for AI analysis
                    mesa_data_by_symbol[str(sym)] = {
                        "mesa1": mesa_result["mesa1"],
                        "mesa2": mesa_result["mesa2"],
                        "mesa3": mesa_result["mesa3"],
                        "mesa4": mesa_result["mesa4"],
                        "timestamps": [x[0] for x in full_norm],
                        "metadata": {
                            "length1": mesa_length1,
                            "length2": mesa_length2,
                            "length3": mesa_length3,
                            "length4": mesa_length4,
                            "trigger_length": mesa_trigger_length,
                            "total_bars": len(full_norm),
                            "display_bars": len(norm),
                        }
                    }
                    
                    # Slice MESA values to match display range (same as Hurst)
                    display_mesa = {}
                    for key in ["mesa1", "mesa2", "mesa3", "mesa4"]:
                        display_mesa[key] = mesa_result[key][start_idx:]
                    
                    # Plot MESA Stochastic on third subplot
                    if ax3 is not None:
                        _plot_mesa_stochastic(ax3, timestamps, display_mesa, mesa_trigger_length)
                        ax3.set_title(f"{str(sym)} MESA Stochastic Multi Length", fontsize=12, fontweight='bold', pad=10)
                        ax3.set_ylabel("MESA Stochastic", fontsize=10)
                        # Don't set xlabel here if CCO is below - it's shared with bottom panel and would overlap with title
                        # Only set xlabel if this is the bottom panel (no CCO)
                        # X-axis label is set on bottommost panel to avoid overlap
                        ax3.tick_params(labelsize=9)
                    
                except Exception as e:
                    logger.error(f"Error calculating MESA Stochastic for {sym}: {e}", exc_info=True)
                    # If MESA fails, still create the image without it
                    pass
            
            # Calculate and plot CCO if enabled
            if show_cco:
                try:
                    # Get CCO parameters
                    cco_short_cycle_length = int(self.params.get("cco_short_cycle_length", 10))
                    cco_medium_cycle_length = int(self.params.get("cco_medium_cycle_length", 30))
                    cco_short_cycle_multiplier = float(self.params.get("cco_short_cycle_multiplier", 1.0))
                    cco_medium_cycle_multiplier = float(self.params.get("cco_medium_cycle_multiplier", 3.0))
                    
                    # Calculate CCO with full history
                    cco_result = calculate_cco(
                        closes=full_closes,
                        highs=full_highs,
                        lows=full_lows,
                        short_cycle_length=cco_short_cycle_length,
                        medium_cycle_length=cco_medium_cycle_length,
                        short_cycle_multiplier=cco_short_cycle_multiplier,
                        medium_cycle_multiplier=cco_medium_cycle_multiplier,
        )
                    
                    # Store full CCO data for AI analysis
                    cco_data_by_symbol[str(sym)] = {
                        "fast_osc": cco_result["fast_osc"],
                        "slow_osc": cco_result["slow_osc"],
                        "short_cycle_top": cco_result["short_cycle_top"],
                        "short_cycle_bottom": cco_result["short_cycle_bottom"],
                        "short_cycle_midline": cco_result["short_cycle_midline"],
                        "medium_cycle_top": cco_result["medium_cycle_top"],
                        "medium_cycle_bottom": cco_result["medium_cycle_bottom"],
                        "timestamps": [x[0] for x in full_norm],
                        "metadata": {
                            "short_cycle_length": cco_short_cycle_length,
                            "medium_cycle_length": cco_medium_cycle_length,
                            "short_cycle_multiplier": cco_short_cycle_multiplier,
                            "medium_cycle_multiplier": cco_medium_cycle_multiplier,
                            "total_bars": len(full_norm),
                            "display_bars": len(norm),
                        }
                    }
                    
                    # Slice CCO values to match display range (same as Hurst and MESA)
                    display_fast_osc = cco_result["fast_osc"][start_idx:]
                    display_slow_osc = cco_result["slow_osc"][start_idx:]
                    
                    # Plot CCO on the appropriate subplot
                    # If MESA is enabled, CCO goes to ax4, otherwise to ax3
                    cco_ax = ax4 if show_mesa else ax3
                    if cco_ax is not None:
                        _plot_cco(cco_ax, timestamps, display_fast_osc, display_slow_osc)
                        cco_ax.set_title(f"{str(sym)} Cycle Channel Oscillator (CCO)", fontsize=12, fontweight='bold', pad=10)
                        cco_ax.set_ylabel("CCO", fontsize=10)
                        # X-axis label is set on bottommost panel to avoid overlap
                        cco_ax.tick_params(labelsize=9)
                    
                except Exception as e:
                    logger.error(f"Error calculating CCO for {sym}: {e}", exc_info=True)
                    # If CCO fails, still create the image without it
                    pass

            # Add visual separation between symbols - StockCharts-style borders and spacing
            # Add border around entire figure to clearly separate each symbol's chart group
            fig.patch.set_edgecolor('#d0d0d0')  # Medium gray border for clear separation
            fig.patch.set_linewidth(3.0)  # 3px border for better visibility
            fig.patch.set_facecolor('#ffffff')  # White background (charts have white axes backgrounds)
            
            # Make all titles more prominent with background boxes - positioned COMPLETELY OUTSIDE chart area
            # Use figure coordinates to position titles well above the chart panels, ensuring no overlap
            # Price chart title (most important - make it stand out)
            ax1_title = ax1.get_title()
            if ax1_title:
                ax1.set_title('')  # Clear default title
                # Position title well above the chart using figure coordinates
                # Get the position of ax1 in figure coordinates
                ax1_pos = ax1.get_position()
                # Position title significantly above ax1, in the top margin space (completely outside chart area)
                # Use y1 (top of axis) + larger offset to ensure it's well outside
                title_y = min(ax1_pos.y1 + 0.035, 0.96)  # Position well above, cap at 0.96 to stay in figure
                fig.text(0.5, title_y, ax1_title,
                        fontsize=14, fontweight='bold', ha='center', va='bottom',
                        bbox=dict(boxstyle='round,pad=0.6', facecolor='white', 
                                 edgecolor='#b0b0b0', linewidth=2.0, alpha=0.98),
                        zorder=100)
            
            # Make other panel titles also more visible - positioned completely outside chart area
            for ax in [ax2, ax3, ax4]:
                if ax is not None:
                    ax_title = ax.get_title()
                    if ax_title:
                        ax.set_title('')  # Clear default title
                        # Position title above the chart using figure coordinates
                        ax_pos = ax.get_position()
                        # Position title well above this axis, in the margin space between panels
                        # Use larger offset to ensure it's completely outside the chart area
                        title_y = min(ax_pos.y1 + 0.025, 0.96)  # Position well above, cap at 0.96
                        fig.text(0.5, title_y, ax_title,
                               fontsize=12, fontweight='bold', ha='center', va='bottom',
                               bbox=dict(boxstyle='round,pad=0.4', facecolor='white',
                                        edgecolor='#d0d0d0', linewidth=1.5, alpha=0.95),
                               zorder=100)
            
            # Get DPI from params (default 250)
            dpi = int(self.params.get("dpi", self.default_params.get("dpi", 250)))
            images[str(sym)] = _encode_fig_to_data_url(fig, dpi=dpi)

        return {
            "images": images,
            "hurst_data": hurst_data_by_symbol,  # Calculated Hurst values for AI analysis
            "ohlcv_bundle": ohlcv_bundle_output,  # OHLCV bars used for calculation
            "mesa_data": mesa_data_by_symbol,  # MESA Stochastic data (when enabled, empty dict otherwise)
            "cco_data": cco_data_by_symbol,  # CCO data (when enabled, empty dict otherwise)
        }

