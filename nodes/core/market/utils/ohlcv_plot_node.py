import io
import base64
import math
from typing import Dict, Any, List, Tuple

import matplotlib
matplotlib.use("Agg")  # non-interactive backend for server-side rendering
import matplotlib.pyplot as plt

from nodes.base.base_node import Base
from core.types_registry import get_type, AssetSymbol, OHLCVBar, NodeValidationError


def _encode_fig_to_data_url(fig) -> str:
    buf = io.BytesIO()
    fig.savefig(buf, format='png', bbox_inches='tight', dpi=150)
    plt.close(fig)
    buf.seek(0)
    b64 = base64.b64encode(buf.read()).decode('ascii')
    return f"data:image/png;base64,{b64}"


def _normalize_bars(bars: List[OHLCVBar]) -> List[Tuple[int, float, float, float, float]]:
    # Return list of tuples (ts, open, high, low, close) sorted by ts
    cleaned: List[Tuple[int, float, float, float, float]] = []
    for b in bars or []:
        try:
            ts = int(b.get('timestamp') or b.get('t') or 0)
            o = float(b.get('open') or b.get('o'))
            h = float(b.get('high') or b.get('h'))
            l = float(b.get('low') or b.get('l'))
            c = float(b.get('close') or b.get('c'))
        except Exception:
            continue
        cleaned.append((ts, o, h, l, c))
    cleaned.sort(key=lambda x: x[0])
    return cleaned


def _plot_candles(ax, series: List[Tuple[int, float, float, float, float]]):
    if not series:
        ax.set_axis_off()
        return
    xs = list(range(len(series)))
    for i, (_ts, o, h, l, c) in enumerate(series):
        color = '#26a69a' if c >= o else '#ef5350'  # teal for up, red for down
        # wick
        ax.vlines(i, l, h, colors=color, linewidth=1)
        # body
        height = max(abs(c - o), 1e-9)
        bottom = min(o, c)
        ax.add_patch(plt.Rectangle((i - 0.3, bottom), 0.6, height, color=color, alpha=0.9))
    ax.set_xlim(-1, len(series))
    # Nice y padding
    lows = [l for (_ts, _o, _h, l, _c) in series]
    highs = [h for (_ts, _o, h, _l, _c) in series]
    if lows and highs:
        pad = (max(highs) - min(lows)) * 0.05 or 1.0
        ax.set_ylim(min(lows) - pad, max(highs) + pad)
    ax.set_xticks([])
    ax.grid(False)


class OHLCVPlot(Base):
    """
    Renders OHLCV data as candlestick chart(s) and returns base64 PNG image(s).

    - Inputs: either 'ohlcv_bundle' (Dict[AssetSymbol, List[OHLCVBar]]) or 'ohlcv' (List[OHLCVBar])
    - Output: 'images' -> Dict[str, str] mapping label to data URL
    """

    inputs = {
        "ohlcv_bundle": get_type("OHLCVBundle"),
        "ohlcv": get_type("OHLCV"),
    }
    # Always return an object/dict of label->dataURL for consistency
    outputs = {
        "images": get_type("ConfigDict"),
    }
    optional_inputs = ["ohlcv_bundle", "ohlcv"]

    # UI metadata
    CATEGORY = "Market"
    default_params = {
        "max_symbols": 12,
        "lookback_bars": None,  # if set, clip to last N bars
    }
    params_meta = [
        {"name": "max_symbols", "type": "number", "default": 12, "min": 1, "max": 64, "step": 1},
        {"name": "lookback_bars", "type": "number", "default": None, "min": 10, "max": 5000, "step": 10},
    ]

    async def _execute_impl(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        bundle: Dict[AssetSymbol, List[OHLCVBar]] = inputs.get("ohlcv_bundle") or {}
        series: List[OHLCVBar] = inputs.get("ohlcv") or []

        if not bundle and not series:
            raise NodeValidationError(self.id, "Provide either 'ohlcv_bundle' or 'ohlcv'")

        lookback = self.params.get("lookback_bars")

        images: Dict[str, str] = {}

        if bundle:
            # Limit symbols for safety
            max_syms = int(self.params.get("max_symbols") or 12)
            items = list(bundle.items())[:max_syms]
            for sym, bars in items:
                norm = _normalize_bars(bars)
                if lookback:
                    norm = norm[-int(lookback):]
                fig, ax = plt.subplots(figsize=(3.2, 2.2))
                _plot_candles(ax, norm)
                ax.set_title(str(sym), fontsize=8)
                ax.tick_params(labelsize=7)
                images[str(sym)] = _encode_fig_to_data_url(fig)
        else:
            norm = _normalize_bars(series)
            if lookback:
                norm = norm[-int(lookback):]
            fig, ax = plt.subplots(figsize=(4.0, 2.8))
            _plot_candles(ax, norm)
            ax.set_title("OHLCV", fontsize=9)
            ax.tick_params(labelsize=8)
            images["OHLCV"] = _encode_fig_to_data_url(fig)

        return {"images": images}


