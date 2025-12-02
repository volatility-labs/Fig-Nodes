"""
Fractal Dimension Adaptive Plot Node

Creates combined chart with price OHLC bars and Fractal Dimension Adaptive (DSSAKAMA) indicators.
Based on TradingView PineScript indicator "DSS of Advanced Kaufman AMA [Loxx]" by loxx.
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
from services.indicator_calculators.fractal_dimension_adaptive_calculator import (
    calculate_fractal_dimension_adaptive,
)
from services.polygon_service import fetch_current_snapshot

logger = logging.getLogger(__name__)


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
        
        for segment_indices, color in segments:
            segment_x = [x_indices[i] for i in segment_indices]
            segment_values = [outer[i] for i in segment_indices if outer[i] is not None]
            if len(segment_x) == len(segment_values):
                ax.plot(segment_x, segment_values, color=color, linewidth=2, label='Outer', zorder=3)
    
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


class FractalDimensionAdaptivePlot(Base):
    """
    Renders OHLCV data with Fractal Dimension Adaptive (DSSAKAMA) indicators.
    
    Creates a combined chart with:
    - Top panel: Price OHLC bars with VBP and volume
    - Bottom panel: Fractal Dimension Adaptive indicators
    
    Inputs: 'ohlcv_bundle' (Dict[AssetSymbol, List[OHLCVBar]])
    Output: 'images' -> Dict[str, str] mapping label to data URL
    """

    inputs = {
        "ohlcv_bundle": get_type("OHLCVBundle") | None,
    }
    optional_inputs = ["ohlcv_bundle", "ohlcv"]

    outputs = {
        "images": get_type("ConfigDict"),
        "fractal_dimension_adaptive_data": get_type("ConfigDict"),
        "ohlcv_bundle": get_type("OHLCVBundle"),
    }

    CATEGORY = NodeCategory.MARKET
    
    default_params = {
        "lookback_bars": None,
        "max_symbols": 12,
        "show_volume_by_price": True,
        "volume_by_price_bars": 12,
        "volume_by_price_color_volume": False,
        "volume_by_price_opacity": 0.3,
        "period": 10,
        "kama_fastend": 2.0,
        "kama_slowend": 30.0,
        "efratiocalc": "Fractal Dimension Adaptive",
        "jcount": 2,
        "smooth_power": 2,
        "stoch_len": 30,
        "sm_ema": 9,
        "sig_ema": 5,
        "dpi": 250,
    }

    param_definitions = [
        {
            "name": "lookback_bars",
            "displayName": "Lookback Bars",
            "type": "number",
            "default": None,
            "description": "Number of bars to look back (None = all available)",
        },
        {
            "name": "max_symbols",
            "displayName": "Max Symbols",
            "type": "number",
            "default": 12,
            "description": "Maximum number of symbols to process",
        },
        {
            "name": "show_volume_by_price",
            "displayName": "Show Volume by Price",
            "type": "boolean",
            "default": True,
            "description": "Show VBP bars on price chart",
        },
        {
            "name": "volume_by_price_bars",
            "displayName": "VBP Bars",
            "type": "number",
            "default": 12,
            "description": "Number of Volume-by-Price bars",
        },
        {
            "name": "volume_by_price_color_volume",
            "displayName": "VBP Color Volume",
            "type": "boolean",
            "default": False,
            "description": "Color VBP bars by up/down volume",
        },
        {
            "name": "volume_by_price_opacity",
            "displayName": "VBP Opacity",
            "type": "number",
            "default": 0.3,
            "description": "Opacity of VBP bars (0.0 to 1.0)",
        },
        {
            "name": "period",
            "displayName": "Period",
            "type": "number",
            "default": 10,
            "description": "KAMA period",
        },
        {
            "name": "kama_fastend",
            "displayName": "KAMA Fast-end Period",
            "type": "number",
            "default": 2.0,
            "description": "Kaufman AMA fast-end period",
        },
        {
            "name": "kama_slowend",
            "displayName": "KAMA Slow-end Period",
            "type": "number",
            "default": 30.0,
            "description": "Kaufman AMA slow-end period",
        },
        {
            "name": "efratiocalc",
            "displayName": "Efficiency Ratio Type",
            "type": "string",
            "default": "Fractal Dimension Adaptive",
            "description": "Efficiency ratio calculation type",
        },
        {
            "name": "jcount",
            "displayName": "Fractal Dimension Count",
            "type": "number",
            "default": 2,
            "description": "Fractal dimension count",
        },
        {
            "name": "smooth_power",
            "displayName": "Kaufman Power Smooth",
            "type": "number",
            "default": 2,
            "description": "Kaufman power smoothing",
        },
        {
            "name": "stoch_len",
            "displayName": "Stoch Smooth Period",
            "type": "number",
            "default": 30,
            "description": "Stochastic smoothing period",
        },
        {
            "name": "sm_ema",
            "displayName": "Intermediate Smooth Period",
            "type": "number",
            "default": 9,
            "description": "Intermediate EMA smoothing period",
        },
        {
            "name": "sig_ema",
            "displayName": "Signal Smooth Period",
            "type": "number",
            "default": 5,
            "description": "Signal EMA smoothing period",
        },
        {
            "name": "dpi",
            "displayName": "DPI",
            "type": "number",
            "default": 250,
            "description": "Image DPI for rendering quality",
        },
    ]

    async def _execute_impl(self, inputs: dict[str, Any]) -> dict[str, Any]:
        bundle: dict[AssetSymbol, list[OHLCVBar]] | None = inputs.get("ohlcv_bundle")
        single_bundle: dict[AssetSymbol, list[OHLCVBar]] | None = inputs.get("ohlcv")

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
        fractal_dimension_adaptive_data_by_symbol: dict[str, dict[str, Any]] = {}
        ohlcv_bundle_output: dict[AssetSymbol, list[OHLCVBar]] = {}

        max_syms_raw = self.params.get("max_symbols") or 12
        max_syms = 12
        if isinstance(max_syms_raw, (int, float, str)):
            try:
                max_syms = int(max_syms_raw)
            except (ValueError, TypeError):
                max_syms = 12

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
                logger.warning(f"⚠️ FractalDimensionAdaptivePlot: No bars provided for {sym}")
                continue

            norm, volumes = _normalize_bars(bars)
            if not norm:
                continue

            # Apply lookback filter if specified
            if lookback is not None and lookback > 0:
                norm = norm[-lookback:]
                volumes = volumes[-lookback:]

            ohlcv_bundle_output[sym] = bars

            # Extract price data
            timestamps = [x[0] for x in norm]
            opens = [x[1] for x in norm]
            highs = [x[2] for x in norm]
            lows = [x[3] for x in norm]
            closes = [x[4] for x in norm]

            # Calculate Fractal Dimension Adaptive
            fractal_dim_result = calculate_fractal_dimension_adaptive(
                closes=closes,
                highs=highs,
                lows=lows,
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
                    snapshot = await fetch_current_snapshot(str(sym), api_key)
                    if snapshot and "lastTrade" in snapshot and "price" in snapshot["lastTrade"]:
                        fresh_price = float(snapshot["lastTrade"]["price"])
            except Exception as e:
                logger.warning(f"Failed to fetch snapshot for {sym}: {e}")

            # Calculate EMAs
            ema_10_result = calculate_ema(closes, period=10) if len(closes) >= 10 else {"ema": []}
            ema_30_result = calculate_ema(closes, period=30) if len(closes) >= 30 else {"ema": []}
            ema_100_result = calculate_ema(closes, period=100) if len(closes) >= 100 else {"ema": []}
            ema_10 = ema_10_result.get("ema", [])
            ema_30 = ema_30_result.get("ema", [])
            ema_100 = ema_100_result.get("ema", [])

            # Create figure with two subplots
            fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(14, 10), sharex=True, gridspec_kw={'height_ratios': [3, 1]})
            
            # Top panel: Price chart with VBP and volume
            show_vbp = bool(self.params.get("show_volume_by_price", True))
            vbp_bars = int(self.params.get("volume_by_price_bars", 12))
            vbp_color_volume = bool(self.params.get("volume_by_price_color_volume", False))
            vbp_opacity = float(self.params.get("volume_by_price_opacity", 0.3))

            _plot_candles(
                ax1, norm, volumes, ema_10, ema_30, ema_100,
                show_current_price=True, current_price_override=fresh_price,
                show_volume_by_price=show_vbp,
                volume_by_price_bars=vbp_bars,
                volume_by_price_color_volume=vbp_color_volume,
                volume_by_price_opacity=vbp_opacity,
            )
            ax1.set_title(f"{str(sym)} Price Chart", fontsize=12, fontweight='bold', pad=10)
            ax1.set_ylabel("Price", fontsize=10)
            ax1.tick_params(axis='y', labelsize=9, which='major', left=True, labelleft=True)
            ax1.yaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda x, p: f'${x:.4f}' if x < 1 else f'${x:.2f}'))  # type: ignore
            ax1.yaxis.set_ticks_position('left')
            ax1.tick_params(axis='y', direction='out', length=4, width=1)

            # Bottom panel: Fractal Dimension Adaptive
            _plot_fractal_dimension_adaptive(
                ax2, timestamps,
                fractal_dim_result["signal"],
                fractal_dim_result["outer"],
                fractal_dim_result.get("kama"),
            )
            ax2.set_title(f"{str(sym)} DSS of Advanced Kaufman AMA [Loxx]", fontsize=12, fontweight='bold', pad=10)
            ax2.set_ylabel("DSSAKAMA", fontsize=10)
            ax2.tick_params(labelsize=9)

            # Set time x-axis labels
            if len(norm) > 0:
                timestamps_for_labels = [x[0] for x in norm]
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
                            
                            ax2.set_xticks(label_positions)
                            ax2.set_xticklabels(date_labels, fontsize=8, rotation=45, ha='right')
                            ax2.set_xlabel("Time", fontsize=10)
                        else:
                            ax2.set_xlabel("Time", fontsize=10)
                except Exception as e:
                    logger.warning(f"Failed to format time axis for {sym}: {e}")
                    ax2.set_xlabel("Time", fontsize=10)

            # Set Y-axis limits for price chart
            if len(norm) > 0:
                current_price = fresh_price if fresh_price is not None and fresh_price > 0 else norm[-1][4]
                all_prices = [bar[1] for bar in norm] + [bar[2] for bar in norm] + [bar[3] for bar in norm] + [bar[4] for bar in norm]
                if fresh_price is not None and fresh_price > 0:
                    all_prices.append(fresh_price)
                full_min = min(all_prices)
                full_max = max(all_prices)
                range_min = min(full_min, current_price)
                range_max = max(full_max, current_price)
                price_range = range_max - range_min
                if price_range < current_price * 0.01:
                    padding = current_price * 0.20
                elif price_range < current_price * 0.05:
                    padding = current_price * 0.10
                else:
                    padding = price_range * 0.10
                y_min = range_min - padding
                y_max = range_max + padding
                if current_price > y_max * 0.98:
                    y_max = current_price * 1.15
                if current_price < y_min * 1.02:
                    y_min = current_price * 0.85
                y_min = max(y_min, 0.01 * current_price)
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
            "fractal_dimension_adaptive_data": fractal_dimension_adaptive_data_by_symbol,
            "ohlcv_bundle": ohlcv_bundle_output,
        }

