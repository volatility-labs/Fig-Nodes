import pytest
from typing import Dict, List
from nodes.core.market.filters.atrx_filter_node import AtrXFilterNode
from core.types_registry import AssetSymbol, OHLCVBar, IndicatorType

@pytest.fixture
def sample_bundle() -> Dict[AssetSymbol, List[OHLCVBar]]:
    symbol = AssetSymbol("TEST", "STOCKS")
    bars = [{"timestamp": 0, "open": 100, "high": 105, "low": 95, "close": 102, "volume": 10000}] * 60
    return {symbol: bars}

@pytest.mark.asyncio
async def test_atrx_filter_node_outside(sample_bundle):
    params = {"filter_condition": "outside", "upper_threshold": 5.0, "lower_threshold": -3.0}
    node = AtrXFilterNode("test_id", params)
    result = await node.execute({"ohlcv_bundle": sample_bundle})
    assert "filtered_ohlcv_bundle" in result

# Add more tests for inside condition, thresholds, empty input, etc.

@pytest.mark.asyncio
@pytest.mark.parametrize("smoothing", ["RMA", "EMA", "SMA"])
async def test_atrx_filter_node_smoothing(sample_bundle, smoothing):
    params = {"smoothing": smoothing, "filter_condition": "outside", "upper_threshold": 5.0, "lower_threshold": -3.0}
    node = AtrXFilterNode("test_id", params)
    result = await node.execute({"ohlcv_bundle": sample_bundle})
    assert "filtered_ohlcv_bundle" in result
