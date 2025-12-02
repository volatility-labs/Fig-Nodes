"""
Fractal Dimension Plot Node

Creates combined chart with price OHLC bars, Fractals ATR Block indicators, and Fractal Dimension Adaptive (DSSAKAMA).
Combines both indicators similar to how HurstPlot combines multiple indicators.
"""

import base64
import io
import logging
from datetime import datetime
from typing import TYPE_CHECKING, Any, Optional

import matplotlib
import matplotlib.ticker

matplotlib.use("Agg")  # non-interactive backend for server-side rendering
import matplotlib.pyplot as plt

# Configure matplotlib for StockCharts-quality rendering
plt.rcParams.update({
    'figure.dpi': 250,
    'savefig.dpi': 250,
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

from core.api_key_vault import APIKeyVault
from core.types_registry import AssetSymbol, NodeCategory, NodeValidationError, OHLCVBar, get_type
from nodes.base.base_node import Base
from nodes.core.market.utils.hurst_plot_node import (
    _encode_fig_to_data_url,
    _normalize_bars,
    _plot_candles,
)
from services.indicator_calculators.ema_calculator import calculate_ema
from services.indicator_calculators.fractals_atr_calculator import calculate_fractals_atr
from services.indicator_calculators.fractal_dimension_adaptive_calculator import (
    calculate_fractal_dimension_adaptive,
)
from services.polygon_service import fetch_current_snapshot

logger = logging.getLogger(__name__)


def _plot_fractals_atr_on_price(
    ax: "Axes",
    timestamps: list[int],
    up_fractals: list[bool],
    down_fractals: list[bool],
    atr_up_breaks: list[float | None],
    atr_down_breaks: list[float | None],
    fractal_roc_up: list[float | None],
    fractal_roc_down: list[float | None],
    highs: list[float],
    lows: list[float],
    show_fractals: bool = True,
    show_atr_breaks: bool = True,
    last_signal_idx: Optional[int] = None,
    last_signal_type: Optional[str] = None,
) -> None:
    """Plot Fractals ATR indicators on the price chart axes."""
    if not timestamps:
        return
    
    # Plot ATR breaks as labels/annotations
    for i in range(len(timestamps)):
        is_last_signal = last_signal_idx is not None and i == last_signal_idx
        is_last_bullish = is_last_signal and last_signal_type in ("bullish", "both")
        is_last_bearish = is_last_signal and last_signal_type in ("bearish", "both")
        # Make last signal more prominent
        fontsize = 10 if is_last_signal else 8
        edgewidth = 2.0 if is_last_signal else 1.0
        alpha = 1.0 if is_last_signal else 0.9
        # ATR Up Break (lime/green) - BULLISH signal
        if show_atr_breaks and atr_up_breaks[i] is not None and atr_up_breaks[i] > 0:
            label_text = f"AB{atr_up_breaks[i]:.2f}"
            if is_last_bullish:
                label_text = f"LAST: {label_text}"  # Mark as last signal
            ax.annotate(
                label_text,
                xy=(i, lows[i] if i < len(lows) else 0),
                xytext=(0, -15),
                textcoords="offset points",
                fontsize=fontsize,
                color='black',
                bbox=dict(boxstyle="round,pad=0.3", facecolor='lime', edgecolor='black', linewidth=edgewidth, alpha=alpha),
                ha='center',
                va='top',
                zorder=11 if is_last_signal else 10,  # Higher zorder for last signal
            )
        
        # ATR Down Break (red) - BEARISH signal
        if show_atr_breaks and atr_down_breaks[i] is not None and atr_down_breaks[i] > 0:
            label_text = f"AB{atr_down_breaks[i]:.2f}"
            if is_last_bearish:
                label_text = f"LAST: {label_text}"  # Mark as last signal
            ax.annotate(
                label_text,
                xy=(i, highs[i] if i < len(highs) else 0),
                xytext=(0, 15),
                textcoords="offset points",
                fontsize=fontsize,
                color='white',
                bbox=dict(boxstyle="round,pad=0.3", facecolor='red', edgecolor='black', linewidth=edgewidth, alpha=alpha),
                ha='center',
                va='bottom',
                zorder=11 if is_last_signal else 10,  # Higher zorder for last signal
            )
        
        # Fractal ROC Up (lime/green) - BULLISH signal (downFractal AND rocup > roclevel)
        if show_fractals and fractal_roc_up[i] is not None and fractal_roc_up[i] > 0:
            label_text = f"FR{fractal_roc_up[i]:.2f}"
            if is_last_bullish:
                label_text = f"LAST: {label_text}"  # Mark as last signal
            ax.annotate(
                label_text,
                xy=(i, lows[i] if i < len(lows) else 0),
                xytext=(0, -30),
                textcoords="offset points",
                fontsize=fontsize,
                color='black',
                bbox=dict(boxstyle="round,pad=0.3", facecolor='lime', edgecolor='black', linewidth=edgewidth, alpha=alpha),
                ha='center',
                va='top',
                zorder=11 if is_last_signal else 10,  # Higher zorder for last signal
            )
        
        # Fractal ROC Down (red) - BEARISH signal (upFractal AND rocdn > roclevel)
        if show_fractals and fractal_roc_down[i] is not None and fractal_roc_down[i] > 0:
            label_text = f"FR{fractal_roc_down[i]:.2f}"
            if is_last_bearish:
                label_text = f"LAST: {label_text}"  # Mark as last signal
            ax.annotate(
                label_text,
                xy=(i, highs[i] if i < len(highs) else 0),
                xytext=(0, 30),
                textcoords="offset points",
                fontsize=fontsize,
                color='white',
                bbox=dict(boxstyle="round,pad=0.3", facecolor='red', edgecolor='black', linewidth=edgewidth, alpha=alpha),
                ha='center',
                va='bottom',
                zorder=11 if is_last_signal else 10,  # Higher zorder for last signal
            )
        
        # Mark fractals with markers
        if show_fractals:
            if up_fractals[i] and i < len(highs):
                ax.plot(i, highs[i], 'v', color='red', markersize=8, zorder=9, alpha=0.8)
            
            if down_fractals[i] and i < len(lows):
                ax.plot(i, lows[i], '^', color='lime', markersize=8, zorder=9, alpha=0.8)


def _plot_fractal_dimension_adaptive(
    ax: "Axes",
    timestamps: list[int],
    signal: list[float | None],
    outer: list[float | None],
    kama: list[float | None] | None = None,
) -> None:
    """Plot Fractal Dimension Adaptive (DSSAKAMA) indicators on the given axes."""
    if not timestamps:
        return
    
    ax.set_facecolor('#ffffff')
    
    x_indices = list(range(len(timestamps)))
    
    # Color constants
    greencolor = '#2DD204'
    redcolor = '#D2042D'
    
    # Plot zero line (50)
    ax.axhline(y=50, color='gray', linestyle='--', linewidth=1, alpha=0.3, zorder=0)
    
    # Plot signal line (white)
    valid_signal_indices = [i for i, v in enumerate(signal) if v is not None]
    if valid_signal_indices:
        valid_signal_x = [x_indices[i] for i in valid_signal_indices]
        valid_signal_values = [signal[i] for i in valid_signal_indices]
        ax.plot(valid_signal_x, valid_signal_values, color='white', linewidth=1, label='Signal', zorder=2)
    
    # Plot outer line (green when > signal, red when <= signal)
    valid_outer_indices = [i for i, v in enumerate(outer) if v is not None and i < len(signal) and signal[i] is not None]
    if valid_outer_indices:
        # Split into segments based on color
        segments: list[tuple[list[int], str]] = []
        current_segment: list[int] = []
        current_color = None
        
        for i in valid_outer_indices:
            if outer[i] is not None and signal[i] is not None:
                color = greencolor if outer[i] > signal[i] else redcolor
                if current_color != color:
                    if current_segment:
                        segments.append((current_segment, current_color))
                    current_segment = [i]
                    current_color = color
                else:
                    current_segment.append(i)
        
        if current_segment:
            segments.append((current_segment, current_color))
        
        # Plot segments - only label the first one to avoid duplicate legend entries
        for idx, (segment_indices, color) in enumerate(segments):
            segment_x = [x_indices[i] for i in segment_indices]
            segment_values = [outer[i] for i in segment_indices if outer[i] is not None]
            if len(segment_x) == len(segment_values):
                # Only add label to first segment to avoid duplicate legend entries
                label = 'Outer' if idx == 0 else ''
                ax.plot(segment_x, segment_values, color=color, linewidth=2, label=label, zorder=3)
    
    # Set Y-axis limits (0 to 100 for stochastic)
    ax.set_ylim(0, 100)
    
    # Add annotations for current values
    if valid_outer_indices and valid_signal_indices:
        last_outer_idx = valid_outer_indices[-1] if valid_outer_indices else None
        last_signal_idx = valid_signal_indices[-1] if valid_signal_indices else None
        
        if last_outer_idx is not None and outer[last_outer_idx] is not None:
            outer_value = outer[last_outer_idx]
            signal_value = signal[last_signal_idx] if last_signal_idx is not None and signal[last_signal_idx] is not None else None
            
            color = greencolor if signal_value is not None and outer_value > signal_value else redcolor
            
            ax.annotate(
                f"Outer: {outer_value:.2f}",
                xy=(len(x_indices) - 1, float(outer_value)),
                xytext=(8, 8),
                textcoords="offset points",
                fontsize=9,
                color=color,
                fontweight='bold',
                bbox=dict(boxstyle="round,pad=0.3", facecolor='white', edgecolor=color, alpha=0.95, linewidth=1.5),
                ha='left',
                va='bottom'
            )
        
        if last_signal_idx is not None and signal[last_signal_idx] is not None:
            signal_value = signal[last_signal_idx]
            ax.annotate(
                f"Signal: {signal_value:.2f}",
                xy=(len(x_indices) - 1, float(signal_value)),
                xytext=(8, -8),
                textcoords="offset points",
                fontsize=9,
                color='black',
                fontweight='bold',
                bbox=dict(boxstyle="round,pad=0.3", facecolor='white', edgecolor='black', alpha=0.95, linewidth=1.5),
                ha='left',
                va='top'
            )
    
    ax.grid(True, alpha=0.7, linestyle='-', linewidth=0.8, color='#c0c0c0', zorder=0)
    ax.set_axisbelow(True)
    for spine in ax.spines.values():
        spine.set_color('#cccccc')
        spine.set_linewidth(0.8)
    
    ax.legend(loc='upper left', fontsize=8, framealpha=0.9, fancybox=False, shadow=False, frameon=True)


class FractalDimensionPlot(Base):
    """
    Renders OHLCV data with Fractal Dimension indicators (Fractals ATR Block + Fractal Dimension Adaptive).
    
    Creates a combined chart with:
    - Top panel: Price OHLC bars with Fractals ATR indicators, VBP and volume
    - Bottom panel: Fractal Dimension Adaptive (DSSAKAMA) indicators (optional)
    
    Inputs: 'ohlcv_bundle' (Dict[AssetSymbol, List[OHLCVBar]])
    Output: 'images' -> Dict[str, str] mapping label to data URL
    """

    inputs = {
        "ohlcv_bundle": get_type("OHLCVBundle") | None,
    }
    optional_inputs = ["ohlcv_bundle", "ohlcv"]

    outputs = {
        "images": get_type("ConfigDict"),
        "fractals_atr_data": get_type("ConfigDict"),
        "fractal_dimension_adaptive_data": get_type("ConfigDict"),
        "ohlcv_bundle": get_type("OHLCVBundle"),
    }

    CATEGORY = NodeCategory.MARKET
    
    default_params = {
        "lookback_bars": None,  # Default to showing all bars
        "zoom_to_recent": False,  # Auto-zoom to last 300 bars for better visibility
        "y_axis_scale": "linear",  # "linear" (default) for price charts, "log" for exponential growth
        "show_current_price": True,  # Annotate current price on chart
        "max_symbols": 100,
        "show_volume_by_price": True,
        "volume_by_price_bars": 12,
        "volume_by_price_color_volume": False,
        "volume_by_price_opacity": 0.3,
        "atr_period": 325,
        "fractals_periods": 1,
        "roc_break_level": 2.0,
        "atr_break_level": 1.5,
        "show_fractals": True,
        "show_atr_breaks": True,
        "show_fractal_dimension_adaptive": True,
        "period": 10,
        "kama_fastend": 2.0,
        "kama_slowend": 30.0,
        "efratiocalc": "Fractal Dimension Adaptive",
        "jcount": 2,
        "smooth_power": 2,
        "stoch_len": 30,
        "sm_ema": 9,
        "sig_ema": 5,
        "dpi": 250,  # Image DPI: 250 for high quality (default), reduce to 150-200 for smaller API payloads
    }

    params_meta = [
        {
            "name": "lookback_bars",
            "type": "number",
            "default": None,
            "description": "Number of bars to plot (None = all). Use this to zoom in on recent data while still calculating with full history. Recommended: 500-2000 for better visibility.",
            "min": 10,
            "max": 10000,
            "step": 100,
        },
        {
            "name": "zoom_to_recent",
            "type": "combo",
            "default": False,
            "options": [True, False],
            "description": "Auto-zoom to last 300 bars (~12 days hourly) for better visibility (still calculates with full history)",
        },
        {
            "name": "y_axis_scale",
            "type": "combo",
            "default": "linear",
            "options": ["linear", "log"],
            "description": "Y-axis scale: 'linear' (default, recommended for prices), 'log' for exponential growth",
        },
        {
            "name": "show_current_price",
            "type": "boolean",
            "default": True,
            "description": "Annotate current price on chart for better visibility",
        },
        {
            "name": "max_symbols",
            "type": "number",
            "default": 100,
            "description": "Maximum number of symbols to process",
        },
        {
            "name": "show_volume_by_price",
            "type": "boolean",
            "default": True,
            "description": "Show VBP bars on price chart",
        },
        {
            "name": "volume_by_price_bars",
            "type": "number",
            "default": 12,
            "description": "Number of Volume-by-Price bars",
        },
        {
            "name": "volume_by_price_color_volume",
            "type": "boolean",
            "default": False,
            "description": "Color VBP bars by up/down volume",
        },
        {
            "name": "volume_by_price_opacity",
            "type": "number",
            "default": 0.3,
            "description": "Opacity of VBP bars (0.0 to 1.0)",
        },
        {
            "name": "atr_period",
            "type": "number",
            "default": 325,
            "description": "ATR period for break detection",
        },
        {
            "name": "fractals_periods",
            "type": "number",
            "default": 1,
            "description": "Fractals periods",
        },
        {
            "name": "roc_break_level",
            "type": "number",
            "default": 2.0,
            "description": "ROC break level threshold",
        },
        {
            "name": "atr_break_level",
            "type": "number",
            "default": 1.5,
            "description": "ATR break level threshold",
        },
        {
            "name": "show_fractals",
            "type": "boolean",
            "default": True,
            "description": "Show fractal markers",
        },
        {
            "name": "show_atr_breaks",
            "type": "boolean",
            "default": True,
            "description": "Show ATR break labels",
        },
        {
            "name": "show_fractal_dimension_adaptive",
            "type": "boolean",
            "default": True,
            "description": "Show DSSAKAMA indicator panel",
        },
        {
            "name": "period",
            "type": "number",
            "default": 10,
            "description": "KAMA period",
        },
        {
            "name": "kama_fastend",
            "type": "number",
            "default": 2.0,
            "description": "Kaufman AMA fast-end period",
        },
        {
            "name": "kama_slowend",
            "type": "number",
            "default": 30.0,
            "description": "Kaufman AMA slow-end period",
        },
        {
            "name": "efratiocalc",
            "type": "text",
            "default": "Fractal Dimension Adaptive",
            "description": "Efficiency ratio calculation type",
        },
        {
            "name": "jcount",
            "type": "number",
            "default": 2,
            "description": "Fractal dimension count",
        },
        {
            "name": "smooth_power",
            "type": "number",
            "default": 2,
            "description": "Kaufman power smoothing",
        },
        {
            "name": "stoch_len",
            "type": "number",
            "default": 30,
            "description": "Stochastic smoothing period",
        },
        {
            "name": "sm_ema",
            "type": "number",
            "default": 9,
            "description": "Intermediate EMA smoothing period",
        },
        {
            "name": "sig_ema",
            "type": "number",
            "default": 5,
            "description": "Signal EMA smoothing period",
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
    ]

    async def _execute_impl(self, inputs: dict[str, Any]) -> dict[str, Any]:
        bundle: dict[AssetSymbol, list[OHLCVBar]] | None = inputs.get("ohlcv_bundle")
        single_bundle: dict[AssetSymbol, list[OHLCVBar]] | None = inputs.get("ohlcv")

        if bundle is not None and single_bundle is not None:
            bundle = {**bundle, **single_bundle}
        elif single_bundle is not None:
            bundle = single_bundle
        elif bundle is None:
            bundle = {}

        # Allow empty bundles (e.g., when filter returns no symbols)
        if bundle is None:
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
        fractals_atr_data_by_symbol: dict[str, dict[str, Any]] = {}
        fractal_dimension_adaptive_data_by_symbol: dict[str, dict[str, Any]] = {}
        ohlcv_bundle_output: dict[AssetSymbol, list[OHLCVBar]] = {}

        max_syms_raw = self.params.get("max_symbols") or 100
        max_syms = 100
        if isinstance(max_syms_raw, (int, float, str)):
            try:
                max_syms = int(max_syms_raw)
            except (ValueError, TypeError):
                max_syms = 100

        atr_period = int(self.params.get("atr_period", 325))
        fractals_periods = int(self.params.get("fractals_periods", 1))
        roc_break_level = float(self.params.get("roc_break_level", 2.0))
        atr_break_level = float(self.params.get("atr_break_level", 1.5))
        show_fractals = bool(self.params.get("show_fractals", True))
        show_atr_breaks = bool(self.params.get("show_atr_breaks", True))
        show_fractal_dim_adaptive = bool(self.params.get("show_fractal_dimension_adaptive", True))

        period = int(self.params.get("period", 10))
        kama_fastend = float(self.params.get("kama_fastend", 2.0))
        kama_slowend = float(self.params.get("kama_slowend", 30.0))
        efratiocalc = str(self.params.get("efratiocalc", "Fractal Dimension Adaptive"))
        jcount = int(self.params.get("jcount", 2))
        smooth_power = int(self.params.get("smooth_power", 2))
        stoch_len = int(self.params.get("stoch_len", 30))
        sm_ema = int(self.params.get("sm_ema", 9))
        sig_ema = int(self.params.get("sig_ema", 5))

        symbols = list(bundle.keys())[:max_syms]

        for sym in symbols:
            bars = bundle[sym]
            if not bars:
                logger.warning(f"⚠️ FractalDimensionPlot: No bars provided for {sym}")
                continue

            norm, volumes = _normalize_bars(bars)
            if not norm:
                continue

            # Store full data for calculations (we calculate with full history)
            full_norm = norm
            full_volumes = volumes

            # Determine display data (for plotting)
            zoom_to_recent = bool(self.params.get("zoom_to_recent", False))
            display_norm = norm
            display_volumes = volumes

            # Apply zoom_to_recent if enabled (auto-zoom to last 300 bars)
            if zoom_to_recent and len(norm) > 300:
                display_norm = norm[-300:]
                display_volumes = volumes[-300:]

            # Apply lookback filter if specified (overrides zoom_to_recent)
            if lookback is not None and lookback > 0:
                display_norm = norm[-lookback:]
                display_volumes = volumes[-lookback:]

            ohlcv_bundle_output[sym] = bars

            # Extract price data for calculations (use full data)
            calc_timestamps = [x[0] for x in full_norm]
            calc_opens = [x[1] for x in full_norm]
            calc_highs = [x[2] for x in full_norm]
            calc_lows = [x[3] for x in full_norm]
            calc_closes = [x[4] for x in full_norm]

            # Extract price data for display (use display data)
            if not display_norm:
                logger.warning(f"⚠️ FractalDimensionPlot: No display data after filtering for {sym}")
                continue
            
            timestamps = [x[0] for x in display_norm]
            opens = [x[1] for x in display_norm]
            highs = [x[2] for x in display_norm]
            lows = [x[3] for x in display_norm]
            closes = [x[4] for x in display_norm]

            # Calculate Fractals ATR (use full data for calculations)
            fractals_atr_result = calculate_fractals_atr(
                highs=calc_highs,
                lows=calc_lows,
                opens=calc_opens,
                closes=calc_closes,
                atr_period=atr_period,
                fractals_periods=fractals_periods,
                roc_break_level=roc_break_level,
                atr_break_level=atr_break_level,
            )

            last_signal_index_full = fractals_atr_result.get("last_signal_index")
            last_signal_type = fractals_atr_result.get("last_signal_type")
            display_last_signal_idx: Optional[int] = None

            # Slice results to match display data
            # Ensure indicator results match display data length
            calc_length = len(fractals_atr_result["up_fractals"])
            display_length = len(timestamps)
            start_idx = 0
            if calc_length > display_length:
                start_idx = calc_length - display_length
                fractals_atr_result = {
                    "up_fractals": fractals_atr_result["up_fractals"][start_idx:],
                    "down_fractals": fractals_atr_result["down_fractals"][start_idx:],
                    "atr_up_breaks": fractals_atr_result["atr_up_breaks"][start_idx:],
                    "atr_down_breaks": fractals_atr_result["atr_down_breaks"][start_idx:],
                    "fractal_roc_up": fractals_atr_result["fractal_roc_up"][start_idx:],
                    "fractal_roc_down": fractals_atr_result["fractal_roc_down"][start_idx:],
                    "atr": fractals_atr_result["atr"][start_idx:],
                }
            elif calc_length < display_length:
                # This shouldn't happen, but log a warning
                logger.warning(f"⚠️ Fractals ATR result length ({calc_length}) < display length ({display_length}) for {sym}")
                # Use what we have
                pass

            if isinstance(last_signal_index_full, int) and last_signal_index_full >= 0:
                if calc_length > display_length:
                    if last_signal_index_full >= start_idx:
                        display_last_signal_idx = last_signal_index_full - start_idx
                else:
                    display_last_signal_idx = last_signal_index_full

            # If calc_length == display_length, no slicing needed - use as is

            fractals_atr_data_by_symbol[str(sym)] = {
                "up_fractals": fractals_atr_result["up_fractals"],
                "down_fractals": fractals_atr_result["down_fractals"],
                "atr_up_breaks": fractals_atr_result["atr_up_breaks"],
                "atr_down_breaks": fractals_atr_result["atr_down_breaks"],
                "fractal_roc_up": fractals_atr_result["fractal_roc_up"],
                "fractal_roc_down": fractals_atr_result["fractal_roc_down"],
                "atr": fractals_atr_result["atr"],
                "timestamps": timestamps,
                "last_signal_index": display_last_signal_idx,
                "last_signal_type": last_signal_type,
            }

            # Calculate Fractal Dimension Adaptive if enabled (use full data for calculations)
            fractal_dim_result = None
            if show_fractal_dim_adaptive:
                fractal_dim_result = calculate_fractal_dimension_adaptive(
                    closes=calc_closes,
                    highs=calc_highs,
                    lows=calc_lows,
                    period=period,
                    kama_fastend=kama_fastend,
                    kama_slowend=kama_slowend,
                    efratiocalc=efratiocalc,
                    jcount=jcount,
                    smooth_power=smooth_power,
                    stoch_len=stoch_len,
                    sm_ema=sm_ema,
                    sig_ema=sig_ema,
                )

                # Slice results to match display data
                calc_length = len(fractal_dim_result["signal"])
                display_length = len(timestamps)
                if calc_length > display_length:
                    start_idx = calc_length - display_length
                    fractal_dim_result = {
                        "kama": fractal_dim_result["kama"][start_idx:],
                        "signal": fractal_dim_result["signal"][start_idx:],
                        "outer": fractal_dim_result["outer"][start_idx:],
                        "stoch": fractal_dim_result["stoch"][start_idx:],
                    }
                elif calc_length < display_length:
                    # This shouldn't happen, but log a warning
                    logger.warning(f"⚠️ Fractal Dimension Adaptive result length ({calc_length}) < display length ({display_length}) for {sym}")
                    # Use what we have
                    pass

                fractal_dimension_adaptive_data_by_symbol[str(sym)] = {
                    "kama": fractal_dim_result["kama"],
                    "signal": fractal_dim_result["signal"],
                    "outer": fractal_dim_result["outer"],
                    "stoch": fractal_dim_result["stoch"],
                    "timestamps": timestamps,
                }

            # Fetch fresh price snapshot
            fresh_price: float | None = None
            try:
                api_key = APIKeyVault().get("POLYGON_API_KEY")
                if api_key:
                    fresh_price, _ = await fetch_current_snapshot(sym, api_key)
                    if fresh_price and fresh_price > 0:
                        logger.warning(f"🔄 Fresh snapshot for {sym}: ${fresh_price:.4f}")
            except Exception as e:
                logger.warning(f"Failed to fetch snapshot for {sym}: {e}")

            # Calculate EMAs (use full data for calculations, then slice to display)
            ema_10_result = calculate_ema(calc_closes, period=10) if len(calc_closes) >= 10 else {"ema": []}
            ema_30_result = calculate_ema(calc_closes, period=30) if len(calc_closes) >= 30 else {"ema": []}
            ema_100_result = calculate_ema(calc_closes, period=100) if len(calc_closes) >= 100 else {"ema": []}
            ema_10_full = ema_10_result.get("ema", [])
            ema_30_full = ema_30_result.get("ema", [])
            ema_100_full = ema_100_result.get("ema", [])

            # Slice EMAs to match display data
            display_length = len(timestamps)
            if len(ema_10_full) > display_length:
                start_idx = len(ema_10_full) - display_length
                ema_10 = ema_10_full[start_idx:]
                ema_30 = ema_30_full[start_idx:]
                ema_100 = ema_100_full[start_idx:]
            elif len(ema_10_full) < display_length:
                # EMA might be shorter due to period requirements, pad with None
                logger.warning(f"⚠️ EMA length ({len(ema_10_full)}) < display length ({display_length}) for {sym}, padding with None")
                padding = [None] * (display_length - len(ema_10_full))
                ema_10 = padding + ema_10_full
                ema_30 = padding + ema_30_full
                ema_100 = padding + ema_100_full
            else:
                ema_10 = ema_10_full
                ema_30 = ema_30_full
                ema_100 = ema_100_full

            # Create figure with subplots (2 if fractal dim adaptive enabled, 1 otherwise)
            # Use taller aspect ratio to avoid narrow charts - similar to enhanced plot but with more height
            # Explicitly close any existing figure and create a fresh one each time to avoid matplotlib state issues
            plt.close('all')  # Close all existing figures to prevent state leakage
            if show_fractal_dim_adaptive:
                # For 2 subplots: wider width (12) with taller height (12) for better proportions
                fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 12), sharex=True, height_ratios=[2.25, 1.0])
                fig.subplots_adjust(hspace=0.20, top=0.88, bottom=0.07, left=0.08, right=0.95)
            else:
                # For 1 subplot: wider width (12) with taller height (9) for better proportions
                fig, ax1 = plt.subplots(1, 1, figsize=(12, 9))
                fig.subplots_adjust(top=0.88, bottom=0.07, left=0.08, right=0.95)
                ax2 = None
            
            # Top panel: Price chart with VBP, volume, and Fractals ATR indicators
            show_vbp = bool(self.params.get("show_volume_by_price", True))
            vbp_bars = int(self.params.get("volume_by_price_bars", 12))
            vbp_color_volume = bool(self.params.get("volume_by_price_color_volume", False))
            vbp_opacity = float(self.params.get("volume_by_price_opacity", 0.3))

            # Set y-axis scale
            y_axis_scale_raw = self.params.get("y_axis_scale", "linear")
            y_axis_scale = str(y_axis_scale_raw) if y_axis_scale_raw else "linear"
            if y_axis_scale not in ["linear", "log"]:
                y_axis_scale = "linear"  # Default to linear if invalid
            
            try:
                if y_axis_scale == "log":
                    ax1.set_yscale('log')
                else:
                    ax1.set_yscale('linear')
            except Exception as e:
                logger.warning(f"Failed to set y_axis_scale '{y_axis_scale}': {e}. Using linear.")
                ax1.set_yscale("linear")

            # Disable autoscaling to prevent matplotlib from overriding our Y-axis limits
            ax1.set_autoscaley_on(False)
            
            show_current_price_param = bool(self.params.get("show_current_price", True))
            _plot_candles(
                ax1, display_norm, display_volumes, ema_10, ema_30, ema_100,
                show_current_price=show_current_price_param, current_price_override=fresh_price,
                show_volume_by_price=show_vbp,
                volume_by_price_bars=vbp_bars,
                volume_by_price_color_volume=vbp_color_volume,
                volume_by_price_opacity=vbp_opacity,
            )
            
            # Overlay Fractals ATR indicators on price chart
            _plot_fractals_atr_on_price(
                ax1, timestamps,
                fractals_atr_result["up_fractals"] if show_fractals else [False] * len(timestamps),
                fractals_atr_result["down_fractals"] if show_fractals else [False] * len(timestamps),
                fractals_atr_result["atr_up_breaks"] if show_atr_breaks else [None] * len(timestamps),
                fractals_atr_result["atr_down_breaks"] if show_atr_breaks else [None] * len(timestamps),
                fractals_atr_result["fractal_roc_up"] if show_fractals else [None] * len(timestamps),
                fractals_atr_result["fractal_roc_down"] if show_fractals else [None] * len(timestamps),
                highs, lows,
                show_fractals, show_atr_breaks,
                display_last_signal_idx,
                last_signal_type,
            )
            
            ax1.set_title(f"{str(sym)} Price Chart with Fractals ATR", fontsize=12, fontweight='bold', pad=10)
            ax1.set_ylabel("Price", fontsize=10)
            ax1.tick_params(axis='y', labelsize=9, which='major', left=True, labelleft=True)
            ax1.yaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda x, p: f'${x:.4f}' if x < 1 else f'${x:.2f}'))  # type: ignore
            ax1.yaxis.set_ticks_position('left')
            ax1.tick_params(axis='y', direction='out', length=4, width=1)

            # Bottom panel: Fractal Dimension Adaptive (if enabled)
            if show_fractal_dim_adaptive and ax2 is not None and fractal_dim_result is not None:
                _plot_fractal_dimension_adaptive(
                    ax2, timestamps,
                    fractal_dim_result["signal"],
                    fractal_dim_result["outer"],
                    fractal_dim_result.get("kama"),
                )
                ax2.set_title(f"{str(sym)} DSS of Advanced Kaufman AMA [Loxx]", fontsize=12, fontweight='bold', pad=10)
                ax2.set_ylabel("DSSAKAMA", fontsize=10)
                ax2.tick_params(labelsize=9)

            # Set time x-axis labels on bottommost panel
            bottom_ax = ax2 if ax2 is not None else ax1
            if len(display_norm) > 0:
                timestamps_for_labels = [x[0] for x in display_norm]
                try:
                    dates = [datetime.fromtimestamp(ts / 1000) for ts in timestamps_for_labels]
                    if len(dates) > 0:
                        num_labels = min(8, len(dates))
                        if num_labels > 1:
                            step = max(1, len(dates) // num_labels)
                            label_indices = list(range(0, len(dates), step))
                            if len(dates) - 1 not in label_indices:
                                label_indices.append(len(dates) - 1)
                            
                            label_positions = label_indices
                            label_dates = [dates[i] for i in label_indices]
                            
                            time_span = (dates[-1] - dates[0]).total_seconds()
                            if time_span < 86400 * 2:
                                date_labels = [d.strftime("%H:%M") for d in label_dates]
                            elif time_span < 86400 * 30:
                                date_labels = [d.strftime("%d/%m") for d in label_dates]
                            else:
                                date_labels = [d.strftime("%b %Y") for d in label_dates]
                            
                            bottom_ax.set_xticks(label_positions)
                            bottom_ax.set_xticklabels(date_labels, fontsize=8, rotation=45, ha='right')
                            bottom_ax.set_xlabel("Time", fontsize=10)
                        else:
                            bottom_ax.set_xlabel("Time", fontsize=10)
                except Exception as e:
                    logger.warning(f"Failed to format time axis for {sym}: {e}")
                    bottom_ax.set_xlabel("Time", fontsize=10)

            # Set Y-axis limits for price chart
            # Ensure charts use full vertical space even for tight price ranges
            if len(display_norm) > 0:
                current_price = fresh_price if fresh_price is not None and fresh_price > 0 else display_norm[-1][4]
                all_prices = [bar[1] for bar in display_norm] + [bar[2] for bar in display_norm] + [bar[3] for bar in display_norm] + [bar[4] for bar in display_norm]
                if fresh_price is not None and fresh_price > 0:
                    all_prices.append(fresh_price)
                full_min = min(all_prices)
                full_max = max(all_prices)
                range_min = min(full_min, current_price)
                range_max = max(full_max, current_price)
                price_range = max(range_max - range_min, 1e-9)

                # Minimum chart range: at least 2.5% of price or $0.05, whichever is greater
                min_range_threshold = max(current_price * 0.025, 0.05)

                # Use 10% of actual range as padding (or a tiny fallback if range is nearly flat)
                padding = price_range * 0.10 if price_range > 0 else max(current_price * 0.0025, 0.01)

                y_min = range_min - padding
                y_max = range_max + padding

                # Determine desired range after padding
                final_range = y_max - y_min
                target_range = max(price_range, min_range_threshold)
                if final_range < target_range:
                    extra = (target_range - final_range) / 2
                    y_min -= extra
                    y_max += extra

                # Add a small additional margin (2% of target range) for visual breathing room
                margin = target_range * 0.02
                y_min -= margin
                y_max += margin

                # Prevent negative price axis
                y_min = max(y_min, 0.0)

                ax1.set_ylim(y_min, y_max)

            fig.patch.set_edgecolor('#d0d0d0')
            fig.patch.set_linewidth(3.0)
            fig.patch.set_facecolor('#ffffff')

            dpi = int(self.params.get("dpi", self.default_params.get("dpi", 250)))
            image_data = _encode_fig_to_data_url(fig, dpi=dpi)
            images[str(sym)] = image_data

            self.emit_partial_result({"images": {str(sym): image_data}})

        return {
            "images": images,
            "fractals_atr_data": fractals_atr_data_by_symbol,
            "fractal_dimension_adaptive_data": fractal_dimension_adaptive_data_by_symbol if show_fractal_dim_adaptive else {},
            "ohlcv_bundle": ohlcv_bundle_output,
        }

