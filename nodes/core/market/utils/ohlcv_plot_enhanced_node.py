import base64
import io
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any

import matplotlib

matplotlib.use("Agg")  # non-interactive backend for server-side rendering
import matplotlib.pyplot as plt

if TYPE_CHECKING:
    from matplotlib.axes import Axes
    from matplotlib.figure import Figure
    from matplotlib.patches import Rectangle
else:
    from matplotlib.axes import Axes
    from matplotlib.figure import Figure
    from matplotlib.patches import Rectangle

from core.api_key_vault import APIKeyVault
from core.types_registry import AssetSymbol, NodeCategory, NodeValidationError, OHLCVBar, get_type
from nodes.base.base_node import Base
from services.indicator_calculators.ema_calculator import calculate_ema
from services.indicator_calculators.sma_calculator import calculate_sma
from services.indicator_calculators.vbp_calculator import calculate_vbp
from services.polygon_service import fetch_bars

# Constants
MIN_BARS_REQUIRED = 10
DAYS_PER_YEAR = 365.25
PRICE_ROUNDING_PRECISION = 2


def _encode_fig_to_data_url(fig: "Figure") -> str:
    buf = io.BytesIO()
    fig.savefig(buf, format="png", bbox_inches="tight", dpi=150)  # pyright: ignore
    plt.close(fig)
    buf.seek(0)
    b64 = base64.b64encode(buf.read()).decode("ascii")
    return f"data:image/png;base64,{b64}"


def _normalize_bars(bars: list[OHLCVBar]) -> list[tuple[int, float, float, float, float]]:
    # Return list of tuples (ts, open, high, low, close) sorted by ts
    cleaned: list[tuple[int, float, float, float, float]] = []
    for b in bars or []:
        try:
            timestamp_raw = b.get("timestamp") or b.get("t") or 0
            open_raw = b.get("open") or b.get("o")
            high_raw = b.get("high") or b.get("h")
            low_raw = b.get("low") or b.get("l")
            close_raw = b.get("close") or b.get("c")

            # Type guards: ensure values are not None before conversion
            if open_raw is None or high_raw is None or low_raw is None or close_raw is None:
                continue

            ts = int(timestamp_raw)
            o = float(open_raw)
            h = float(high_raw)
            low_price = float(low_raw)
            c = float(close_raw)
        except (ValueError, TypeError):
            continue
        cleaned.append((ts, o, h, low_price, c))
    cleaned.sort(key=lambda x: x[0])
    return cleaned


def _find_significant_levels(histogram: list[dict[str, Any]], num_levels: int) -> list[dict[str, Any]]:
    """Find the most significant volume levels from histogram."""
    if not histogram:
        return []

    def volume_key(x: dict[str, Any]) -> float:
        vol = x.get("volume", 0.0)
        return float(vol) if isinstance(vol, int | float) else 0.0

    sorted_bins = sorted(histogram, key=volume_key, reverse=True)
    return sorted_bins[:num_levels]


async def _fetch_weekly_bars_for_vbp(
    symbol: AssetSymbol, api_key: str, lookback_years: int
) -> list[OHLCVBar]:
    """Fetch weekly bars directly from Polygon API for VBP calculation."""
    lookback_days = lookback_years * 365

    fetch_params = {
        "multiplier": 1,
        "timespan": "week",
        "lookback_period": f"{lookback_days} days",
        "adjusted": True,
        "sort": "asc",
        "limit": 50000,
    }

    bars, _metadata = await fetch_bars(symbol, api_key, fetch_params)
    return bars


def _calculate_vbp_levels_from_weekly(
    weekly_bars: list[OHLCVBar],
    bins: int,
    num_levels: int,
    use_dollar_weighted: bool = False,
    use_close_only: bool = False,
) -> list[float]:
    """Calculate VBP levels from weekly bars."""
    if not weekly_bars or len(weekly_bars) < MIN_BARS_REQUIRED:
        return []

    vbp_result = calculate_vbp(weekly_bars, bins, use_dollar_weighted, use_close_only)

    if vbp_result.get("pointOfControl") is None:
        return []

    # Find significant levels
    significant_levels = _find_significant_levels(vbp_result["histogram"], num_levels)

    # Extract price levels
    vbp_levels: list[float] = []
    for level in significant_levels:
        price_level = level.get("priceLevel", 0.0)
        if isinstance(price_level, (int, float)) and price_level > 0:
            vbp_levels.append(float(price_level))

    return vbp_levels


def _calculate_overlay(ohlcv_data: list[OHLCVBar], period: int, ma_type: str) -> list[float | None]:
    """Calculate SMA or EMA overlay from OHLCV data."""
    if not ohlcv_data or period <= 1:
        return []

    close_prices = [bar["close"] for bar in ohlcv_data]
    if ma_type == "SMA":
        result = calculate_sma(close_prices, period=period)
        return result.get("sma", [])
    elif ma_type == "EMA":
        result = calculate_ema(close_prices, period=period)
        return result.get("ema", [])
    else:
        return []


def _plot_candles(
    ax: "Axes",
    series: list[tuple[int, float, float, float, float]],
    overlays: list[tuple[list[float | None], str, str]] | None = None,
    vbp_levels: list[float] | None = None,
    vbp_color: str = "#FF6B35",
    vbp_style: str = "dashed",
) -> None:
    """Plot candlesticks with optional overlay lines and VBP levels."""

    if not series:
        ax.set_axis_off()
        return

    for i, (_ts, o, h, low_price, c) in enumerate(series):
        color = "#26a69a" if c >= o else "#ef5350"  # teal for up, red for down
        # wick
        ax.vlines(i, low_price, h, colors=color, linewidth=1)  # pyright: ignore
        # body
        height = max(abs(c - o), 1e-9)
        bottom = min(o, c)
        ax.add_patch(Rectangle((i - 0.3, bottom), 0.6, height, color=color, alpha=0.9))

    # Plot overlay lines (SMA/EMA)
    if overlays:
        for overlay_values, overlay_label, overlay_color in overlays:
            if overlay_values and len(overlay_values) == len(series):
                # Filter out None values for plotting
                valid_indices: list[int] = []
                valid_values: list[float] = []

                for i, val in enumerate(overlay_values):
                    if val is not None:
                        valid_indices.append(i)
                        valid_values.append(val)

                if valid_indices and valid_values:
                    ax.plot(  # pyright: ignore
                        valid_indices,
                        valid_values,
                        color=overlay_color,
                        linewidth=1.5,
                        label=overlay_label,
                        alpha=0.8,
                    )

    ax.set_xlim(-1, len(series))
    # Nice y padding - consider overlay values too
    lows = [low for (_ts, _o, _h, low, _c) in series]
    highs = [h for (_ts, _o, h, _l, _c) in series]

    # Include overlay values in y-axis range calculation
    if overlays:
        for overlay_values, _, _ in overlays:
            if overlay_values:
                valid_values = [v for v in overlay_values if v is not None]
                if valid_values:
                    lows.extend(valid_values)
                    highs.extend(valid_values)

    # Calculate y-axis limits
    y_min = min(lows) if lows else 0
    y_max = max(highs) if highs else 1
    pad = (y_max - y_min) * 0.05 or 1.0
    y_min_with_pad = y_min - pad
    y_max_with_pad = y_max + pad

    if lows and highs:
        ax.set_ylim(y_min_with_pad, y_max_with_pad)

    # Plot VBP levels as horizontal lines (only if within visible range)
    if vbp_levels and len(vbp_levels) > 0:
        # Convert linestyle string to matplotlib format
        linestyle_map = {"solid": "-", "dashed": "--", "dotted": ":"}
        linestyle = linestyle_map.get(vbp_style, "--")

        for level in vbp_levels:
            # Only plot if level is within the visible Y-axis range
            if y_min_with_pad <= level <= y_max_with_pad:
                ax.axhline(  # pyright: ignore
                    y=level, color=vbp_color, linestyle=linestyle, linewidth=1.5, alpha=0.7
                )
                # Add subtle label for each VBP level
                ax.text(  # pyright: ignore
                    len(series) - 1,
                    level,
                    f"{level:.2f}",
                    fontsize=6,
                    verticalalignment="center",
                    horizontalalignment="left",
                    bbox=dict(boxstyle="round,pad=0.1", facecolor="white", alpha=0.8),
                )

    # Show legend if overlays present
    if overlays and any(ov[0] for ov in overlays):
        ax.legend(loc="upper left", fontsize=7, framealpha=0.7)  # pyright: ignore

    # Add equal-spaced month labels on X-axis (timezone-aware)
    if len(series) >= 10:  # Only show labels if enough data points
        timestamps_ms: list[int] = [bar[0] for bar in series]
        # First convert to UTC
        utc_dates: list[datetime] = [
            datetime.fromtimestamp(ts / 1000, tz=timezone.utc) for ts in timestamps_ms
        ]

        # Convert to local timezone (user's system timezone)
        try:
            import zoneinfo

            local_tz = zoneinfo.ZoneInfo(matplotlib.rcParams.get("timezone", "UTC"))
        except Exception:
            # Fallback if rcParams not set or zoneinfo unavailable
            local_tz = None

        local_dates: list[datetime] = [
            d.astimezone(local_tz) if local_tz else d.replace(tzinfo=None) for d in utc_dates
        ]

        # Find month boundaries (first bar of each month in LOCAL timezone)
        month_changes: list[int] = [0]  # Start with first bar
        prev_ym: tuple[int, int] | None = None
        for i, d in enumerate(local_dates):
            cur_ym: tuple[int, int] = (d.year, d.month)
            if prev_ym is not None and cur_ym != prev_ym:
                month_changes.append(i)  # First bar of new month
            prev_ym = cur_ym

        month_changes.append(len(series))  # One-past-the-end

        # Draw vertical month separators at exact bar boundaries
        for idx in month_changes[1:-1]:  # Skip first and last
            ax.axvline(
                x=idx - 0.5, color="gray", linestyle="--", linewidth=0.7, alpha=0.5
            )  # pyright: ignore

        # Place label in the exact center of each month block (skip partial months)
        if len(month_changes) >= 3:  # At least two full months
            positions: list[float] = []
            labels: list[str] = []

            for i in range(len(month_changes) - 1):
                start = month_changes[i]
                end = month_changes[i + 1]
                num_bars = end - start

                # Skip months with fewer than 10 bars (partial months like Jun with only 3 bars)
                if num_bars < 10:
                    continue

                # Center index (float for precise positioning)
                centre_idx = (start + end - 1) / 2.0
                positions.append(centre_idx)

                # Month abbreviation from the middle bar
                mid_idx = int((start + end - 1) // 2)
                labels.append(local_dates[mid_idx].strftime("%b"))

            if positions:  # Only set ticks if we have labels to show
                ax.set_xticks(positions)  # pyright: ignore
                ax.set_xticklabels(labels, fontsize=7, ha="center")  # pyright: ignore
            else:
                ax.set_xticks([])  # pyright: ignore
        else:
            # Not enough months - hide labels
            ax.set_xticks([])  # pyright: ignore
    else:
        ax.set_xticks([])  # pyright: ignore

    ax.grid(False)  # pyright: ignore


class OHLCVPlotEnhanced(Base):
    """
    Enhanced OHLCV plot node with SMA/EMA overlays and VBP level calculation.

    - Inputs: either 'ohlcv_bundle' (Dict[AssetSymbol, List[OHLCVBar]]) or 'ohlcv' (Dict[AssetSymbol, List[OHLCVBar]])
    - Calculates VBP levels by fetching weekly bars from Polygon API
    - Optional: overlay1, overlay2 (automatically calculated SMA/EMA from OHLCV data)
    - Output: 'images' -> Dict[str, str] mapping label to data URL
    """

    inputs = {
        "ohlcv_bundle": get_type("OHLCVBundle") | None,
    }
    optional_inputs = ["ohlcv_bundle", "ohlcv"]

    outputs = {
        "images": get_type("ConfigDict"),
    }

    CATEGORY = NodeCategory.MARKET
    default_params = {
        "max_symbols": 12,
        "lookback_bars": 60,  # Default: 60 bars (~3 months of daily data)
        "overlay1_period": 20,
        "overlay1_type": "SMA",
        "overlay2_period": 50,
        "overlay2_type": "SMA",
        "show_vbp_levels": True,
        "vbp_bins": 50,
        "vbp_num_levels": 5,
        "vbp_lookback_years": 2,
        "vbp_use_dollar_weighted": False,
        "vbp_use_close_only": False,
        "vbp_color": "#FF6B35",
        "vbp_style": "dashed",
    }

    params_meta = [
        {"name": "max_symbols", "type": "integer", "default": 12, "min": 1, "max": 64, "step": 4},
        {
            "name": "lookback_bars",
            "type": "number",
            "default": 60,
            "min": 10,
            "max": 5000,
            "step": 10,
        },
        {"name": "overlay1_period", "type": "number", "default": 20, "min": 2, "max": 200, "step": 1},
        {"name": "overlay1_type", "type": "combo", "default": "SMA", "options": ["SMA", "EMA"]},
        {"name": "overlay2_period", "type": "number", "default": 50, "min": 2, "max": 200, "step": 1},
        {"name": "overlay2_type", "type": "combo", "default": "SMA", "options": ["SMA", "EMA"]},
        {"name": "show_vbp_levels", "type": "combo", "default": True, "options": [True, False]},
        {"name": "vbp_bins", "type": "number", "default": 50, "min": 10, "max": 200, "step": 5},
        {"name": "vbp_num_levels", "type": "number", "default": 5, "min": 1, "max": 20, "step": 1},
        {
            "name": "vbp_lookback_years",
            "type": "number",
            "default": 2,
            "min": 1,
            "max": 10,
            "step": 1,
        },
        {
            "name": "vbp_use_dollar_weighted",
            "type": "combo",
            "default": False,
            "options": [True, False],
        },
        {"name": "vbp_use_close_only", "type": "combo", "default": False, "options": [True, False]},
        {"name": "vbp_color", "type": "text", "default": "#FF6B35"},
        {"name": "vbp_style", "type": "combo", "default": "dashed", "options": ["solid", "dashed", "dotted"]},
    ]

    def _get_int_param(self, key: str, default: int) -> int:
        """Get and validate an integer parameter."""
        raw = self.params.get(key, default)
        if not isinstance(raw, int | float):
            return default
        return int(raw)

    def _get_bool_param(self, key: str, default: bool) -> bool:
        """Get and validate a boolean parameter."""
        raw = self.params.get(key, default)
        return bool(raw) if raw is not None else default

    async def _execute_impl(self, inputs: dict[str, Any]) -> dict[str, Any]:
        bundle: dict[AssetSymbol, list[OHLCVBar]] | None = inputs.get("ohlcv_bundle")
        single_bundle: dict[AssetSymbol, list[OHLCVBar]] | None = inputs.get("ohlcv")

        # Merge both inputs if both provided, otherwise use whichever is available
        if bundle and single_bundle:
            bundle = {**bundle, **single_bundle}
        elif single_bundle:
            bundle = single_bundle

        if not bundle:
            raise NodeValidationError(self.id, "Provide either 'ohlcv_bundle' or 'ohlcv'")

        lookback_raw = self.params.get("lookback_bars")
        lookback: int | None = None
        if lookback_raw is not None:
            if isinstance(lookback_raw, int | float | str):
                try:
                    lookback = int(lookback_raw)
                except (ValueError, TypeError):
                    lookback = None

        # Prepare overlay configurations
        overlay_configs: list[tuple[int, str]] = []
        for i in range(1, 3):  # Just overlay1 and overlay2
            period_raw = self.params.get(f"overlay{i}_period", 20 if i == 1 else 50)
            ma_type_raw = self.params.get(f"overlay{i}_type", "SMA")

            if isinstance(period_raw, (int, float)) and isinstance(ma_type_raw, str) and ma_type_raw in ["SMA", "EMA"]:
                overlay_configs.append((int(period_raw), ma_type_raw))

        # VBP parameters
        show_vbp = self._get_bool_param("show_vbp_levels", True)
        vbp_bins = self._get_int_param("vbp_bins", 50)
        vbp_num_levels = self._get_int_param("vbp_num_levels", 5)
        vbp_lookback_years = self._get_int_param("vbp_lookback_years", 2)
        vbp_use_dollar_weighted = self._get_bool_param("vbp_use_dollar_weighted", False)
        vbp_use_close_only = self._get_bool_param("vbp_use_close_only", False)
        vbp_color = str(self.params.get("vbp_color", "#FF6B35"))
        vbp_style = str(self.params.get("vbp_style", "dashed"))

        # Get API key for fetching weekly bars
        api_key: str | None = None
        if show_vbp:
            api_key = APIKeyVault().get("POLYGON_API_KEY")
            if not api_key:
                # If no API key, disable VBP levels
                show_vbp = False

        images: dict[str, str] = {}

        if bundle:
            # Limit symbols for safety
            max_syms_raw = self.params.get("max_symbols") or 12
            max_syms = 12
            if isinstance(max_syms_raw, int | float | str):
                try:
                    max_syms = int(max_syms_raw)
                except (ValueError, TypeError):
                    max_syms = 12

            items = list(bundle.items())[:max_syms]
            for sym, bars in items:
                # Calculate overlays on full data (before trimming to lookback)
                plot_overlays: list[tuple[list[float | None], str, str]] = []
                colors = ["#2196F3", "#FF9800"]  # Blue, Orange

                for i, (period, ma_type) in enumerate(overlay_configs):
                    # Calculate on full data with warmup
                    overlay_values_full = _calculate_overlay(bars, period, ma_type)
                    if overlay_values_full:
                        # Trim overlay to match the lookback window
                        if lookback is not None and lookback > 0:
                            overlay_values = overlay_values_full[-lookback:]
                        else:
                            overlay_values = overlay_values_full
                        label = f"{ma_type} {period}"
                        color = colors[i % len(colors)]
                        plot_overlays.append((overlay_values, label, color))

                # Fetch weekly bars and calculate VBP levels
                vbp_levels_for_sym: list[float] | None = None
                if show_vbp and api_key:
                    try:
                        weekly_bars = await _fetch_weekly_bars_for_vbp(sym, api_key, vbp_lookback_years)
                        if weekly_bars:
                            vbp_levels_for_sym = _calculate_vbp_levels_from_weekly(
                                weekly_bars,
                                vbp_bins,
                                vbp_num_levels,
                                vbp_use_dollar_weighted,
                                vbp_use_close_only,
                            )
                    except Exception as e:
                        # If fetching fails, continue without VBP levels
                        import logging

                        logger = logging.getLogger(__name__)
                        logger.warning(f"Failed to fetch weekly bars for VBP calculation for {sym}: {e}")

                # Normalize and trim bars for display (daily bars from input)
                norm = _normalize_bars(bars)
                if lookback is not None and lookback > 0:
                    norm = norm[-lookback:]

                # Trim overlays to match normalized bars length
                if plot_overlays:
                    trimmed_overlays: list[tuple[list[float | None], str, str]] = []
                    for overlay_values, label, color in plot_overlays:
                        if len(overlay_values) == len(bars):
                            # Need to trim overlay to match norm length
                            if lookback is not None and lookback > 0:
                                trimmed_overlay = overlay_values[-lookback:]
                            else:
                                trimmed_overlay = overlay_values
                            trimmed_overlays.append((trimmed_overlay, label, color))
                    plot_overlays = trimmed_overlays

                fig, ax = plt.subplots(figsize=(3.2, 2.2))  # pyright: ignore
                _plot_candles(
                    ax,
                    norm,
                    plot_overlays if plot_overlays else None,
                    vbp_levels_for_sym if show_vbp else None,
                    vbp_color,
                    vbp_style,
                )
                ax.set_title(str(sym), fontsize=8)  # pyright: ignore
                ax.tick_params(labelsize=7)  # pyright: ignore
                images[str(sym)] = _encode_fig_to_data_url(fig)

        return {"images": images}

