import pytest
import pandas as pd
import numpy as np
from typing import Dict, List
from nodes.core.market.indicators.atrx_indicator_node import AtrXIndicatorNode
from core.types_registry import IndicatorType, IndicatorResult

@pytest.fixture
def sample_ohlcv() -> List[Dict[str, float]]:
    return [
        {"timestamp": 0, "open": 100, "high": 105, "low": 95, "close": 102, "volume": 10000},
        # Add more bars as needed for sufficient data
    ] * 60  # Assuming 60 bars for MA=50 + buffer

@pytest.mark.asyncio
async def test_atrx_indicator_node_happy_path(sample_ohlcv):
    node = AtrXIndicatorNode("test_id", {})
    result = await node.execute({"ohlcv": sample_ohlcv})
    assert "results" in result
    assert len(result["results"]) == 1
    assert result["results"][0]["indicator_type"] == IndicatorType.ATRX
    assert "single" in result["results"][0]["values"]
    assert isinstance(result["results"][0]["values"]["single"], float)

@pytest.mark.asyncio
async def test_atrx_indicator_node_insufficient_data():
    node = AtrXIndicatorNode("test_id", {})
    result = await node.execute({"ohlcv": []})
    assert result == {"results": []}

# Add more tests for params, errors, etc.

@pytest.mark.asyncio
@pytest.mark.parametrize("smoothing", ["RMA", "EMA", "SMA"])
async def test_atrx_indicator_node_smoothing(sample_ohlcv, smoothing):
    node = AtrXIndicatorNode("test_id", {"smoothing": smoothing})
    result = await node.execute({"ohlcv": sample_ohlcv})
    assert "results" in result
    assert len(result["results"]) == 1
    assert result["results"][0]["indicator_type"] == IndicatorType.ATRX
    assert "single" in result["results"][0]["values"]
    assert isinstance(result["results"][0]["values"]["single"], float)
