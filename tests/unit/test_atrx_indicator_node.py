import pytest
import pandas as pd
import numpy as np
from typing import Dict, List
from nodes.core.market.indicators.atrx_indicator_node import AtrXIndicator
from core.types_registry import IndicatorType, IndicatorResult
from unittest.mock import patch

@pytest.fixture
def sample_ohlcv() -> List[Dict[str, float]]:
    return [
        {"timestamp": 0, "open": 100, "high": 105, "low": 95, "close": 102, "volume": 10000},
        # Add more bars as needed for sufficient data
    ] * 60  # Assuming 60 bars for MA=50 + buffer

@pytest.fixture
def varying_ohlcv() -> List[Dict[str, float]]:
    """OHLCV data with varying prices to test trend detection"""
    return [
        {"timestamp": i * 1000, "open": 100 + i, "high": 105 + i, "low": 95 + i, "close": 102 + i, "volume": 10000}
        for i in range(60)
    ]

@pytest.fixture
def insufficient_ohlcv() -> List[Dict[str, float]]:
    """OHLCV data with insufficient bars for calculation"""
    return [
        {"timestamp": i * 1000, "open": 100, "high": 105, "low": 95, "close": 102, "volume": 10000}
        for i in range(10)  # Only 10 bars, insufficient for MA=50
    ]

@pytest.fixture
def extreme_ohlcv() -> List[Dict[str, float]]:
    """OHLCV data with extreme values"""
    return [
        {"timestamp": i * 1000, "open": 1000, "high": 1000, "low": 1000, "close": 1000, "volume": 10000}
        for i in range(60)  # Zero volatility (high = low)
    ]

@pytest.mark.asyncio
async def test_atrx_indicator_node_happy_path(sample_ohlcv):
    node = AtrXIndicator("test_id", {})
    result = await node.execute({"ohlcv": sample_ohlcv})
    assert "results" in result
    assert len(result["results"]) == 1
    assert result["results"][0].indicator_type == IndicatorType.ATRX
    assert hasattr(result["results"][0].values, 'single')
    assert isinstance(result["results"][0].values.single, float)
    # With constant data: close=102, high=105, low=95, daily_avg=100
    # EMA trend ≈ 100, ATR = 10, ATRX = (102-100)/10 = 0.2
    atrx_value = result["results"][0].values.single
    assert abs(atrx_value - 0.2) < 0.1  # Should be close to 0.2

@pytest.mark.asyncio
async def test_atrx_indicator_node_insufficient_data():
    node = AtrXIndicator("test_id", {})
    result = await node.execute({"ohlcv": []})
    assert result == {"results": []}

# Add more tests for params, errors, etc.

@pytest.mark.asyncio
async def test_atrx_indicator_node_varying_data(varying_ohlcv):
    """Test ATRX calculation with trending data"""
    node = AtrXIndicator("test_id", {})
    result = await node.execute({"ohlcv": varying_ohlcv})
    assert "results" in result
    assert len(result["results"]) == 1
    assert result["results"][0].indicator_type == IndicatorType.ATRX
    atrx_value = result["results"][0].values.single
    assert isinstance(atrx_value, float)
    # With trending up data, ATRX should be positive
    assert atrx_value > 0

@pytest.mark.asyncio
async def test_atrx_indicator_node_insufficient_data(insufficient_ohlcv):
    """Test behavior with insufficient data"""
    node = AtrXIndicator("test_id", {})
    result = await node.execute({"ohlcv": insufficient_ohlcv})
    assert "results" in result
    assert len(result["results"]) == 0  # Should return empty results

@pytest.mark.asyncio
async def test_atrx_indicator_node_extreme_values(extreme_ohlcv):
    """Test behavior with extreme values (zero volatility)"""
    node = AtrXIndicator("test_id", {})
    result = await node.execute({"ohlcv": extreme_ohlcv})
    assert "results" in result
    assert len(result["results"]) == 0  # Should return empty results due to zero ATR

@pytest.mark.asyncio
@pytest.mark.parametrize("length,ma_length", [(14, 50), (21, 30), (7, 20)])
async def test_atrx_indicator_node_different_params(sample_ohlcv, length, ma_length):
    """Test ATRX with different parameter combinations"""
    node = AtrXIndicator("test_id", {"length": length, "ma_length": ma_length})
    result = await node.execute({"ohlcv": sample_ohlcv})
    assert "results" in result
    assert len(result["results"]) == 1
    assert result["results"][0].indicator_type == IndicatorType.ATRX
    atrx_value = result["results"][0].values.single
    assert isinstance(atrx_value, float)

@pytest.mark.asyncio
async def test_atrx_indicator_node_empty_input():
    """Test behavior with empty input"""
    node = AtrXIndicator("test_id", {})
    result = await node.execute({"ohlcv": []})
    assert result == {"results": []}

@pytest.mark.asyncio
async def test_atrx_indicator_node_missing_input():
    """Test behavior with missing ohlcv input"""
    from core.types_registry import NodeValidationError
    node = AtrXIndicator("test_id", {})
    with pytest.raises(NodeValidationError):
        await node.execute({})

@pytest.mark.asyncio
async def test_atrx_indicator_node_malformed_data():
    """Test behavior with malformed OHLCV data"""
    node = AtrXIndicator("test_id", {})
    malformed_data = [
        {"timestamp": 0, "open": 100, "high": 105, "low": 95, "close": 102, "volume": 10000},
        {"timestamp": 1000, "open": "invalid", "high": 105, "low": 95, "close": 102, "volume": 10000},  # Invalid open
    ] * 30
    with pytest.raises(TypeError):
        await node.execute({"ohlcv": malformed_data})

@pytest.mark.asyncio
async def test_atrx_indicator_node_calculation_error(sample_ohlcv):
    """Test behavior when calculation service raises an error"""
    node = AtrXIndicator("test_id", {})
    with patch.object(node.indicators_service, 'calculate_atrx') as mock_calc:
        mock_calc.side_effect = Exception("Calculation error")
        result = await node.execute({"ohlcv": sample_ohlcv})
        assert "results" in result
        assert len(result["results"]) == 0  # Should return empty results on error

@pytest.mark.asyncio
async def test_atrx_indicator_node_nan_result(sample_ohlcv):
    """Test behavior when calculation returns NaN"""
    node = AtrXIndicator("test_id", {})
    with patch.object(node.indicators_service, 'calculate_atrx') as mock_calc:
        mock_calc.return_value = float('nan')
        result = await node.execute({"ohlcv": sample_ohlcv})
        assert "results" in result
        assert len(result["results"]) == 0  # Should return empty results for NaN

@pytest.mark.asyncio
async def test_atrx_indicator_node_result_structure(sample_ohlcv):
    """Test the structure of the returned result"""
    node = AtrXIndicator("test_id", {})
    result = await node.execute({"ohlcv": sample_ohlcv})
    assert "results" in result
    assert isinstance(result["results"], list)
    assert len(result["results"]) == 1
    
    indicator_result = result["results"][0]
    assert isinstance(indicator_result, IndicatorResult)
    assert indicator_result.indicator_type == IndicatorType.ATRX
    assert hasattr(indicator_result, 'timestamp')
    assert hasattr(indicator_result, 'values')
    assert hasattr(indicator_result.values, 'single')
    assert isinstance(indicator_result.values.single, float)

@pytest.mark.asyncio
async def test_atrx_indicator_node_default_params(sample_ohlcv):
    """Test that default parameters are used correctly"""
    node = AtrXIndicator("test_id", {})  # No params provided
    with patch.object(node.indicators_service, 'calculate_atrx') as mock_calc:
        mock_calc.return_value = 1.5
        result = await node.execute({"ohlcv": sample_ohlcv})
        mock_calc.assert_called_once()
        call_args = mock_calc.call_args
        # Check that default parameters are used
        assert call_args[1]['length'] == 14
        assert call_args[1]['ma_length'] == 50
        assert call_args[1]['smoothing'] == 'SMA'
        assert call_args[1]['price'] == 'Close'
