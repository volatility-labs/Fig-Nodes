import base64
import io
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

from core.types_registry import AssetSymbol, NodeCategory, NodeValidationError, OHLCVBar, get_type
from nodes.base.base_node import Base


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


def _plot_candles(ax: "Axes", series: list[tuple[int, float, float, float, float]]) -> None:
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
    ax.set_xlim(-1, len(series))
    # Nice y padding
    lows = [low for (_ts, _o, _h, low, _c) in series]
    highs = [h for (_ts, _o, h, _l, _c) in series]
    if lows and highs:
        pad = (max(highs) - min(lows)) * 0.05 or 1.0
        ax.set_ylim(min(lows) - pad, max(highs) + pad)
    ax.set_xticks([])  # pyright: ignore
    ax.grid(False)  # pyright: ignore


class OHLCVPlot(Base):
    """
    Renders OHLCV data as candlestick chart(s) and returns base64 PNG image(s).

    - Inputs: either 'ohlcv_bundle' (Dict[AssetSymbol, List[OHLCVBar]]) or 'ohlcv' (Dict[AssetSymbol, List[OHLCVBar]])
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
        "lookback_bars": None,  # if set, clip to last N bars
    }
    params_meta = [
        {"name": "max_symbols", "type": "integer", "default": 12, "min": 1, "max": 64, "step": 4},
        {
            "name": "lookback_bars",
            "type": "number",
            "default": None,
            "min": 10,
            "max": 5000,
            "step": 10,
        },
    ]

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
        images: dict[str, str] = {}

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
            norm = _normalize_bars(bars)
            if lookback is not None and lookback > 0:
                norm = norm[-lookback:]
            fig, ax = plt.subplots(figsize=(3.2, 2.2))  # pyright: ignore
            _plot_candles(ax, norm)
            ax.set_title(str(sym), fontsize=8)  # pyright: ignore
            ax.tick_params(labelsize=7)  # pyright: ignore
            images[str(sym)] = _encode_fig_to_data_url(fig)

        return {"images": images}
