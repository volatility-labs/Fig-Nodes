import pytest
from typing import Dict, List

from nodes.core.market.utils.ohlcv_plot_node import OHLCVPlot
from core.types_registry import AssetSymbol, AssetClass, OHLCVBar


def _sample_bars(n: int = 20) -> List[OHLCVBar]:
    return [
        OHLCVBar(timestamp=i * 86400000, open=100 + i, high=105 + i, low=95 + i, close=100 + i, volume=1000)
        for i in range(n)
    ]


@pytest.mark.asyncio
async def test_plot_node_single_series():
    node = OHLCVPlot(id=1, params={})
    symbol = AssetSymbol("TEST", AssetClass.STOCKS)
    bundle = {symbol: _sample_bars(30)}
    inputs = {"ohlcv": bundle}
    out = await node.execute(inputs)
    assert "images" in out
    imgs = out["images"]
    assert isinstance(imgs, dict)
    assert str(symbol) in imgs
    assert isinstance(imgs[str(symbol)], str)
    assert imgs[str(symbol)].startswith("data:image/png;base64,")


@pytest.mark.asyncio
async def test_plot_node_bundle_multiple_symbols():
    node = OHLCVPlot(id=1, params={"max_symbols": 2})
    sym1 = AssetSymbol("AAPL", AssetClass.STOCKS)
    sym2 = AssetSymbol("MSFT", AssetClass.STOCKS)
    bundle: Dict[AssetSymbol, List[OHLCVBar]] = {sym1: _sample_bars(25), sym2: _sample_bars(25)}
    out = await node.execute({"ohlcv_bundle": bundle})
    imgs = out["images"]
    assert set(imgs.keys()) == {str(sym1), str(sym2)}
    for v in imgs.values():
        assert v.startswith("data:image/png;base64,")


@pytest.mark.asyncio
async def test_plot_node_lookback_applied():
    node = OHLCVPlot(id=1, params={"lookback_bars": 10})
    symbol = AssetSymbol("TEST", AssetClass.STOCKS)
    bundle = {symbol: _sample_bars(50)}
    out = await node.execute({"ohlcv": bundle})
    # Still should produce an image
    assert out["images"][str(symbol)].startswith("data:image/png;base64,")


@pytest.mark.asyncio
async def test_plot_node_requires_input():
    node = OHLCVPlot(id=1, params={})
    with pytest.raises(Exception):
        await node.execute({})


