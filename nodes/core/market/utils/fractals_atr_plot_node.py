"""
Fractals ATR Block Plot Node

Creates combined chart with price OHLC bars and Fractals ATR Block indicators.
Based on TradingView PineScript indicator "[JL] Fractals ATR Block" by Jesse.Lau.
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
    _calculate_volume_by_price,
    _encode_fig_to_data_url,
    _normalize_bars,
    _plot_candles,
    _plot_volume_by_price,
)
from services.indicator_calculators.ema_calculator import calculate_ema
from services.indicator_calculators.fractals_atr_calculator import calculate_fractals_atr
from services.polygon_service import fetch_current_snapshot

logger = logging.getLogger(__name__)


def _plot_fractals_atr(
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
) -> None:
    """Plot Fractals ATR indicators on the given axes."""
    if not timestamps:
        return
    
    ax.set_facecolor('#ffffff')
    
    x_indices = list(range(len(timestamps)))
    
    # Plot ATR breaks as labels/annotations
    for i in range(len(timestamps)):
        # ATR Up Break (lime/green)
        if atr_up_breaks[i] is not None:
            ax.annotate(
                f"AB{atr_up_breaks[i]:.2f}",
                xy=(i, lows[i] if i < len(lows) else 0),
                xytext=(0, -15),
                textcoords="offset points",
                fontsize=8,
                color='black',
                bbox=dict(boxstyle="round,pad=0.3", facecolor='lime', edgecolor='black', alpha=0.9),
                ha='center',
                va='top',
                zorder=10,
            )
        
        # ATR Down Break (red)
        if atr_down_breaks[i] is not None:
            ax.annotate(
                f"AB{atr_down_breaks[i]:.2f}",
                xy=(i, highs[i] if i < len(highs) else 0),
                xytext=(0, 15),
                textcoords="offset points",
                fontsize=8,
                color='white',
                bbox=dict(boxstyle="round,pad=0.3", facecolor='red', edgecolor='black', alpha=0.9),
                ha='center',
                va='bottom',
                zorder=10,
            )
        
        # Fractal ROC Up (lime/green)
        if fractal_roc_up[i] is not None:
            ax.annotate(
                f"FR{fractal_roc_up[i]:.2f}",
                xy=(i, lows[i] if i < len(lows) else 0),
                xytext=(0, -30),
                textcoords="offset points",
                fontsize=8,
                color='black',
                bbox=dict(boxstyle="round,pad=0.3", facecolor='lime', edgecolor='black', alpha=0.9),
                ha='center',
                va='top',
                zorder=10,
            )
        
        # Fractal ROC Down (red)
        if fractal_roc_down[i] is not None:
            ax.annotate(
                f"FR{fractal_roc_down[i]:.2f}",
                xy=(i, highs[i] if i < len(highs) else 0),
                xytext=(0, 30),
                textcoords="offset points",
                fontsize=8,
                color='white',
                bbox=dict(boxstyle="round,pad=0.3", facecolor='red', edgecolor='black', alpha=0.9),
                ha='center',
                va='bottom',
                zorder=10,
            )
        
        # Mark fractals with markers
        if up_fractals[i] and i < len(highs):
            ax.plot(i, highs[i], 'v', color='red', markersize=8, zorder=9, alpha=0.8)
        
        if down_fractals[i] and i < len(lows):
            ax.plot(i, lows[i], '^', color='lime', markersize=8, zorder=9, alpha=0.8)
    
    ax.grid(True, alpha=0.7, linestyle='-', linewidth=0.8, color='#c0c0c0', zorder=0)
    ax.set_axisbelow(True)
    for spine in ax.spines.values():
        spine.set_color('#cccccc')
        spine.set_linewidth(0.8)


class FractalsATRPlot(Base):
    """
    Renders OHLCV data with Fractals ATR Block indicators.
    
    Creates a combined chart with:
    - Top panel: Price OHLC bars with VBP and volume
    - Bottom panel: Fractals ATR indicators
    
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
        "atr_period": 325,
        "fractals_periods": 1,
        "roc_break_level": 2.0,
        "atr_break_level": 1.5,
        "show_fractals": True,
        "show_atr_breaks": True,
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
            "name": "atr_period",
            "displayName": "ATR Period",
            "type": "number",
            "default": 325,
            "description": "ATR period for break detection",
        },
        {
            "name": "fractals_periods",
            "displayName": "Fractals Periods",
            "type": "number",
            "default": 1,
            "description": "Fractals periods",
        },
        {
            "name": "roc_break_level",
            "displayName": "ROC Break Level",
            "type": "number",
            "default": 2.0,
            "description": "ROC break level threshold",
        },
        {
            "name": "atr_break_level",
            "displayName": "ATR Break Level",
            "type": "number",
            "default": 1.5,
            "description": "ATR break level threshold",
        },
        {
            "name": "show_fractals",
            "displayName": "Show Fractals",
            "type": "boolean",
            "default": True,
            "description": "Show fractal markers",
        },
        {
            "name": "show_atr_breaks",
            "displayName": "Show ATR Breaks",
            "type": "boolean",
            "default": True,
            "description": "Show ATR break labels",
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
        fractals_atr_data_by_symbol: dict[str, dict[str, Any]] = {}
        ohlcv_bundle_output: dict[AssetSymbol, list[OHLCVBar]] = {}

        max_syms_raw = self.params.get("max_symbols") or 12
        max_syms = 12
        if isinstance(max_syms_raw, (int, float, str)):
            try:
                max_syms = int(max_syms_raw)
            except (ValueError, TypeError):
                max_syms = 12

        atr_period = int(self.params.get("atr_period", 325))
        fractals_periods = int(self.params.get("fractals_periods", 1))
        roc_break_level = float(self.params.get("roc_break_level", 2.0))
        atr_break_level = float(self.params.get("atr_break_level", 1.5))
        show_fractals = bool(self.params.get("show_fractals", True))
        show_atr_breaks = bool(self.params.get("show_atr_breaks", True))

        symbols = list(bundle.keys())[:max_syms]

        for sym in symbols:
            bars = bundle[sym]
            if not bars:
                logger.warning(f"⚠️ FractalsATRPlot: No bars provided for {sym}")
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

            # Calculate Fractals ATR
            fractals_atr_result = calculate_fractals_atr(
                highs=highs,
                lows=lows,
                opens=opens,
                closes=closes,
                atr_period=atr_period,
                fractals_periods=fractals_periods,
                roc_break_level=roc_break_level,
                atr_break_level=atr_break_level,
            )

            fractals_atr_data_by_symbol[str(sym)] = {
                "up_fractals": fractals_atr_result["up_fractals"],
                "down_fractals": fractals_atr_result["down_fractals"],
                "atr_up_breaks": fractals_atr_result["atr_up_breaks"],
                "atr_down_breaks": fractals_atr_result["atr_down_breaks"],
                "fractal_roc_up": fractals_atr_result["fractal_roc_up"],
                "fractal_roc_down": fractals_atr_result["fractal_roc_down"],
                "atr": fractals_atr_result["atr"],
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

            # Bottom panel: Fractals ATR
            _plot_fractals_atr(
                ax2, timestamps,
                fractals_atr_result["up_fractals"] if show_fractals else [False] * len(timestamps),
                fractals_atr_result["down_fractals"] if show_fractals else [False] * len(timestamps),
                fractals_atr_result["atr_up_breaks"] if show_atr_breaks else [None] * len(timestamps),
                fractals_atr_result["atr_down_breaks"] if show_atr_breaks else [None] * len(timestamps),
                fractals_atr_result["fractal_roc_up"] if show_fractals else [None] * len(timestamps),
                fractals_atr_result["fractal_roc_down"] if show_fractals else [None] * len(timestamps),
                highs, lows,
            )
            ax2.set_title(f"{str(sym)} Fractals ATR Block", fontsize=12, fontweight='bold', pad=10)
            ax2.set_ylabel("Fractals ATR", fontsize=10)
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
            "fractals_atr_data": fractals_atr_data_by_symbol,
            "ohlcv_bundle": ohlcv_bundle_output,
        }

