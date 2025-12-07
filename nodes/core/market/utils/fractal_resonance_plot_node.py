"""
Fractal Resonance Bar Plot Node

Creates chart with Fractal Resonance Bar indicator showing WaveTrend oscillators
at multiple timeframes as horizontal colored bars stacked vertically.

Based on TradingView Pine Script by Pythagoras.
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

# Timeframe constants (shared by bars rendering)
TIMEFRAMES = ["1", "2", "4", "8", "16", "32", "64", "128"]

# Configure matplotlib for high-quality rendering
plt.rcParams.update({
    'figure.dpi': 400,
    'savefig.dpi': 400,
    'figure.facecolor': 'white',
    'axes.facecolor': 'white',
    'lines.antialiased': True,
    'patch.antialiased': True,
    'text.antialiased': True,
    'font.family': 'sans-serif',
    'font.sans-serif': ['Arial', 'DejaVu Sans', 'Liberation Sans', 'Helvetica', 'sans-serif'],
    'font.size': 10,
    'axes.labelsize': 10,
    'axes.titlesize': 12,
    'xtick.labelsize': 9,
    'ytick.labelsize': 9,
    'legend.fontsize': 8,
    'lines.linewidth': 1.5,
    'lines.markeredgewidth': 0.5,
    'patch.linewidth': 0.5,
    'axes.grid': True,
    'axes.axisbelow': True,
    'grid.alpha': 0.7,
    'grid.color': '#c0c0c0',
    'grid.linewidth': 0.8,
    'grid.linestyle': '-',
    'axes.edgecolor': '#cccccc',
    'axes.linewidth': 0.8,
    'xtick.color': '#666666',
    'ytick.color': '#666666',
    'image.interpolation': 'bilinear',
    'image.resample': True,
    'agg.path.chunksize': 10000,
})

if TYPE_CHECKING:
    from matplotlib.axes import Axes
    from matplotlib.figure import Figure
else:
    from matplotlib.axes import Axes
    from matplotlib.figure import Figure

from core.types_registry import AssetSymbol, NodeCategory, NodeValidationError, OHLCVBar, get_type
from nodes.base.base_node import Base
from services.indicator_calculators.fractal_resonance_calculator import (
    calculate_fractal_resonance,
    stochastic_trend,  # used for FR Component panel
)

logger = logging.getLogger(__name__)


def _encode_fig_to_data_url(fig: "Figure", dpi: int = 400) -> str:
    """Encode matplotlib figure to base64 data URL with high resolution."""
    buf = io.BytesIO()
    fig.savefig(
        buf,
        format="png",
        bbox_inches="tight",
        pad_inches=0.1,
        dpi=dpi,  # Increased to 400 for much better resolution
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
    """Return tuple of (OHLC data, volume data) sorted by ts (oldest to newest)."""
    timestamp_map: dict[int, tuple[int, float, float, float, float, float]] = {}
    
    for bar in bars:
        ts = int(bar["timestamp"])
        open_price = float(bar["open"])
        high_price = float(bar["high"])
        low_price = float(bar["low"])
        close_price = float(bar["close"])
        volume = float(bar.get("volume", 0.0))
        timestamp_map[ts] = (ts, open_price, high_price, low_price, close_price, volume)
    
    normalized = list(timestamp_map.values())
    normalized.sort(key=lambda x: x[0])
    
    ohlc_data = [(ts, o, h, l, c) for ts, o, h, l, c, _v in normalized]
    volume_data = [_v for _, _, _, _, _, _v in normalized]
    
    return ohlc_data, volume_data


def _plot_fractal_resonance_bars(
    ax: "Axes",
    timestamps: list[int],
    colors: dict[str, list[str]],
    block_colors: dict[str, list[str]],
    ribbon_line_width: int = 8,
) -> None:
    """Plot Fractal Resonance Bar indicator as horizontal bars stacked vertically."""
    if not timestamps:
        return
    
    # Use light background for better visibility and AI analysis
    ax.set_facecolor('#ffffff')
    
    x_indices = list(range(len(timestamps)))
    
    # Calculate Y positions for each row (use positive values, stacked from top)
    # We'll plot 16 rows total (8 timeframes * 2 rows each)
    # Start from top and work down
    y_positions_regular: list[float] = []
    y_positions_block: list[float] = []
    
    total_rows = len(TIMEFRAMES) * 2
    start_y = total_rows * ribbon_line_width
    
    for idx, tf in enumerate(TIMEFRAMES):
        # Regular color row (top row for this timeframe)
        y_pos_regular = start_y - (idx * 2 + 1) * ribbon_line_width
        y_positions_regular.append(y_pos_regular)
        # Block color row (bottom row for this timeframe, with embedding)
        y_pos_block = start_y - (idx * 2 + 2) * ribbon_line_width
        y_positions_block.append(y_pos_block)
    
    # Collect all bars to draw efficiently
    bars_to_draw: list[dict[str, Any]] = []
    
    # Draw horizontal bars for each timeframe
    for idx, tf in enumerate(TIMEFRAMES):
        if tf not in colors or tf not in block_colors:
            logger.warning(f"Missing colors for timeframe {tf}: colors keys={list(colors.keys())}, block_colors keys={list(block_colors.keys())}")
            continue
        
        regular_colors = colors[tf]
        block_colors_tf = block_colors[tf]
        y_pos_regular = y_positions_regular[idx]
        y_pos_block = y_positions_block[idx]
        
        # Count non-white colors for debugging
        non_white_regular = sum(1 for c in regular_colors if c and c != "#ffffff")
        non_white_block = sum(1 for c in block_colors_tf if c and c != "#ffffff")
        
        if idx == 0:  # Log for first timeframe only
            logger.warning(f"WT{tf}: {len(regular_colors)} regular colors ({non_white_regular} non-white), {len(block_colors_tf)} block colors ({non_white_block} non-white)")
            if len(regular_colors) > 0:
                sample_colors = regular_colors[:min(10, len(regular_colors))]
                logger.warning(f"WT{tf} sample colors: {sample_colors}")
        
        # Draw horizontal bars for each time point
        for i in range(len(timestamps)):
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
    
    # Draw all bars using Rectangle patches for better rendering
    from matplotlib.patches import Rectangle
    
    if bars_to_draw:
        for bar in bars_to_draw:
            rect = Rectangle(
                (bar['left'], bar['y'] - bar['height'] / 2),
                bar['width'],
                bar['height'],
                facecolor=bar['color'],
                edgecolor='none',
                alpha=1.0,
                zorder=bar['zorder'],
            )
            ax.add_patch(rect)
        logger.warning(f"Drew {len(bars_to_draw)} bars total")
    else:
        logger.error("No bars to draw! Colors dict might be empty or all None")
    
    # Draw separator line at top (like Pine Script hline)
    ax.axhline(y=start_y, color='#000000', linewidth=1.5, zorder=3)
    
    # Add Y-axis labels for timeframes (positioned at middle of each timeframe's two rows)
    y_tick_positions = []
    y_tick_labels = []
    for idx, tf in enumerate(TIMEFRAMES):
        # Position label between the two rows for this timeframe
        y_pos = (y_positions_regular[idx] + y_positions_block[idx]) / 2
        y_tick_positions.append(y_pos)
        y_tick_labels.append(f"WT{tf}")
    
    ax.set_yticks(y_tick_positions)
    ax.set_yticklabels(y_tick_labels, color='#000000', fontsize=9)
    ax.tick_params(colors='#000000')
    
    # Set Y-axis limits (positive values)
    ax.set_ylim(0, start_y + ribbon_line_width)


def _plot_fr_component(
    ax: "Axes",
    timestamps: list[int],
    wta: list[float | None],
    wtb: list[float | None],
    wtdiff: list[float | None],
    ob_level: float,
    ob_extreme_level: float,
) -> None:
    """Plot the Fractal Resonance Component (single timescale wave trend)."""
    if not timestamps or not wta or not wtb or not wtdiff:
        return

    os_level = -ob_level
    os_extreme_level = -ob_extreme_level

    x_idx = list(range(len(timestamps)))

    # Shaded zones
    ax.axhspan(ob_level, ob_extreme_level, color="#800000", alpha=0.08, zorder=0)  # maroon-ish
    ax.axhspan(os_extreme_level, os_level, color="#808000", alpha=0.08, zorder=0)  # olive-ish

    # WaveTrend diff area
    ax.fill_between(
        x_idx,
        [v if v is not None else 0 for v in wtdiff],
        0,
        color="blue",
        alpha=0.18,
        zorder=1,
    )

    # Lead/lag lines
    ax.plot(x_idx, wta, color="green", linewidth=1.2, label="wtA", zorder=2)
    ax.plot(x_idx, wtb, color="red", linewidth=1.0, label="wtB", zorder=2)

    # Cross detection
    cross_x: list[int] = []
    cross_y: list[float] = []
    cross_extreme_x: list[int] = []
    cross_extreme_y: list[float] = []
    cross_wtb_x: list[int] = []
    cross_wtb_y: list[float] = []
    cross_wtb_color: list[str] = []

    def _sign(x: float) -> int:
        return 1 if x > 0 else (-1 if x < 0 else 0)

    for i in range(1, len(x_idx)):
        a0, b0 = wta[i - 1], wtb[i - 1]
        a1, b1 = wta[i], wtb[i]
        if a0 is None or b0 is None or a1 is None or b1 is None:
            continue
        prev_diff = a0 - b0
        curr_diff = a1 - b1
        if _sign(prev_diff) == 0 or _sign(prev_diff) == _sign(curr_diff):
            continue
        is_extreme = (a1 > ob_extreme_level) or (a1 < os_extreme_level)
        is_significant = (a1 > ob_level) or (a1 < os_level)
        if is_extreme:
            cross_extreme_x.append(x_idx[i])
            cross_extreme_y.append(a1)
        elif is_significant:
            cross_x.append(x_idx[i])
            cross_y.append(a1)
        # Colored circle at wtb level with trend direction color
        cross_wtb_x.append(x_idx[i])
        cross_wtb_y.append(b1)
        cross_wtb_color.append("red" if (b1 - a1) > 0 else "lime")

    if cross_x:
        ax.scatter(cross_x, cross_y, marker="o", s=20, facecolors="none", edgecolors="black", linewidths=1.2, zorder=3)
    if cross_extreme_x:
        ax.scatter(cross_extreme_x, cross_extreme_y, marker="x", s=28, color="black", linewidths=1.2, zorder=3)
    if cross_wtb_x:
        ax.scatter(
            cross_wtb_x,
            cross_wtb_y,
            marker="o",
            s=18,
            facecolors="none",
            edgecolors=cross_wtb_color,
            linewidths=1.0,
            zorder=3,
        )

    # Styling
    ax.grid(True, alpha=0.3, linestyle="-", linewidth=0.5, color="#cccccc", zorder=0)
    ax.set_axisbelow(True)
    for spine in ax.spines.values():
        spine.set_color("#000000")
        spine.set_linewidth(0.8)
    
    # Set X-axis limits
    if x_idx:
        ax.set_xlim(-0.5, len(x_idx) - 0.5)
    
    # Format X-axis with timestamps
    if timestamps:
        # Show more labels for better readability
        num_labels = min(15, len(timestamps))
        step = max(1, len(timestamps) // num_labels)
        tick_positions = list(range(0, len(timestamps), step))
        tick_labels = []
        for pos in tick_positions:
            if pos < len(timestamps):
                ts = timestamps[pos]
                dt = datetime.fromtimestamp(ts / 1000)
                tick_labels.append(dt.strftime("%m/%d %H:%M"))
        ax.set_xticks(tick_positions)
        ax.set_xticklabels(tick_labels, rotation=45, ha='right', color='#000000', fontsize=9)
    
    # Grid and styling - clear grid on light background
    ax.grid(True, alpha=0.3, linestyle='-', linewidth=0.5, color='#cccccc', zorder=0)
    ax.set_axisbelow(True)
    ax.set_facecolor('#ffffff')
    for spine in ax.spines.values():
        spine.set_color('#000000')
        spine.set_linewidth(1.0)


class FractalResonancePlot(Base):
    """
    Renders OHLCV data with Fractal Resonance Bar indicator.
    
    Creates a chart with:
    - Top panel: Price OHLC bars
    - Bottom panel: Fractal Resonance Bar (horizontal colored bars stacked vertically)
    
    Inputs: 'ohlcv_bundle' (Dict[AssetSymbol, List[OHLCVBar]])
    Output: 'images' -> Dict[str, str] mapping label to data URL
    """

    inputs = {
        "ohlcv_bundle": get_type("OHLCVBundle") | None,
    }
    optional_inputs = ["ohlcv_bundle", "ohlcv"]

    outputs = {
        "images": get_type("ConfigDict"),
        "fractal_resonance_data": get_type("ConfigDict"),  # Calculated FR data
        "ohlcv_bundle": get_type("OHLCVBundle"),  # OHLCV bars used for calculation
    }

    CATEGORY = NodeCategory.MARKET
    
    default_params = {
        "n1": 10,  # Channel Length
        "n2": 21,  # Stochastic Ratio Length
        "crossover_sma_len": 3,  # Crossover Lag
        "ob_level": 75.0,  # Overbought level
        "ob_embed_level": 88.0,  # Embedded overbought level
        "ob_extreme_level": 100.0,  # Extreme overbought level
        "cross_separation": 3.0,  # Embed separation
        "ribbon_line_width": 8,  # Row width (increased for better visibility)
        "lookback_bars": None,  # Optional lookback limit
        "max_symbols": 50,  # Maximum symbols to process
        "zoom_to_recent": False,  # Auto-zoom to recent bars
        "dpi": 400,  # High resolution for better image quality
    }

    async def _execute_impl(self, inputs: dict[str, Any]) -> dict[str, Any]:
        bundle_raw = inputs.get("ohlcv_bundle")
        single_bundle_raw = inputs.get("ohlcv")

        logger.warning(f"🔵 FractalResonancePlot: Starting execution. Bundle type: {type(bundle_raw)}, Single bundle type: {type(single_bundle_raw)}")
        logger.warning(f"🔵 FractalResonancePlot: Bundle keys: {list(bundle_raw.keys()) if bundle_raw and isinstance(bundle_raw, dict) else 'None'}, Single bundle keys: {list(single_bundle_raw.keys()) if single_bundle_raw and isinstance(single_bundle_raw, dict) else 'None'}")

        # Normalize bundles - handle None values and ensure dict type
        bundle: dict[AssetSymbol, list[OHLCVBar]] | None = None
        bundle_received_but_empty = False
        if bundle_raw is not None and isinstance(bundle_raw, dict):
            # Normalize: filter out None values and ensure all values are lists
            normalized_bundle: dict[AssetSymbol, list[OHLCVBar]] = {}
            for key, value in bundle_raw.items():
                if isinstance(key, AssetSymbol):
                    if value is None:
                        normalized_bundle[key] = []
                    elif isinstance(value, list):
                        normalized_bundle[key] = value
            if normalized_bundle:
                bundle = normalized_bundle
            elif len(bundle_raw) == 0:
                # Empty dict was received
                bundle_received_but_empty = True
        
        single_bundle: dict[AssetSymbol, list[OHLCVBar]] | None = None
        if single_bundle_raw is not None and isinstance(single_bundle_raw, dict):
            normalized_single: dict[AssetSymbol, list[OHLCVBar]] = {}
            for key, value in single_bundle_raw.items():
                if isinstance(key, AssetSymbol):
                    if value is None:
                        normalized_single[key] = []
                    elif isinstance(value, list):
                        normalized_single[key] = value
            if normalized_single:
                single_bundle = normalized_single
            elif len(single_bundle_raw) == 0:
                bundle_received_but_empty = True

        # Merge both inputs if both provided
        if bundle and single_bundle:
            bundle = {**bundle, **single_bundle}
        elif single_bundle:
            bundle = single_bundle

        if not bundle or len(bundle) == 0:
            if bundle_received_but_empty or (bundle_raw is not None and isinstance(bundle_raw, dict) and len(bundle_raw) == 0):
                logger.error(f"❌ FractalResonancePlot: Empty bundle received (likely all symbols filtered out by upstream filter). Inputs keys: {list(inputs.keys())}")
                logger.error(f"❌ FractalResonancePlot: bundle_raw type={type(bundle_raw)}, bundle_raw keys={list(bundle_raw.keys()) if bundle_raw and isinstance(bundle_raw, dict) else 'N/A'}")
                raise NodeValidationError(
                    self.id, 
                    "Received empty bundle - upstream filter may have filtered out all symbols. "
                    "Check your filter node settings or ensure symbols are passing through."
                )
            else:
                logger.error(f"❌ FractalResonancePlot: No bundle provided. Inputs keys: {list(inputs.keys())}")
                logger.error(f"❌ FractalResonancePlot: bundle_raw={bundle_raw}, single_bundle_raw={single_bundle_raw}")
                raise NodeValidationError(self.id, "Provide either 'ohlcv_bundle' or 'ohlcv' with at least one symbol")
        
        # Filter out symbols with empty data
        original_bundle_size = len(bundle)
        filtered_bundle: dict[AssetSymbol, list[OHLCVBar]] = {}
        for sym, bars in bundle.items():
            if bars and len(bars) > 0:
                filtered_bundle[sym] = bars
        
        if not filtered_bundle:
            logger.error(f"❌ FractalResonancePlot: All symbols have empty data. Original bundle had {original_bundle_size} symbols")
            raise NodeValidationError(self.id, "All symbols in bundle have empty or no data")
        
        bundle = filtered_bundle
        logger.warning(f"🔵 FractalResonancePlot: Processing {len(bundle)} symbols (filtered from {original_bundle_size} original)")

        lookback_raw = self.params.get("lookback_bars")
        lookback: int | None = None
        if lookback_raw is not None:
            if isinstance(lookback_raw, (int, float, str)):
                try:
                    lookback = int(lookback_raw)
                except (ValueError, TypeError):
                    lookback = None

        images: dict[str, str] = {}
        fr_data_by_symbol: dict[str, dict[str, Any]] = {}
        ohlcv_bundle_output: dict[AssetSymbol, list[OHLCVBar]] = {}

        # Limit symbols for safety
        max_syms_raw = self.params.get("max_symbols", 50)
        max_syms = 50  # default fallback
        if isinstance(max_syms_raw, (int, float, str)):
            try:
                max_syms = int(max_syms_raw)
            except (ValueError, TypeError):
                max_syms = 50

        # Get Fractal Resonance parameters
        n1 = int(self.params.get("n1", 10))
        n2 = int(self.params.get("n2", 21))
        crossover_sma_len = int(self.params.get("crossover_sma_len", 3))
        ob_level = float(self.params.get("ob_level", 75.0))
        ob_embed_level = float(self.params.get("ob_embed_level", 88.0))
        ob_extreme_level = float(self.params.get("ob_extreme_level", 100.0))
        cross_separation = float(self.params.get("cross_separation", 3.0))
        ribbon_line_width = int(self.params.get("ribbon_line_width", 5))
        component_multiplier = int(self.params.get("component_multiplier", 1))

        items = list(bundle.items())[:max_syms]
        logger.warning(f"🔵 FractalResonancePlot: Processing {len(items)} symbols (max: {max_syms})")
        
        for sym, bars in items:
            if not bars:
                logger.warning(f"⚠️ FractalResonancePlot: No bars provided for {sym}")
                continue
            
            logger.warning(f"🔵 FractalResonancePlot: Processing {sym}: received {len(bars)} bars")
            
            norm, volumes = _normalize_bars(bars)
            logger.warning(f"🔵 FractalResonancePlot: Normalized {sym}: {len(norm)} bars")
            
            if len(norm) < 10:
                logger.warning(f"Insufficient bars for {sym}: {len(norm)} bars (need at least 10)")
                continue
            
            # Use FULL history for calculation (needed for higher timeframes like 128x)
            # For 128x timeframe: n1=10, n2=21, crossover_sma_len=3
            # Max period needed: n2 * 128 = 21 * 128 = 2688 bars
            full_closes_raw = [x[4] for x in norm]
            # Forward-fill missing closes to avoid None cascades in EMA/SMA
            full_closes: list[float | None] = []
            last_close: float | None = None
            for c in full_closes_raw:
                if c is None:
                    full_closes.append(last_close)
                else:
                    full_closes.append(c)
                    last_close = c
            
            # Apply lookback for display only
            zoom_to_recent = bool(self.params.get("zoom_to_recent", False))
            
            if zoom_to_recent and len(norm) > 300:
                display_norm = norm[-300:]
            elif lookback is not None and lookback > 0:
                if len(norm) > lookback:
                    display_norm = norm[-lookback:]
                else:
                    display_norm = norm
            else:
                # Smart default - show recent data but use full for calculation
                total_bars = len(norm)
                if total_bars <= 2500:
                    display_norm = norm
                else:
                    display_norm = norm[-2000:]
            
            # Extract price data for display
            timestamps = [x[0] for x in display_norm]
            display_closes = [x[4] for x in display_norm]
            
            # Calculate Fractal Resonance with FULL history
            try:
                # Calculate minimum bars needed for each timeframe
                # Max period needed: n2 * time_multiplier (for TCI EMA)
                min_bars_needed = {}
                usable_timeframes = []
                for tm_str in TIMEFRAMES:
                    tm = int(tm_str)  # Convert string to int
                    min_bars = n2 * tm  # TCI period is the longest
                    min_bars_needed[tm] = min_bars
                    if len(full_closes) >= min_bars:
                        usable_timeframes.append(tm)
                
                logger.warning(
                    f"🔵 FractalResonancePlot: Calculating FR for {sym} with {len(full_closes)} bars "
                    f"(displaying {len(display_closes)} bars)\n"
                    f"   📊 Timeframe requirements:\n"
                    f"   {'   '.join([f'WT{tm}: {bars} bars min' for tm, bars in min_bars_needed.items()])}\n"
                    f"   ✅ Usable timeframes: {usable_timeframes if usable_timeframes else 'NONE!'}\n"
                    f"   ⚠️  For WT128, you need {min_bars_needed[128]} bars (~{min_bars_needed[128]//365:.1f} years of daily data)"
                )
                
                fr_result = calculate_fractal_resonance(
                    closes=full_closes,
                    n1=n1,
                    n2=n2,
                    crossover_sma_len=crossover_sma_len,
                    ob_level=ob_level,
                    ob_embed_level=ob_embed_level,
                    ob_extreme_level=ob_extreme_level,
                    cross_separation=cross_separation,
                )
                
                # Store FR data
                fr_data_by_symbol[str(sym)] = {
                    "wt_a": fr_result.get("wt_a", {}),
                    "wt_b": fr_result.get("wt_b", {}),
                    "wt_diff": fr_result.get("wt_diff", {}),
                    "colors": fr_result.get("colors", {}),
                    "block_colors": fr_result.get("block_colors", {}),
                    "highest_overbought": fr_result.get("highest_overbought", []),
                    "highest_oversold": fr_result.get("highest_oversold", []),
                    "timestamps": timestamps,
                }
                
                ohlcv_bundle_output[sym] = bars
                
            except Exception as e:
                logger.error(f"Error calculating Fractal Resonance for {sym}: {e}", exc_info=True)
                continue
            
            # Create figure with 2 subplots: Price and Fractal Resonance
            # Increased size and better aspect ratio for higher resolution
            fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(16, 12), sharex=True, height_ratios=[2.0, 1.5])
            # Add third panel for FR Component
            fig.clf()
            ax1 = fig.add_subplot(3, 1, 1)
            ax2 = fig.add_subplot(3, 1, 2, sharex=ax1)
            ax3 = fig.add_subplot(3, 1, 3, sharex=ax1)
            fig.set_size_inches(16, 14)
            fig.subplots_adjust(hspace=0.18, top=0.95, bottom=0.08, left=0.08, right=0.95)
            
            # Slice FR results to match display range
            # FR results are calculated on full_closes, but we only display display_closes
            # So we need to slice the results to match the display range
            full_length = len(full_closes)
            display_length = len(display_closes)
            start_idx = max(0, full_length - display_length)
            
            # Slice colors and block_colors to match display range
            display_colors: dict[str, list[str]] = {}
            display_block_colors: dict[str, list[str]] = {}
            
            fr_colors = fr_result.get("colors", {})
            fr_block_colors = fr_result.get("block_colors", {})
            fr_debug = fr_result.get("debug", {})
            
            logger.warning(f"FR result colors keys: {list(fr_colors.keys())}, block_colors keys: {list(fr_block_colors.keys())}")
            dbg_tm1 = fr_debug.get("1") if isinstance(fr_debug, dict) else None
            if dbg_tm1:
                logger.warning(f"WT1 debug: {dbg_tm1}")
            
            for tf in fr_colors.keys():
                colors_tf = fr_colors[tf]
                block_colors_tf = fr_block_colors.get(tf, [])
                
                if len(colors_tf) == full_length:
                    display_colors[tf] = colors_tf[start_idx:]
                    if len(block_colors_tf) == full_length:
                        display_block_colors[tf] = block_colors_tf[start_idx:]
                    else:
                        display_block_colors[tf] = block_colors_tf[start_idx:] if len(block_colors_tf) > start_idx else []
                else:
                    display_colors[tf] = colors_tf
                    display_block_colors[tf] = block_colors_tf
                
                # Debug: check color distribution
                if tf == "1" and len(display_colors[tf]) > 0:
                    sample = display_colors[tf][:min(20, len(display_colors[tf]))]
                    unique_colors = set(sample)
                    logger.warning(f"WT{tf} display colors sample (first 20): {sample[:10]}, unique: {unique_colors}")
            
            # Top panel: Price candlesticks (simplified)
            ax1.set_facecolor('#ffffff')
            x_indices = list(range(len(timestamps)))
            
            # Plot simple line chart for price
            ax1.plot(x_indices, display_closes, color='#000000', linewidth=1.5, label='Close')
            ax1.set_ylabel('Price', fontsize=10)
            ax1.set_title(f"{sym} - Fractal Resonance Bar", fontsize=12, fontweight='bold')
            ax1.grid(True, alpha=0.7, linestyle='-', linewidth=0.8, color='#c0c0c0', zorder=0)
            ax1.set_axisbelow(True)
            for spine in ax1.spines.values():
                spine.set_color('#cccccc')
                spine.set_linewidth(0.8)
            
            # Bottom panel: Fractal Resonance bars (use sliced colors for display)
            _plot_fractal_resonance_bars(ax2, timestamps, display_colors, display_block_colors, ribbon_line_width)
            ax2.set_xlabel('Time', fontsize=10)
            ax2.set_ylabel('Fractal Resonance', fontsize=10)

            # Third panel: Fractal Resonance Component (single timescale WaveTrend)
            comp_wta_full, comp_wtb_full, comp_wtdiff_full = stochastic_trend(
                full_closes, n1, n2, crossover_sma_len, component_multiplier
            )
            comp_wta = comp_wta_full[start_idx:] if len(comp_wta_full) == full_length else comp_wta_full
            comp_wtb = comp_wtb_full[start_idx:] if len(comp_wtb_full) == full_length else comp_wtb_full
            comp_wtdiff = comp_wtdiff_full[start_idx:] if len(comp_wtdiff_full) == full_length else comp_wtdiff_full

            fr_data_by_symbol[str(sym)]["component"] = {
                "wt_a": comp_wta,
                "wt_b": comp_wtb,
                "wt_diff": comp_wtdiff,
                "timestamps": timestamps,
                "multiplier": component_multiplier,
            }

            _plot_fr_component(ax3, timestamps, comp_wta, comp_wtb, comp_wtdiff, ob_level, ob_extreme_level)
            ax3.set_xlabel('Time', fontsize=10)
            ax3.set_ylabel(f'FR Component x{component_multiplier}', fontsize=10)
            
            # Encode figure to data URL with high resolution
            dpi = int(self.params.get("dpi", 400))
            label = str(sym)  # Use symbol string directly, matching HurstPlot pattern
            image_data = _encode_fig_to_data_url(fig, dpi=dpi)
            images[label] = image_data
            logger.warning(f"✅ FractalResonancePlot: Generated chart for {sym}, image size: {len(image_data)} chars, DPI: {dpi}, label: {label}")
            
            # Emit partial result so images show up incrementally
            self.emit_partial_result({"images": {label: image_data}})

        logger.warning(f"🔵 FractalResonancePlot: Completed. Generated {len(images)} images")
        logger.warning(f"🔵 FractalResonancePlot: Returning images with keys: {list(images.keys())}")
        
        result = {
            "images": images,
            "fractal_resonance_data": fr_data_by_symbol,
            "ohlcv_bundle": ohlcv_bundle_output,
        }
        logger.warning(f"🔵 FractalResonancePlot: Final result keys: {list(result.keys())}, images count: {len(result.get('images', {}))}")
        return result

