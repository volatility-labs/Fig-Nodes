
import pytest
import pandas as pd
from nodes.core.market.indicators.atr_indicator_node import ATRIndicator
from core.types_registry import IndicatorType, AssetSymbol, AssetClass

@pytest.fixture
def sample_ohlcv_bundle() -> dict[AssetSymbol, list[dict[str, float]]]:
    symbol = AssetSymbol("TEST", AssetClass.STOCKS)
    bars = [
        {"timestamp": i * 86400000, "open": 100 + i, "high": 105 + i, "low": 95 + i, "close": 100 + i, "volume": 1000}
        for i in range(20)
    ]
    return {symbol: bars}

@pytest.mark.asyncio
async def test_atr_indicator_node_happy_path(sample_ohlcv_bundle):
    node = ATRIndicator("test", {"window": 14})
    inputs = {"ohlcv": sample_ohlcv_bundle}
    result = await node.execute(inputs)
    assert "results" in result
    assert len(result["results"]) == 1
    ind = result["results"][0]
    assert ind["indicator_type"] == IndicatorType.ATR
    assert "single" in ind["values"]
    assert isinstance(ind["values"]["single"], float)
    assert ind["values"]["single"] > 0

@pytest.mark.asyncio
async def test_atr_indicator_node_insufficient_data():
    node = ATRIndicator("test", {"window": 14})
    inputs = {"ohlcv": {}}
    result = await node.execute(inputs)
    assert result == {"results": []}

@pytest.mark.asyncio
async def test_atr_indicator_node_zero_volatility():
    symbol = AssetSymbol("TEST", AssetClass.STOCKS)
    ohlcv = [
        {"timestamp": i * 86400000, "open": 100, "high": 100, "low": 100, "close": 100, "volume": 1000}
        for i in range(20)
    ]
    node = ATRIndicator("test", {"window": 14})
    inputs = {"ohlcv": {symbol: ohlcv}}
    result = await node.execute(inputs)
    assert "results" in result
    assert len(result["results"]) == 1
    ind = result["results"][0]
    assert ind["values"]["single"] == 0.0  # ATR should be 0 for no movement

@pytest.mark.asyncio
async def test_atr_indicator_node_small_window():
    symbol = AssetSymbol("TEST", AssetClass.STOCKS)
    ohlcv = [
        {"timestamp": i * 86400000, "open": 100 + i, "high": 105 + i, "low": 95 + i, "close": 100 + i, "volume": 1000}
        for i in range(5)
    ]
    node = ATRIndicator("test", {"window": 3})
    inputs = {"ohlcv": {symbol: ohlcv}}
    result = await node.execute(inputs)
    assert "results" in result
    assert len(result["results"]) == 1
    ind = result["results"][0]
    assert ind["values"]["single"] > 0

@pytest.mark.asyncio
async def test_atr_indicator_node_insufficient_data_for_window():
    symbol = AssetSymbol("TEST", AssetClass.STOCKS)
    ohlcv = [
        {"timestamp": i * 86400000, "open": 100 + i, "high": 105 + i, "low": 95 + i, "close": 100 + i, "volume": 1000}
        for i in range(10)
    ]
    node = ATRIndicator("test", {"window": 14})
    inputs = {"ohlcv": {symbol: ohlcv}}
    result = await node.execute(inputs)
    assert "results" in result
    assert len(result["results"]) == 0

@pytest.mark.asyncio
async def test_atr_indicator_node_with_nan_values():
    symbol = AssetSymbol("TEST", AssetClass.STOCKS)
    ohlcv = [
        {"timestamp": i * 86400000, "open": 100 + i, "high": 105 + i, "low": 95 + i, "close": 100 + i, "volume": 1000}
        for i in range(20)
    ]
    ohlcv[5]["high"] = float('nan')  # Introduce NaN
    node = ATRIndicator("test", {"window": 14})
    inputs = {"ohlcv": {symbol: ohlcv}}
    result = await node.execute(inputs)
    assert "results" in result
    assert len(result["results"]) == 1
    ind = result["results"][0]
    assert ind["values"]["single"] > 0  # ta handles historical NaN gracefully
