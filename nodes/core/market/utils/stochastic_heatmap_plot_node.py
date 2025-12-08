"""
Stochastic Heat Map Plot Node

Creates chart with Stochastic Heat Map indicator showing multiple stochastic oscillators
stacked vertically as horizontal colored lines.

Based on TradingView Pine Script by Violent (https://www.tradingview.com/v/7PRbCBjk/)
"""

import base64
import io
import logging
from typing import TYPE_CHECKING, Any

import matplotlib
import matplotlib.ticker

matplotlib.use("Agg")  # non-interactive backend for server-side rendering
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches

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
    'grid.alpha': 0.3,
    'grid.color': '#c0c0c0',
    'grid.linewidth': 0.5,
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
from services.indicator_calculators.stochastic_heatmap_calculator import calculate_stochastic_heatmap

logger = logging.getLogger(__name__)


def _encode_fig_to_data_url(fig: "Figure", dpi: int = 150) -> str:
    """Encode matplotlib figure to base64 data URL with high resolution."""
    buf = io.BytesIO()
    fig.patch.set_facecolor('#1a1a1a')  # Dark background
    fig.savefig(
        buf,
        format="png",
        bbox_inches="tight",
        pad_inches=0.1,
        dpi=dpi,
        facecolor='#1a1a1a',  # Dark background like TradingView
        edgecolor='none',
        transparent=False,
        metadata={'Software': None},
    )
    plt.close(fig)
    buf.seek(0)
    b64 = base64.b64encode(buf.read()).decode("ascii")
    return f"data:image/png;base64,{b64}"


class StochasticHeatmapPlot(Base):
    """
    Renders OHLCV data with Stochastic Heat Map indicator.
    
    Creates a chart with:
    - Stochastic Heat Map: Multiple horizontal colored lines stacked vertically
    - Fast and Slow oscillator lines
    
    Inputs: 'ohlcv_bundle' (Dict[AssetSymbol, List[OHLCVBar]])
    Output: 'images' -> Dict[str, str] mapping label to data URL
    """

    inputs = {
        "ohlcv_bundle": get_type("OHLCVBundle") | None,
    }
    optional_inputs = ["ohlcv_bundle", "ohlcv"]

    outputs = {
        "images": get_type("ConfigDict"),
        "stochastic_heatmap_data": get_type("ConfigDict"),
        "ohlcv_bundle": get_type("OHLCVBundle"),
    }

    CATEGORY = NodeCategory.MARKET
    
    default_params = {
        "ma_type": "EMA",  # Moving average type: SMA, EMA, WMA
        "theme": "Theme 3",  # Color theme (Theme 1, 2, or 3)
        "increment": 10,  # Base increment for stochastic lengths
        "smooth_fast": 2,  # Smoothing period for fast line
        "smooth_slow": 21,  # Smoothing period for slow line
        "plot_number": 28,  # Number of stochastics to plot (1-28)
        "waves": True,  # Use weighted increments (True) or linear increments (False)
        "lookback_bars": None,  # Number of bars to display (None = all). Use to zoom in on recent data while calculating with full history.
        "zoom_to_recent": False,  # Auto-zoom to last 500 bars for better visibility
        "max_symbols": 50,  # Maximum symbols to process
        "dpi": 400,  # High resolution
        "filter_crossover": "none",  # Filter by crossover: "none" (no filter), "fast_above_slow" (bullish), "slow_above_fast" (bearish)
        "check_last_bar_only": True,  # If True, check only the last bar; if False, check if condition is true for any bar in display range
    }

    params_meta = [
        {
            "name": "ma_type",
            "type": "select",
            "options": ["SMA", "EMA", "WMA"],
            "default": "EMA",
            "description": "Moving average type for smoothing",
        },
        {
            "name": "theme",
            "type": "select",
            "options": ["Theme 1", "Theme 2", "Theme 3"],
            "default": "Theme 3",
            "description": "Color theme",
        },
        {
            "name": "increment",
            "type": "number",
            "default": 10,
            "min": 1,
            "step": 1,
            "description": "Base increment for stochastic lengths",
        },
        {
            "name": "smooth_fast",
            "type": "number",
            "default": 2,
            "min": 1,
            "step": 1,
            "description": "Smoothing period for fast line",
        },
        {
            "name": "smooth_slow",
            "type": "number",
            "default": 21,
            "min": 1,
            "step": 1,
            "description": "Smoothing period for slow line",
        },
        {
            "name": "plot_number",
            "type": "number",
            "default": 28,
            "min": 1,
            "max": 28,
            "step": 1,
            "description": "Number of stochastics to plot (1-28)",
        },
        {
            "name": "waves",
            "type": "boolean",
            "default": True,
            "description": "Use weighted increments (True) or linear increments (False)",
        },
        {
            "name": "max_symbols",
            "type": "number",
            "default": 50,
            "min": 1,
            "step": 1,
            "description": "Maximum number of symbols to process",
        },
        {
            "name": "lookback_bars",
            "type": "number",
            "default": None,
            "min": 10,
            "max": 10000,
            "step": 50,
            "description": "Number of bars to display (None = all). Use to zoom in on recent data while calculating with full history. Recommended: 500-2000 for better visibility.",
        },
        {
            "name": "zoom_to_recent",
            "type": "boolean",
            "default": False,
            "description": "Auto-zoom to last 500 bars for better visibility",
        },
        {
            "name": "filter_crossover",
            "type": "combo",
            "options": ["none", "fast_above_slow", "slow_above_fast"],
            "default": "none",
            "description": "Filter symbols by fast/slow crossover: none (no filter), fast_above_slow (bullish - fast > slow), slow_above_fast (bearish - slow > fast)",
        },
        {
            "name": "check_last_bar_only",
            "type": "boolean",
            "default": True,
            "description": "If True, check only the last bar for filter condition; if False, check if condition is true for any bar in display range",
        },
        {
            "name": "dpi",
            "type": "number",
            "default": 400,
            "min": 100,
            "max": 600,
            "step": 50,
            "description": "Image resolution (DPI)",
        },
    ]

    async def _execute_impl(self, inputs: dict[str, Any]) -> dict[str, Any]:
        bundle_raw = inputs.get("ohlcv_bundle")
        single_bundle_raw = inputs.get("ohlcv")

        # Normalize bundles
        bundle: dict[AssetSymbol, list[OHLCVBar]] | None = None
        bundle_received_but_empty = False
        
        if bundle_raw is not None and isinstance(bundle_raw, dict):
            normalized_bundle: dict[AssetSymbol, list[OHLCVBar]] = {}
            for key, value in bundle_raw.items():
                if isinstance(key, AssetSymbol):
                    if value is None:
                        normalized_bundle[key] = []
                    elif isinstance(value, list) and len(value) > 0:
                        normalized_bundle[key] = value
            if normalized_bundle:
                bundle = normalized_bundle
            elif len(bundle_raw) == 0:
                bundle_received_but_empty = True
        
        single_bundle: dict[AssetSymbol, list[OHLCVBar]] | None = None
        if single_bundle_raw is not None and isinstance(single_bundle_raw, dict):
            normalized_single: dict[AssetSymbol, list[OHLCVBar]] = {}
            for key, value in single_bundle_raw.items():
                if isinstance(key, AssetSymbol):
                    if value is None:
                        normalized_single[key] = []
                    elif isinstance(value, list) and len(value) > 0:
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
            if bundle_received_but_empty:
                logger.error(f"❌ StochasticHeatmapPlot: Empty bundle received")
                raise NodeValidationError(
                    self.id,
                    "Received empty bundle - upstream filter may have filtered out all symbols."
                )
            else:
                raise NodeValidationError(self.id, "Provide either 'ohlcv_bundle' or 'ohlcv' with at least one symbol")

        # Filter out symbols with empty data
        filtered_bundle: dict[AssetSymbol, list[OHLCVBar]] = {}
        for sym, bars in bundle.items():
            if bars and len(bars) > 0:
                filtered_bundle[sym] = bars
        
        if not filtered_bundle:
            raise NodeValidationError(self.id, "No symbols with valid data found in bundle")

        # Limit number of symbols
        max_symbols = int(self.params.get("max_symbols", 50))
        symbols_to_process = list(filtered_bundle.keys())[:max_symbols]
        
        logger.warning(f"🔵 StochasticHeatmapPlot: Processing {len(symbols_to_process)} symbols (max: {max_symbols})")

        images: dict[str, str] = {}
        shm_data_by_symbol: dict[str, Any] = {}
        ohlcv_bundle_output: dict[AssetSymbol, list[OHLCVBar]] = {}

        # Get parameters
        ma_type = str(self.params.get("ma_type", "EMA"))
        increment = int(self.params.get("increment", 10))
        smooth_fast = int(self.params.get("smooth_fast", 2))
        smooth_slow = int(self.params.get("smooth_slow", 21))
        plot_number = int(self.params.get("plot_number", 28))
        waves = bool(self.params.get("waves", True))
        dpi = int(self.params.get("dpi", 400))

        for sym in symbols_to_process:
            ohlcv_data = filtered_bundle[sym]
            
            if not ohlcv_data:
                continue

            logger.warning(f"🔵 StochasticHeatmapPlot: Processing {sym}: received {len(ohlcv_data)} bars")

            # Extract price data
            closes = [bar["close"] for bar in ohlcv_data]
            highs = [bar["high"] for bar in ohlcv_data]
            lows = [bar["low"] for bar in ohlcv_data]

            # Forward-fill None values
            for i in range(len(closes)):
                if closes[i] is None or closes[i] == 0:
                    for j in range(i - 1, -1, -1):
                        if closes[j] is not None and closes[j] != 0:
                            closes[i] = closes[j]
                            break
                    if closes[i] is None or closes[i] == 0:
                        for j in range(i + 1, len(closes)):
                            if closes[j] is not None and closes[j] != 0:
                                closes[i] = closes[j]
                                break

            # Apply same forward-fill to highs and lows
            for i in range(len(highs)):
                if highs[i] is None or highs[i] == 0:
                    for j in range(i - 1, -1, -1):
                        if highs[j] is not None and highs[j] != 0:
                            highs[i] = highs[j]
                            break
                if lows[i] is None or lows[i] == 0:
                    for j in range(i - 1, -1, -1):
                        if lows[j] is not None and lows[j] != 0:
                            lows[i] = lows[j]
                            break

            # Calculate with FULL data for accuracy, then slice for display
            # This ensures indicators are calculated correctly even if we only show recent bars
            full_closes = closes
            full_highs = highs
            full_lows = lows
            
            # Determine display range (similar to HurstPlot logic)
            zoom_to_recent = bool(self.params.get("zoom_to_recent", False))
            lookback_bars = self.params.get("lookback_bars")
            
            if zoom_to_recent and len(ohlcv_data) > 500:
                # Auto-zoom to last 500 bars for better visibility
                display_start = max(0, len(ohlcv_data) - 500)
                logger.warning(f"🔧 StochasticHeatmapPlot: Auto-zoom enabled: displaying last 500 bars (out of {len(ohlcv_data)} total)")
            elif lookback_bars is not None and lookback_bars > 0:
                # User-specified lookback
                if len(ohlcv_data) > lookback_bars:
                    display_start = max(0, len(ohlcv_data) - lookback_bars)
                else:
                    display_start = 0
                logger.warning(f"🔧 StochasticHeatmapPlot: User lookback: displaying last {len(ohlcv_data) - display_start} bars (requested {lookback_bars}, total {len(ohlcv_data)})")
            else:
                # SMART DEFAULT: Auto-choose based on total bars
                total_bars = len(ohlcv_data)
                if total_bars <= 2000:
                    # Small to medium dataset: show ALL
                    display_start = 0
                    logger.warning(f"🔧 StochasticHeatmapPlot: Smart default: showing ALL {total_bars} bars (full dataset)")
                else:
                    # Very large dataset: cap at 2000 bars for readability
                    display_start = max(0, total_bars - 2000)
                    logger.warning(f"🔧 StochasticHeatmapPlot: Smart default (large): showing last 2000 bars (out of {total_bars} total)")
            
            display_closes = closes[display_start:]
            display_highs = highs[display_start:]
            display_lows = lows[display_start:]

            # Calculate Stochastic Heat Map with FULL data for accuracy
            try:
                shm_result = calculate_stochastic_heatmap(
                    closes=full_closes,  # Use full data for calculation
                    highs=full_highs,     # Use full data for calculation
                    lows=full_lows,       # Use full data for calculation
                    ma_type=ma_type,
                    increment=increment,
                    smooth_fast=smooth_fast,
                    smooth_slow=smooth_slow,
                    plot_number=plot_number,
                    waves=waves,
                )

                # Apply filter if specified
                filter_crossover = self.params.get("filter_crossover", "none")
                check_last_bar_only = bool(self.params.get("check_last_bar_only", True))
                
                if filter_crossover and filter_crossover != "none":
                    fast_line_display = shm_result["fast_line"][display_start:]
                    slow_line_display = shm_result["slow_line"][display_start:]
                    
                    # Check filter condition
                    passes_filter = False
                    
                    if check_last_bar_only:
                        # Check only the last bar
                        if len(fast_line_display) > 0 and len(slow_line_display) > 0:
                            last_fast = fast_line_display[-1]
                            last_slow = slow_line_display[-1]
                            
                            if last_fast is not None and last_slow is not None:
                                if filter_crossover == "fast_above_slow":
                                    passes_filter = last_fast > last_slow
                                elif filter_crossover == "slow_above_fast":
                                    passes_filter = last_slow > last_fast
                    else:
                        # Check if condition is true for any bar in display range
                        for fast_val, slow_val in zip(fast_line_display, slow_line_display):
                            if fast_val is not None and slow_val is not None:
                                if filter_crossover == "fast_above_slow" and fast_val > slow_val:
                                    passes_filter = True
                                    break
                                elif filter_crossover == "slow_above_fast" and slow_val > fast_val:
                                    passes_filter = True
                                    break
                    
                    if not passes_filter:
                        logger.warning(f"⏭️  StochasticHeatmapPlot: Skipping chart for {sym} - filter condition not met ({filter_crossover})")
                        # Still store OHLCV data for downstream nodes, but skip chart generation
                        ohlcv_bundle_output[sym] = ohlcv_data
                        continue
                    else:
                        logger.warning(f"✅ StochasticHeatmapPlot: {sym} passes filter ({filter_crossover})")

                # Store data
                shm_data_by_symbol[str(sym)] = {
                    "stochastics": {str(k): v[display_start:] for k, v in shm_result["stochastics"].items()},
                    "colors": {str(k): v[display_start:] for k, v in shm_result["colors"].items()},
                    "fast_line": shm_result["fast_line"][display_start:],
                    "slow_line": shm_result["slow_line"][display_start:],
                    "average_stoch": shm_result["average_stoch"][display_start:],
                }

                # Create plot with two subplots: heat map and oscillator lines
                fig = plt.figure(figsize=(16, 12), dpi=dpi)
                gs = fig.add_gridspec(2, 1, height_ratios=[3, 1], hspace=0.1)
                ax_heatmap = fig.add_subplot(gs[0])
                ax_oscillator = fig.add_subplot(gs[1])
                
                ax_heatmap.set_facecolor('#1a1a1a')  # Dark background like TradingView
                ax_oscillator.set_facecolor('#1a1a1a')

                # Plot stochastic heat map lines
                x_indices = list(range(len(display_closes)))
                line_width = 3.5  # Thicker lines for better visibility
                
                # Plot each stochastic as a horizontal line with colors
                for idx in range(1, min(plot_number, 28) + 1):
                    if idx in shm_result["stochastics"]:
                        stoch_vals = shm_result["stochastics"][idx][display_start:]
                        colors = shm_result["colors"][idx][display_start:]
                        
                        # Plot line segments with different colors
                        y_pos = idx - 1  # Position from 0 to plot_number-1
                        
                        # Group consecutive bars with same color and plot segments
                        current_color = None
                        segment_start = None
                        
                        for i, (val, color) in enumerate(zip(stoch_vals, colors)):
                            if val is not None:
                                if color != current_color:
                                    # End previous segment
                                    if current_color is not None and segment_start is not None:
                                        ax_heatmap.plot(
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
                                    ax_heatmap.plot(
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
                            ax_heatmap.plot(
                                x_indices[segment_start:],
                                [y_pos] * (len(x_indices) - segment_start),
                                color=current_color,
                                linewidth=line_width,
                                solid_capstyle='round',
                                alpha=0.9,
                            )

                # Plot fast and slow lines (oscillator lines) in separate subplot
                fast_line = shm_result["fast_line"][display_start:]
                slow_line = shm_result["slow_line"][display_start:]
                
                # Determine line colors based on theme - use bright, contrasting colors
                theme = str(self.params.get("theme", "Theme 3"))
                if theme == "Theme 1":
                    fast_color = "#ffffff"  # Bright white
                    slow_color = "#c0c0c0"  # Silver
                elif theme == "Theme 2":
                    fast_color = "#ffffff"  # Bright white
                    slow_color = "#0080ff"  # Bright blue
                else:  # Theme 3
                    fast_color = "#ffffff"  # Bright white
                    slow_color = "#ff8000"  # Bright orange
                
                # Plot lines in oscillator subplot with thicker lines
                ax_oscillator.plot(
                    x_indices, fast_line, 
                    color=fast_color, 
                    linewidth=3.0, 
                    label="Fast", 
                    alpha=1.0,
                    zorder=10
                )
                ax_oscillator.plot(
                    x_indices, slow_line, 
                    color=slow_color, 
                    linewidth=3.0, 
                    label="Slow", 
                    alpha=1.0,
                    zorder=10
                )

                # Set axis limits and labels for heat map
                ax_heatmap.set_xlim(0, len(x_indices) - 1)
                ax_heatmap.set_ylim(-0.5, plot_number + 0.5)
                ax_heatmap.set_ylabel("Stochastic Index", color='white', fontsize=11)
                ax_heatmap.set_title(f"Stochastic Heat Map - {sym}", color='white', fontsize=14, fontweight='bold')
                ax_heatmap.grid(True, alpha=0.2, color='gray', linestyle='--')
                ax_heatmap.tick_params(colors='white', labelsize=9)
                ax_heatmap.spines['bottom'].set_color('gray')
                ax_heatmap.spines['top'].set_color('gray')
                ax_heatmap.spines['left'].set_color('gray')
                ax_heatmap.spines['right'].set_color('gray')
                
                # Set axis limits and labels for oscillator
                fast_min = min([v for v in fast_line if v is not None] or [0])
                fast_max = max([v for v in fast_line if v is not None] or [plot_number])
                slow_min = min([v for v in slow_line if v is not None] or [0])
                slow_max = max([v for v in slow_line if v is not None] or [plot_number])
                y_min = min(fast_min, slow_min) - 1
                y_max = max(fast_max, slow_max) + 1
                
                ax_oscillator.set_xlim(0, len(x_indices) - 1)
                ax_oscillator.set_ylim(y_min, y_max)
                ax_oscillator.set_xlabel("Bar Index", color='white', fontsize=11)
                ax_oscillator.set_ylabel("Oscillator Value", color='white', fontsize=11)
                ax_oscillator.grid(True, alpha=0.3, color='gray', linestyle='--')
                ax_oscillator.tick_params(colors='white', labelsize=9)
                ax_oscillator.spines['bottom'].set_color('gray')
                ax_oscillator.spines['top'].set_color('gray')
                ax_oscillator.spines['left'].set_color('gray')
                ax_oscillator.spines['right'].set_color('gray')
                ax_oscillator.legend(loc='upper right', facecolor='#2a2a2a', edgecolor='gray', labelcolor='white', fontsize=10)

                # Encode figure to data URL
                label = str(sym)
                image_data = _encode_fig_to_data_url(fig, dpi=dpi)
                images[label] = image_data
                logger.warning(f"✅ StochasticHeatmapPlot: Generated chart for {sym}, image size: {len(image_data)} chars")

                # Emit partial result
                self.emit_partial_result({"images": {label: image_data}})

                # Store FULL OHLCV data (not just display range) for downstream nodes
                # This maintains data integrity for filters and other nodes that need full history
                ohlcv_bundle_output[sym] = ohlcv_data

            except Exception as e:
                logger.error(f"❌ StochasticHeatmapPlot: Error processing {sym}: {e}", exc_info=True)
                continue

        logger.warning(f"🔵 StochasticHeatmapPlot: Completed. Generated {len(images)} images")

        return {
            "images": images,
            "stochastic_heatmap_data": shm_data_by_symbol,
            "ohlcv_bundle": ohlcv_bundle_output,
        }

