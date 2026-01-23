"""
Hurst Spectral Analysis Oscillator Plot Node

Creates combined chart with price OHLC bars and Hurst bandpass waves.
"""

import base64
import io
import logging
from datetime import datetime
from typing import TYPE_CHECKING, Any, cast

import matplotlib
import matplotlib.ticker

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

matplotlib.use("Agg")
import matplotlib.pyplot as plt

plt.rcParams.update(
    {
        "figure.dpi": 60,
        "savefig.dpi": 60,
        "figure.facecolor": "white",
        "axes.facecolor": "white",
        "lines.antialiased": True,
        "patch.antialiased": True,
        "text.antialiased": True,
        "font.family": "sans-serif",
        "font.sans-serif": ["Arial", "DejaVu Sans", "Liberation Sans", "Helvetica", "sans-serif"],
        "font.size": 10,
        "axes.labelsize": 10,
        "axes.titlesize": 12,
        "xtick.labelsize": 9,
        "ytick.labelsize": 9,
        "legend.fontsize": 8,
        "lines.linewidth": 1.5,
        "axes.grid": True,
        "axes.axisbelow": True,
        "grid.alpha": 0.7,
        "grid.color": "#c0c0c0",
        "grid.linewidth": 0.8,
        "grid.linestyle": "-",
        "axes.edgecolor": "#cccccc",
        "axes.linewidth": 0.8,
        "xtick.color": "#666666",
        "ytick.color": "#666666",
    }
)

if TYPE_CHECKING:
    from matplotlib.axes import Axes
    from matplotlib.figure import Figure


logger = logging.getLogger(__name__)


def _encode_fig_to_data_url(fig: "Figure", dpi: int = 60) -> str:
    """Encode matplotlib figure to base64 data URL."""
    buf = io.BytesIO()
    fig.savefig(
        buf,
        format="png",
        bbox_inches="tight",
        pad_inches=0.1,
        dpi=dpi,
        facecolor="#ffffff",
        edgecolor="none",
        transparent=False,
        metadata={"Software": None},
    )
    plt.close(fig)
    buf.seek(0)
    b64 = base64.b64encode(buf.read()).decode("ascii")
    return f"data:image/png;base64,{b64}"


def _normalize_bars(
    bars: list[OHLCVBar],
) -> tuple[list[tuple[int, float, float, float, float]], list[float]]:
    """Return tuple of (OHLC data, volume data) sorted by ts. Keeps last occurrence for duplicates."""
    timestamp_map: dict[int, tuple[int, float, float, float, float, float]] = {}

    for bar in bars:
        ts = int(bar["timestamp"])
        open_price = float(bar["open"])
        high_price = float(bar["high"])
        low_price = float(bar["low"])
        close_price = float(bar["close"])
        volume = float(bar.get("volume", 0.0))
        timestamp_map[ts] = (ts, open_price, high_price, low_price, close_price, volume)

    normalized = sorted(timestamp_map.values(), key=lambda x: x[0])
    ohlc_data: list[tuple[int, float, float, float, float]] = [
        (ts, o, h, low, c) for ts, o, h, low, c, _v in normalized
    ]
    volume_data = [_v for _, _, _, _, _, _v in normalized]
    return ohlc_data, volume_data


def _plot_candles(
    ax: "Axes",
    series: list[tuple[int, float, float, float, float]],
    volumes: list[float] | None = None,
    ema_10: list[float | None] | None = None,
    ema_30: list[float | None] | None = None,
    ema_100: list[float | None] | None = None,
    show_current_price: bool = True,
    current_price_override: float | None = None,
) -> None:
    """Plot OHLC bars, volume bars, and EMAs."""
    if not series:
        return

    opens = [x[1] for x in series]
    highs = [x[2] for x in series]
    lows = [x[3] for x in series]
    closes = [x[4] for x in series]

    ax.set_facecolor("#ffffff")

    # Plot EMAs
    ema_data = [
        (ema_10, "#1565c0", "EMA 10", 2.0),
        (ema_30, "#ef5350", "EMA 30", 2.0),
        (ema_100, "#4caf50", "EMA 100", 2.5),
    ]
    ema_lines = []

    for ema_values, color, label, linewidth in ema_data:
        if ema_values and len(ema_values) == len(series):
            valid_ema = [(i, v) for i, v in enumerate(ema_values) if v is not None]
            if valid_ema:
                valid_indices = [x[0] for x in valid_ema]
                valid_values = [x[1] for x in valid_ema]
                (line,) = ax.plot(
                    valid_indices,
                    valid_values,
                    color=color,
                    linewidth=linewidth,
                    alpha=1.0,
                    label=label,
                    linestyle="-",
                    zorder=4,
                )
                ema_lines.append(line)

    # Plot volume bars
    if volumes and len(volumes) == len(series):
        all_prices = lows + highs
        price_min = min(all_prices) if all_prices else 0
        price_max = max(all_prices) if all_prices else 1
        price_range = price_max - price_min if price_max > price_min else 1

        max_volume = max(volumes) if volumes else 1
        volume_scale = (price_range * 0.20) / max_volume if max_volume > 0 else 0
        volume_bottom = price_min

        from matplotlib.patches import Rectangle

        for i, volume in enumerate(volumes):
            volume_height = volume * volume_scale
            volume_rect = Rectangle(
                (i - 0.4, volume_bottom),
                0.8,
                volume_height,
                facecolor="#808080",
                edgecolor="#808080",
                alpha=0.4,
                linewidth=0.5,
            )
            ax.add_patch(volume_rect)

    # Plot OHLC bars
    tick_length = 0.15
    for i, (open, close, high, low) in enumerate(zip(opens, closes, highs, lows)):
        color = "black" if close >= open else "#ef5350"
        ax.plot(
            [i, i],
            [low, high],
            color=color,
            linewidth=1.5,
            alpha=1.0,
            solid_capstyle="round",
            solid_joinstyle="round",
            zorder=5,
        )
        ax.plot(
            [i - tick_length, i],
            [open, open],
            color=color,
            linewidth=1.5,
            alpha=1.0,
            solid_capstyle="round",
            solid_joinstyle="round",
            zorder=5,
        )
        ax.plot(
            [i, i + tick_length],
            [close, close],
            color=color,
            linewidth=1.5,
            alpha=1.0,
            solid_capstyle="round",
            solid_joinstyle="round",
            zorder=5,
        )

    ax.set_xlim(-0.5, len(series) + 1.5)

    # Annotate current price
    if show_current_price and len(closes) > 0:
        current_price = current_price_override if current_price_override is not None else closes[-1]
        current_index = len(closes) - 1

        ax.plot(
            [-0.5, len(closes) + 1.5],
            [current_price, current_price],
            color="#ef5350",
            linestyle="--",
            linewidth=2.0,
            alpha=0.9,
            zorder=10,
        )

        ax.annotate(
            f"${current_price:.4f}",
            xy=(current_index, current_price),
            xytext=(8, 12),
            textcoords="offset points",
            bbox=dict(boxstyle="round,pad=0.4", facecolor="yellow", alpha=0.9, linewidth=2.0),
            fontsize=12,
            fontweight="bold",
            color="black",
            ha="left",
            va="bottom",
        )

    ax.grid(True, alpha=0.7, linestyle="-", linewidth=0.8, color="#c0c0c0", zorder=0)
    ax.set_axisbelow(True)
    for spine in ax.spines.values():
        spine.set_color("#cccccc")
        spine.set_linewidth(0.8)

    if ema_lines:
        legend_labels = []
        last_index = len(series) - 1
        for ema_values, color, label, _linewidth in ema_data:
            if ema_values and len(ema_values) == len(series) and ema_values[last_index] is not None:
                ema_value = ema_values[last_index]
                if isinstance(ema_value, int | float):
                    legend_labels.append(f"{label}: ${ema_value:.4f}")
                else:
                    legend_labels.append(label)
            else:
                legend_labels.append(label)

        if len(legend_labels) == len(ema_lines):
            ax.legend(
                handles=ema_lines,
                labels=legend_labels,
                loc="upper left",
                fontsize=8,
                framealpha=0.9,
                fancybox=False,
                shadow=False,
                frameon=True,
            )


def _plot_hurst_waves(
    ax: "Axes",
    timestamps: list[int],
    bandpasses: dict[str, list[float | None]],
    composite: list[float | None],
    selected_periods: list[str] | None = None,
    show_composite: bool = True,
    y_axis_scale: str = "symlog",
) -> None:
    """Plot Hurst bandpass waves."""
    if not timestamps:
        return

    ax.set_facecolor("#ffffff")
    x_indices = list(range(len(timestamps)))

    period_colors = {
        "5_day": "#9c27b0",
        "10_day": "#2196f3",
        "20_day": "#00bcd4",
        "40_day": "#4caf50",
        "80_day": "#ffeb3b",
        "20_week": "#ff9800",
        "40_week": "#f44336",
        "18_month": "#856c44",
        "54_month": "#000000",
        "9_year": "#9e9e9e",
        "18_year": "#ffffff",
    }

    if selected_periods:
        for period_name in selected_periods:
            if period_name in bandpasses:
                values = bandpasses[period_name]
                color = period_colors.get(period_name, "#888888")
                valid_data = [
                    (x_indices[i], cast(float, v)) for i, v in enumerate(values) if v is not None
                ]
                if valid_data:
                    valid_x, valid_values = zip(*valid_data)
                    linewidth = (
                        1.8
                        if period_name in ["5_day", "10_day"]
                        else 1.5
                        if period_name in ["20_day", "40_day", "80_day"]
                        else 1.3
                    )
                    alpha = (
                        0.95
                        if period_name in ["5_day", "10_day"]
                        else 0.9
                        if period_name in ["20_day", "40_day", "80_day"]
                        else 0.85
                    )
                    ax.plot(
                        list(valid_x),
                        list(valid_values),
                        color=color,
                        linewidth=linewidth,
                        alpha=alpha,
                        label=period_name.replace("_", " ").title(),
                    )

    if show_composite and composite:
        valid_data = [
            (x_indices[i], cast(float, v)) for i, v in enumerate(composite) if v is not None
        ]
        if valid_data:
            valid_x, valid_values = zip(*valid_data)
            ax.plot(
                list(valid_x),
                list(valid_values),
                color="#ff6600",
                linewidth=2.0,
                alpha=0.95,
                label="Composite",
                zorder=10,
            )
            valid_indices = [i for i, v in enumerate(composite) if v is not None]
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
                        fontweight="bold",
                        bbox=dict(
                            boxstyle="round,pad=0.3",
                            facecolor="white",
                            edgecolor="#ff6600",
                            alpha=0.95,
                            linewidth=1.5,
                        ),
                        ha="left",
                        va="bottom",
                    )

    if y_axis_scale == "symlog":
        ax.set_yscale("symlog", linthresh=0.01, linscale=0.5)
    elif y_axis_scale == "log":
        ax.set_yscale("log")
    else:
        ax.set_yscale("linear")

    ax.axhline(y=0, color="#888888", linestyle="--", linewidth=0.5, alpha=0.5)
    ax.grid(True, alpha=0.7, linestyle="-", linewidth=0.8, color="#c0c0c0", zorder=0)
    ax.set_axisbelow(True)
    for spine in ax.spines.values():
        spine.set_color("#cccccc")
        spine.set_linewidth(0.8)

    if selected_periods or show_composite:
        ax.legend(
            fontsize=8,
            loc="upper left",
            framealpha=0.9,
            edgecolor="#cccccc",
            fancybox=False,
            shadow=False,
            frameon=True,
            ncol=1,
            columnspacing=0.5,
        )


def _plot_mesa_stochastic(
    ax: "Axes",
    timestamps: list[int],
    mesa_values: dict[str, list[float]],
    trigger_length: int = 2,
) -> None:
    """Plot MESA Stochastic Multi Length indicator."""
    if not timestamps or not mesa_values:
        return

    ax.set_facecolor("#ffffff")
    x_indices = list(range(len(timestamps)))

    mesa_colors = {
        "mesa1": "#2196f3",
        "mesa2": "#4caf50",
        "mesa3": "#ff9800",
        "mesa4": "#f44336",
    }

    for key, values in mesa_values.items():
        if len(values) == len(timestamps):
            color = mesa_colors.get(key, "#888888")
            ax.plot(x_indices, values, color=color, linewidth=1.5, alpha=0.9, label=key.upper())

            if trigger_length > 0 and len(values) >= trigger_length:
                import numpy as np

                trigger = []
                for i in range(len(values)):
                    if i >= trigger_length - 1:
                        trigger.append(np.mean(values[i - trigger_length + 1 : i + 1]))
                    else:
                        trigger.append(values[i])
                ax.plot(
                    x_indices,
                    trigger,
                    color="#2962ff",
                    linewidth=1.3,
                    alpha=0.8,
                    linestyle="--",
                    label=f"{key} Trigger",
                )

    ax.set_ylim(-0.1, 1.1)
    ax.axhline(y=0, color="#888888", linestyle="--", linewidth=0.5, alpha=0.5)
    ax.axhline(y=0.5, color="#888888", linestyle="--", linewidth=0.5, alpha=0.5)
    ax.axhline(y=1, color="#888888", linestyle="--", linewidth=0.5, alpha=0.5)
    ax.grid(True, alpha=0.7, linestyle="-", linewidth=0.8, color="#c0c0c0", zorder=0)
    ax.set_axisbelow(True)
    for spine in ax.spines.values():
        spine.set_color("#cccccc")
        spine.set_linewidth(0.8)
    ax.legend(
        loc="upper left",
        fontsize=8,
        framealpha=0.9,
        fancybox=False,
        shadow=False,
        frameon=True,
        ncol=2,
        columnspacing=0.5,
    )


def _plot_cco(
    ax: "Axes",
    timestamps: list[int],
    fast_osc: list[float | None],
    slow_osc: list[float | None],
) -> None:
    """Plot Cycle Channel Oscillator (CCO)."""
    if not timestamps or not fast_osc or not slow_osc:
        return

    ax.set_facecolor("#ffffff")
    x_indices = list(range(len(timestamps)))

    min_len = min(len(fast_osc), len(slow_osc), len(timestamps))
    fast_osc = fast_osc[:min_len]
    slow_osc = slow_osc[:min_len]
    x_indices = x_indices[:min_len]

    ax.axhline(y=0.0, color="#888888", linestyle="--", linewidth=0.5, alpha=0.5)
    ax.axhline(y=0.5, color="#888888", linestyle="--", linewidth=0.5, alpha=0.5)
    ax.axhline(y=1.0, color="#888888", linestyle="--", linewidth=0.5, alpha=0.5)
    ax.fill_between(x_indices, 0.0, 0.5, color="red", alpha=0.1)
    ax.fill_between(x_indices, 0.5, 1.0, color="green", alpha=0.1)

    for i in range(min_len):
        slow_val = slow_osc[i]
        if slow_val is not None:
            if slow_val >= 1.0:
                ax.bar(i, slow_val - 1.0, bottom=1.0, color="purple", alpha=0.6, width=0.8)
            elif slow_val <= 0.0:
                ax.bar(i, abs(slow_val), bottom=0.0, color="purple", alpha=0.6, width=0.8)

    for i in range(min_len):
        fast_val = fast_osc[i]
        if fast_val is not None:
            if fast_val >= 1.0:
                ax.bar(i, fast_val - 1.0, bottom=1.0, color="purple", alpha=0.4, width=0.6)
            elif fast_val <= 0.0:
                ax.bar(i, abs(fast_val), bottom=0.0, color="purple", alpha=0.4, width=0.6)

    valid_fast_data = [
        (x_indices[i], cast(float, v)) for i, v in enumerate(fast_osc) if v is not None
    ]
    valid_slow_data = [
        (x_indices[i], cast(float, v)) for i, v in enumerate(slow_osc) if v is not None
    ]

    if valid_fast_data:
        valid_fast_x, valid_fast_values = zip(*valid_fast_data)
        ax.plot(
            list(valid_fast_x),
            list(valid_fast_values),
            color="red",
            linewidth=2,
            alpha=0.9,
            label="FastOsc",
        )

    if valid_slow_data:
        valid_slow_x, valid_slow_values = zip(*valid_slow_data)
        ax.plot(
            list(valid_slow_x),
            list(valid_slow_values),
            color="green",
            linewidth=2,
            alpha=0.9,
            label="SlowOsc",
        )

    ax.set_ylim(-0.2, 1.4)
    ax.grid(True, alpha=0.7, linestyle="-", linewidth=0.8, color="#c0c0c0", zorder=0)
    ax.set_axisbelow(True)
    for spine in ax.spines.values():
        spine.set_color("#cccccc")
        spine.set_linewidth(0.8)
    ax.legend(
        loc="upper left",
        fontsize=8,
        framealpha=0.9,
        fancybox=False,
        shadow=False,
        frameon=True,
        ncol=1,
        columnspacing=0.5,
    )


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
        "hurst_data": get_type("ConfigDict"),
        "ohlcv_bundle": get_type("OHLCVBundle"),
        "mesa_data": get_type("ConfigDict"),
        "cco_data": get_type("ConfigDict"),
    }

    CATEGORY = NodeCategory.MARKET

    default_params = {
        "max_symbols": 20,
        "lookback_bars": 100,
        "zoom_to_recent": False,
        "y_axis_scale": "symlog",
        "show_current_price": True,
        "source": "hl2",
        "bandwidth": 0.025,
        "dpi": 60,
        "show_5_day": True,
        "show_10_day": True,
        "show_20_day": True,
        "show_40_day": True,
        "show_80_day": True,
        "show_20_week": False,
        "show_40_week": False,
        "show_18_month": False,
        "show_54_month": False,
        "show_9_year": False,
        "show_18_year": False,
        "show_composite": True,
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
        "show_mesa_stochastic": False,
        "mesa_length1": 50,
        "mesa_length2": 21,
        "mesa_length3": 14,
        "mesa_length4": 9,
        "mesa_trigger_length": 2,
        "show_cco": False,
        "cco_short_cycle_length": 10,
        "cco_medium_cycle_length": 30,
        "cco_short_cycle_multiplier": 1.0,
        "cco_medium_cycle_multiplier": 3.0,
    }

    params_meta = [
        {"name": "max_symbols", "type": "integer", "default": 20, "min": 1, "max": 50, "step": 1},
        {
            "name": "lookback_bars",
            "type": "number",
            "default": None,
            "min": 10,
            "max": 10000,
            "step": 100,
        },
        {"name": "zoom_to_recent", "type": "combo", "default": False, "options": [True, False]},
        {
            "name": "y_axis_scale",
            "type": "combo",
            "default": "symlog",
            "options": ["linear", "symlog", "log"],
        },
        {"name": "show_current_price", "type": "combo", "default": True, "options": [True, False]},
        {"name": "dpi", "type": "number", "default": 60, "min": 50, "max": 300, "step": 10},
        {
            "name": "source",
            "type": "combo",
            "default": "hl2",
            "options": ["close", "hl2", "open", "high", "low"],
        },
        {
            "name": "bandwidth",
            "type": "number",
            "default": 0.025,
            "min": 0.001,
            "max": 1.0,
            "step": 0.001,
        },
        {"name": "show_5_day", "type": "combo", "default": True, "options": [True, False]},
        {"name": "show_10_day", "type": "combo", "default": True, "options": [True, False]},
        {"name": "show_20_day", "type": "combo", "default": True, "options": [True, False]},
        {"name": "show_40_day", "type": "combo", "default": True, "options": [True, False]},
        {"name": "show_80_day", "type": "combo", "default": True, "options": [True, False]},
        {"name": "show_20_week", "type": "combo", "default": False, "options": [True, False]},
        {"name": "show_40_week", "type": "combo", "default": False, "options": [True, False]},
        {"name": "show_18_month", "type": "combo", "default": False, "options": [True, False]},
        {"name": "show_54_month", "type": "combo", "default": False, "options": [True, False]},
        {"name": "show_9_year", "type": "combo", "default": False, "options": [True, False]},
        {"name": "show_18_year", "type": "combo", "default": False, "options": [True, False]},
        {"name": "show_composite", "type": "combo", "default": True, "options": [True, False]},
        {"name": "composite_5_day", "type": "boolean", "default": True},
        {"name": "composite_10_day", "type": "boolean", "default": True},
        {"name": "composite_20_day", "type": "boolean", "default": True},
        {"name": "composite_40_day", "type": "boolean", "default": True},
        {"name": "composite_80_day", "type": "boolean", "default": True},
        {"name": "composite_20_week", "type": "boolean", "default": True},
        {"name": "composite_40_week", "type": "boolean", "default": True},
        {"name": "composite_18_month", "type": "boolean", "default": True},
        {"name": "composite_54_month", "type": "boolean", "default": True},
        {"name": "composite_9_year", "type": "boolean", "default": True},
        {"name": "composite_18_year", "type": "boolean", "default": True},
        {"name": "period_5_day", "type": "number", "default": 4.3, "min": 2.0, "step": 0.1},
        {"name": "period_10_day", "type": "number", "default": 8.5, "min": 2.0, "step": 0.1},
        {"name": "period_20_day", "type": "number", "default": 17.0, "min": 2.0, "step": 0.1},
        {"name": "period_40_day", "type": "number", "default": 34.1, "min": 2.0, "step": 0.1},
        {"name": "period_80_day", "type": "number", "default": 68.2, "min": 2.0, "step": 0.1},
        {"name": "period_20_week", "type": "number", "default": 136.4, "min": 2.0, "step": 0.1},
        {"name": "period_40_week", "type": "number", "default": 272.8, "min": 2.0, "step": 0.1},
        {"name": "period_18_month", "type": "number", "default": 545.6, "min": 2.0, "step": 0.1},
        {"name": "period_54_month", "type": "number", "default": 1636.8, "min": 2.0, "step": 0.1},
        {"name": "period_9_year", "type": "number", "default": 3273.6, "min": 2.0, "step": 0.1},
        {"name": "period_18_year", "type": "number", "default": 6547.2, "min": 2.0, "step": 0.1},
        {
            "name": "show_mesa_stochastic",
            "type": "combo",
            "default": False,
            "options": [True, False],
        },
        {"name": "mesa_length1", "type": "number", "default": 50, "min": 2, "max": 200, "step": 1},
        {"name": "mesa_length2", "type": "number", "default": 21, "min": 2, "max": 200, "step": 1},
        {"name": "mesa_length3", "type": "number", "default": 14, "min": 2, "max": 200, "step": 1},
        {"name": "mesa_length4", "type": "number", "default": 9, "min": 2, "max": 200, "step": 1},
        {
            "name": "mesa_trigger_length",
            "type": "number",
            "default": 2,
            "min": 1,
            "max": 20,
            "step": 1,
        },
        {"name": "show_cco", "type": "combo", "default": False, "options": [True, False]},
        {
            "name": "cco_short_cycle_length",
            "type": "integer",
            "default": 10,
            "min": 2,
            "max": 100,
            "step": 1,
        },
        {
            "name": "cco_medium_cycle_length",
            "type": "integer",
            "default": 30,
            "min": 2,
            "max": 200,
            "step": 1,
        },
        {
            "name": "cco_short_cycle_multiplier",
            "type": "number",
            "default": 1.0,
            "min": 0.1,
            "max": 10.0,
            "step": 0.1,
        },
        {
            "name": "cco_medium_cycle_multiplier",
            "type": "number",
            "default": 3.0,
            "min": 0.1,
            "max": 10.0,
            "step": 0.1,
        },
    ]

    def _parse_params(self) -> dict[str, Any]:
        """Parse and validate parameters, returning a dictionary of validated values."""
        lookback_raw = self.params.get("lookback_bars")
        lookback: int | None = None
        if lookback_raw is not None:
            if isinstance(lookback_raw, int | float | str):
                try:
                    lookback_val = int(lookback_raw)
                    lookback = lookback_val if lookback_val > 0 else None
                except (ValueError, TypeError):
                    lookback = None

        max_syms_raw = self.params.get("max_symbols", 20)
        max_syms = 20
        if isinstance(max_syms_raw, int | float | str):
            try:
                max_syms = int(max_syms_raw)
            except (ValueError, TypeError):
                max_syms = 20

        source = str(self.params.get("source", "hl2"))

        bandwidth_raw = self.params.get("bandwidth", 0.025)
        bandwidth = 0.025
        if isinstance(bandwidth_raw, int | float | str):
            try:
                bandwidth = float(bandwidth_raw)
            except (ValueError, TypeError):
                bandwidth = 0.025

        periods = {}
        period_defaults = {
            "5_day": 4.3,
            "10_day": 8.5,
            "20_day": 17.0,
            "40_day": 34.1,
            "80_day": 68.2,
            "20_week": 136.4,
            "40_week": 272.8,
            "18_month": 545.6,
            "54_month": 1636.8,
            "9_year": 3273.6,
            "18_year": 6547.2,
        }
        for key, default in period_defaults.items():
            raw = self.params.get(f"period_{key}", default)
            if isinstance(raw, int | float | str):
                try:
                    periods[key] = float(raw)
                except (ValueError, TypeError):
                    periods[key] = default
            else:
                periods[key] = default

        composite_selection = {}
        for k in periods.keys():
            raw = self.params.get(f"composite_{k}", True)
            composite_selection[k] = bool(raw) if raw is not None else True

        show_periods = [
            k
            for k in [
                "5_day",
                "10_day",
                "20_day",
                "40_day",
                "80_day",
                "20_week",
                "40_week",
                "18_month",
                "54_month",
                "9_year",
                "18_year",
            ]
            if bool(
                self.params.get(f"show_{k}", k in ["5_day", "10_day", "20_day", "40_day", "80_day"])
            )
        ]

        show_composite = bool(self.params.get("show_composite", True))
        show_mesa = bool(self.params.get("show_mesa_stochastic", False))
        show_cco = bool(self.params.get("show_cco", False))
        zoom_to_recent = bool(self.params.get("zoom_to_recent", False))
        y_axis_scale = str(self.params.get("y_axis_scale", "symlog"))
        show_current_price = bool(self.params.get("show_current_price", True))

        dpi_raw = self.params.get("dpi", 60)
        dpi = 60
        if isinstance(dpi_raw, int | float | str):
            try:
                dpi = int(dpi_raw)
            except (ValueError, TypeError):
                dpi = 60

        mesa_params = {}
        if show_mesa:
            mesa_params["length1"] = (
                int(self.params.get("mesa_length1", 50))
                if isinstance(self.params.get("mesa_length1", 50), int | float)
                else 50
            )
            mesa_params["length2"] = (
                int(self.params.get("mesa_length2", 21))
                if isinstance(self.params.get("mesa_length2", 21), int | float)
                else 21
            )
            mesa_params["length3"] = (
                int(self.params.get("mesa_length3", 14))
                if isinstance(self.params.get("mesa_length3", 14), int | float)
                else 14
            )
            mesa_params["length4"] = (
                int(self.params.get("mesa_length4", 9))
                if isinstance(self.params.get("mesa_length4", 9), int | float)
                else 9
            )
            mesa_params["trigger_length"] = (
                int(self.params.get("mesa_trigger_length", 2))
                if isinstance(self.params.get("mesa_trigger_length", 2), int | float)
                else 2
            )

        cco_params = {}
        if show_cco:
            cco_params["short_cycle_length"] = (
                int(self.params.get("cco_short_cycle_length", 10))
                if isinstance(self.params.get("cco_short_cycle_length", 10), int | float)
                else 10
            )
            cco_params["medium_cycle_length"] = (
                int(self.params.get("cco_medium_cycle_length", 30))
                if isinstance(self.params.get("cco_medium_cycle_length", 30), int | float)
                else 30
            )
            cco_params["short_cycle_multiplier"] = (
                float(self.params.get("cco_short_cycle_multiplier", 1.0))
                if isinstance(self.params.get("cco_short_cycle_multiplier", 1.0), int | float)
                else 1.0
            )
            cco_params["medium_cycle_multiplier"] = (
                float(self.params.get("cco_medium_cycle_multiplier", 3.0))
                if isinstance(self.params.get("cco_medium_cycle_multiplier", 3.0), int | float)
                else 3.0
            )

        return {
            "lookback": lookback,
            "max_syms": max_syms,
            "source": source,
            "bandwidth": bandwidth,
            "periods": periods,
            "composite_selection": composite_selection,
            "show_periods": show_periods,
            "show_composite": show_composite,
            "show_mesa": show_mesa,
            "show_cco": show_cco,
            "zoom_to_recent": zoom_to_recent,
            "y_axis_scale": y_axis_scale,
            "show_current_price": show_current_price,
            "dpi": dpi,
            "mesa_params": mesa_params,
            "cco_params": cco_params,
        }

    def _determine_display_range(
        self,
        norm: list[tuple[int, float, float, float, float]],
        lookback: int | None,
        zoom_to_recent: bool,
    ) -> list[tuple[int, float, float, float, float]]:
        """Determine the display range based on lookback and zoom settings."""
        if zoom_to_recent and len(norm) > 300:
            return norm[-300:]
        elif lookback and len(norm) > lookback:
            return norm[-lookback:]
        else:
            return norm[-2000:] if len(norm) > 2000 else norm

    def _calculate_emas(
        self, closes: list[float]
    ) -> tuple[list[float | None], list[float | None], list[float | None]]:
        """Calculate EMA indicators."""
        ema_10_result = calculate_ema(closes, period=10) if len(closes) >= 10 else {"ema": []}
        ema_30_result = calculate_ema(closes, period=30) if len(closes) >= 30 else {"ema": []}
        ema_100_result = calculate_ema(closes, period=100) if len(closes) >= 100 else {"ema": []}
        return (
            ema_10_result.get("ema", []),
            ema_30_result.get("ema", []),
            ema_100_result.get("ema", []),
        )

    def _create_figure(
        self, show_mesa: bool, show_cco: bool
    ) -> tuple["Figure", "Axes", "Axes", "Axes | None", "Axes | None"]:
        """Create matplotlib figure with appropriate number of subplots."""
        num_subplots = 2 + (1 if show_mesa else 0) + (1 if show_cco else 0)

        if num_subplots == 2:
            fig, (ax1, ax2) = plt.subplots(
                2, 1, figsize=(8, 6), sharex=True, height_ratios=[2.25, 1.0]
            )
            fig.subplots_adjust(hspace=0.20, top=0.88, bottom=0.07, left=0.08, right=0.95)
            return fig, ax1, ax2, None, None
        elif num_subplots == 3:
            if show_mesa:
                fig, (ax1, ax2, ax3) = plt.subplots(
                    3, 1, figsize=(8, 8), sharex=True, height_ratios=[2.25, 1.0, 1.0]
                )
                fig.subplots_adjust(hspace=0.18, top=0.88, bottom=0.07, left=0.08, right=0.95)
                return fig, ax1, ax2, ax3, None
            else:
                fig, (ax1, ax2, ax4) = plt.subplots(
                    3, 1, figsize=(8, 8), sharex=True, height_ratios=[2.25, 1.0, 1.0]
                )
                fig.subplots_adjust(hspace=0.18, top=0.88, bottom=0.07, left=0.08, right=0.95)
                return fig, ax1, ax2, None, ax4
        else:
            fig, (ax1, ax2, ax3, ax4) = plt.subplots(
                4, 1, figsize=(8, 10), sharex=True, height_ratios=[2.25, 1.0, 1.0, 1.0]
            )
            fig.subplots_adjust(hspace=0.15, top=0.88, bottom=0.07, left=0.08, right=0.95)
            return fig, ax1, ax2, ax3, ax4

    def _format_time_axis(self, ax: "Axes", timestamps: list[int]) -> None:
        """Format the time axis with appropriate date labels."""
        if not timestamps:
            return
        try:
            dates = [datetime.fromtimestamp(ts / 1000) for ts in timestamps]
            if len(dates) > 1:
                num_labels = min(8, len(dates))
                step = max(1, len(dates) // num_labels)
                label_indices = list(range(0, len(dates), step))
                if len(dates) - 1 not in label_indices:
                    label_indices.append(len(dates) - 1)

                label_dates = [dates[i] for i in label_indices]
                time_span = (dates[-1] - dates[0]).total_seconds()
                if time_span < 86400 * 2:
                    date_labels = [d.strftime("%H:%M") for d in label_dates]
                elif time_span < 86400 * 30:
                    date_labels = [d.strftime("%d/%m") for d in label_dates]
                else:
                    date_labels = [d.strftime("%b %Y") for d in label_dates]

                ax.set_xticks(label_indices)
                ax.set_xticklabels(date_labels, fontsize=8, rotation=45, ha="right")
        except Exception:
            pass
        ax.set_xlabel("Time", fontsize=10)

    async def _execute_impl(self, inputs: dict[str, Any]) -> dict[str, Any]:
        bundle: dict[AssetSymbol, list[OHLCVBar]] | None = inputs.get("ohlcv_bundle")
        single_bundle: dict[AssetSymbol, list[OHLCVBar]] | None = inputs.get("ohlcv")

        if bundle and single_bundle:
            bundle = {**bundle, **single_bundle}
        elif single_bundle:
            bundle = single_bundle

        if not bundle:
            raise NodeValidationError(self.id, "Provide either 'ohlcv_bundle' or 'ohlcv'")

        params = self._parse_params()

        images: dict[str, str] = {}
        hurst_data_by_symbol: dict[str, dict[str, Any]] = {}
        ohlcv_bundle_output: dict[AssetSymbol, list[OHLCVBar]] = {}
        mesa_data_by_symbol: dict[str, dict[str, Any]] = {}
        cco_data_by_symbol: dict[str, dict[str, Any]] = {}

        items = list(bundle.items())[: params["max_syms"]]
        for sym, bars in items:
            if not bars or len(bars) < 10:
                continue

            norm, volumes = _normalize_bars(bars)

            # Determine display range
            full_norm = norm
            display_norm = self._determine_display_range(
                norm, params["lookback"], params["zoom_to_recent"]
            )
            norm = display_norm

            if len(norm) < 10:
                continue

            # Extract price data
            full_closes = [x[4] for x in full_norm]
            full_highs = [x[2] for x in full_norm]
            full_lows = [x[3] for x in full_norm]

            timestamps = [x[0] for x in norm]
            closes = [x[4] for x in norm]

            # Calculate Hurst oscillator
            try:
                full_hurst_result = calculate_hurst_oscillator(
                    closes=full_closes,
                    highs=full_highs,
                    lows=full_lows,
                    source=params["source"],
                    bandwidth=params["bandwidth"],
                    periods=params["periods"],
                    composite_selection=params["composite_selection"],
                )

                hurst_data_by_symbol[str(sym)] = {
                    "bandpasses": full_hurst_result.get("bandpasses", {}),
                    "composite": full_hurst_result.get("composite", []),
                    "peaks": full_hurst_result.get("peaks", []),
                    "troughs": full_hurst_result.get("troughs", []),
                    "wavelength": full_hurst_result.get("wavelength"),
                    "amplitude": full_hurst_result.get("amplitude"),
                    "timestamps": [x[0] for x in full_norm],
                }

                ohlcv_bundle_output[sym] = bars

                start_idx = max(0, len(full_norm) - len(norm))
                hurst_result = {
                    "bandpasses": {
                        k: v[start_idx:] for k, v in full_hurst_result.get("bandpasses", {}).items()
                    },
                    "composite": full_hurst_result.get("composite", [])[start_idx:],
                }
            except Exception as e:
                logger.error(f"Error calculating Hurst for {sym}: {e}", exc_info=True)
                continue

            bandpasses = hurst_result.get("bandpasses", {})
            composite = hurst_result.get("composite", [])

            # Calculate EMAs
            display_volumes = volumes[-len(norm) :] if len(volumes) >= len(norm) else volumes
            display_ema_10, display_ema_30, display_ema_100 = self._calculate_emas(closes)

            # Fetch fresh price
            fresh_price: float | None = None
            if params["show_current_price"] and len(norm) > 0:
                try:
                    api_key = APIKeyVault().get("POLYGON_API_KEY")
                    if api_key:
                        fresh_price, _ = await fetch_current_snapshot(sym, api_key)
                except Exception:
                    pass

            # Create figure
            fig, ax1, ax2, ax3, ax4 = self._create_figure(params["show_mesa"], params["show_cco"])

            # Plot price chart
            _plot_candles(
                ax1,
                norm,
                display_volumes,
                display_ema_10,
                display_ema_30,
                display_ema_100,
                params["show_current_price"],
                fresh_price,
            )
            ax1.set_title(f"{str(sym)} Price Chart", fontsize=12, fontweight="bold", pad=10)
            ax1.set_ylabel("Price", fontsize=10)
            ax1.tick_params(axis="y", labelsize=9)
            ax1.yaxis.set_major_formatter(
                matplotlib.ticker.FuncFormatter(lambda x, p: f"${x:.4f}" if x < 1 else f"${x:.2f}")
            )

            try:
                ax1.set_yscale(params["y_axis_scale"])
            except Exception:
                ax1.set_yscale("linear")

            if len(norm) > 0:
                all_prices = (
                    [bar[1] for bar in norm]
                    + [bar[2] for bar in norm]
                    + [bar[3] for bar in norm]
                    + [bar[4] for bar in norm]
                )
                if fresh_price:
                    all_prices.append(fresh_price)
                price_min = min(all_prices)
                price_max = max(all_prices)
                padding = (price_max - price_min) * 0.05
                ax1.set_ylim(max(price_min - padding, 0.01 * price_min), price_max + padding)

            # Plot Hurst waves
            _plot_hurst_waves(
                ax2,
                timestamps,
                bandpasses,
                composite,
                params["show_periods"],
                params["show_composite"],
                params["y_axis_scale"],
            )
            ax2.set_title(
                f"{str(sym)} Hurst Spectral Analysis Oscillator",
                fontsize=12,
                fontweight="bold",
                pad=10,
            )
            ax2.set_ylabel("Hurst Oscillator", fontsize=10)
            ax2.tick_params(labelsize=9)

            # Set time axis labels
            bottom_ax = ax4 if ax4 else (ax3 if ax3 else ax2)
            self._format_time_axis(bottom_ax, timestamps)

            # Auto-scale Hurst Y-axis
            all_wave_values: list[float] = []
            if params["show_composite"] and composite:
                all_wave_values.extend([v for v in composite if v is not None])
            if params["show_periods"]:
                for period_name in params["show_periods"]:
                    if period_name in bandpasses:
                        all_wave_values.extend(
                            [v for v in bandpasses[period_name] if v is not None]
                        )

            if all_wave_values:
                min_val = min(all_wave_values)
                max_val = max(all_wave_values)
                padding = (max_val - min_val) * 0.1 if max_val != min_val else 1.0
                ax2.set_ylim(min_val - padding, max_val + padding)

            # MESA Stochastic
            if params["show_mesa"] and ax3 is not None:
                try:
                    mesa_params_dict = params["mesa_params"]
                    full_hl2 = [(high + low) / 2.0 for high, low in zip(full_highs, full_lows)]
                    mesa_result = calculate_mesa_stochastic_multi_length(
                        prices=full_hl2,
                        length1=mesa_params_dict["length1"],
                        length2=mesa_params_dict["length2"],
                        length3=mesa_params_dict["length3"],
                        length4=mesa_params_dict["length4"],
                    )

                    mesa_data_by_symbol[str(sym)] = {
                        "mesa1": mesa_result["mesa1"],
                        "mesa2": mesa_result["mesa2"],
                        "mesa3": mesa_result["mesa3"],
                        "mesa4": mesa_result["mesa4"],
                        "timestamps": [x[0] for x in full_norm],
                    }

                    display_mesa = {
                        k: v[start_idx:] for k, v in mesa_result.items() if k.startswith("mesa")
                    }
                    _plot_mesa_stochastic(
                        ax3, timestamps, display_mesa, mesa_params_dict["trigger_length"]
                    )
                    ax3.set_title(
                        f"{str(sym)} MESA Stochastic Multi Length",
                        fontsize=12,
                        fontweight="bold",
                        pad=10,
                    )
                    ax3.set_ylabel("MESA Stochastic", fontsize=10)
                    ax3.tick_params(labelsize=9)
                except Exception as e:
                    logger.error(f"Error calculating MESA Stochastic for {sym}: {e}", exc_info=True)

            # CCO
            if params["show_cco"]:
                cco_ax = ax4 if params["show_mesa"] else ax3
                if cco_ax is not None:
                    try:
                        cco_params_dict = params["cco_params"]
                        cco_result = calculate_cco(
                            closes=full_closes,
                            highs=full_highs,
                            lows=full_lows,
                            short_cycle_length=cco_params_dict["short_cycle_length"],
                            medium_cycle_length=cco_params_dict["medium_cycle_length"],
                            short_cycle_multiplier=cco_params_dict["short_cycle_multiplier"],
                            medium_cycle_multiplier=cco_params_dict["medium_cycle_multiplier"],
                        )

                        cco_data_by_symbol[str(sym)] = {
                            "fast_osc": cco_result["fast_osc"],
                            "slow_osc": cco_result["slow_osc"],
                            "timestamps": [x[0] for x in full_norm],
                        }

                        display_fast_osc = cco_result["fast_osc"][start_idx:]
                        display_slow_osc = cco_result["slow_osc"][start_idx:]
                        _plot_cco(cco_ax, timestamps, display_fast_osc, display_slow_osc)
                        cco_ax.set_title(
                            f"{str(sym)} Cycle Channel Oscillator (CCO)",
                            fontsize=12,
                            fontweight="bold",
                            pad=10,
                        )
                        cco_ax.set_ylabel("CCO", fontsize=10)
                        cco_ax.tick_params(labelsize=9)
                    except Exception as e:
                        logger.error(f"Error calculating CCO for {sym}: {e}", exc_info=True)

            images[str(sym)] = _encode_fig_to_data_url(fig, dpi=params["dpi"])

        return {
            "images": images,
            "hurst_data": hurst_data_by_symbol,
            "ohlcv_bundle": ohlcv_bundle_output,
            "mesa_data": mesa_data_by_symbol,
            "cco_data": cco_data_by_symbol,
        }
