
import pytest
import pandas as pd
from nodes.core.market.indicators.atr_indicator_node import ATRIndicator
from core.types_registry import IndicatorType

@pytest.fixture
def sample_ohlcv() -> list[dict[str, float]]:
    # Generate 20 bars for window=14
    return [
        {"timestamp": i * 86400000, "open": 100 + i, "high": 105 + i, "low": 95 + i, "close": 100 + i, "volume": 1000}
        for i in range(20)
    ]

@pytest.mark.asyncio
async def test_atr_indicator_node_happy_path(sample_ohlcv):
    node = ATRIndicator("test", {"window": 14})
    inputs = {"ohlcv": sample_ohlcv}
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
    inputs = {"ohlcv": []}
    result = await node.execute(inputs)
    assert result == {"results": []}

@pytest.mark.asyncio
async def test_atr_indicator_node_zero_volatility():
    ohlcv = [
        {"timestamp": i * 86400000, "open": 100, "high": 100, "low": 100, "close": 100, "volume": 1000}
        for i in range(20)
    ]
    node = ATRIndicator("test", {"window": 14})
    inputs = {"ohlcv": ohlcv}
    result = await node.execute(inputs)
    assert "results" in result
    assert len(result["results"]) == 1
    ind = result["results"][0]
    assert ind["values"]["single"] == 0.0  # ATR should be 0 for no movement

@pytest.mark.asyncio
async def test_atr_indicator_node_small_window():
    ohlcv = [
        {"timestamp": i * 86400000, "open": 100 + i, "high": 105 + i, "low": 95 + i, "close": 100 + i, "volume": 1000}
        for i in range(5)
    ]
    node = ATRIndicator("test", {"window": 3})
    inputs = {"ohlcv": ohlcv}
    result = await node.execute(inputs)
    assert "results" in result
    assert len(result["results"]) == 1
    ind = result["results"][0]
    assert ind["values"]["single"] > 0

@pytest.mark.asyncio
async def test_atr_indicator_node_insufficient_data_for_window():
    ohlcv = [
        {"timestamp": i * 86400000, "open": 100 + i, "high": 105 + i, "low": 95 + i, "close": 100 + i, "volume": 1000}
        for i in range(10)
    ]
    node = ATRIndicator("test", {"window": 14})
    inputs = {"ohlcv": ohlcv}
    result = await node.execute(inputs)
    assert "results" in result
    assert len(result["results"]) == 0

@pytest.mark.asyncio
async def test_atr_indicator_node_with_nan_values():
    ohlcv = [
        {"timestamp": i * 86400000, "open": 100 + i, "high": 105 + i, "low": 95 + i, "close": 100 + i, "volume": 1000}
        for i in range(20)
    ]
    ohlcv[5]["high"] = float('nan')  # Introduce NaN
    node = ATRIndicator("test", {"window": 14})
    inputs = {"ohlcv": ohlcv}
    result = await node.execute(inputs)
    assert "results" in result
    assert len(result["results"]) == 1
    ind = result["results"][0]
    assert ind["values"]["single"] > 0  # ta handles historical NaN gracefully
