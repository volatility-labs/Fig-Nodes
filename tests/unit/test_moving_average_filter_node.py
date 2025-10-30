import pytest
from typing import List
from unittest.mock import patch
from nodes.core.market.filters.moving_average_filter_node import MovingAverageFilter
from core.types_registry import OHLCVBar, AssetSymbol, AssetClass


@pytest.fixture
def ma_filter_node():
    return MovingAverageFilter(id=1, params={"period": 5, "prior_days": 1, "ma_type": "SMA"})


@pytest.fixture
def ema_filter_node():
    return MovingAverageFilter(id=1, params={"period": 5, "prior_days": 1, "ma_type": "EMA"})


@pytest.fixture
def sample_ohlcv_bars() -> List[OHLCVBar]:
    """Create sample OHLCV bars with increasing closes over 10 days."""
    bars = []
    base_ts = 1672531200000  # 2023-01-01 00:00:00
    for i in range(10):
        ts = base_ts + i * 86400000
        close = 100 + i * 2  # Increasing closes
        bars.append({
            'timestamp': ts,
            'open': close - 1,
            'high': close + 1,
            'low': close - 2,
            'close': close,
            'volume': 1000 + i * 100
        })
    return bars


@pytest.mark.asyncio
@patch('nodes.core.market.filters.moving_average_filter_node.calculate_sma')
async def test_sma_filter_happy_path(mock_calculate_sma, ma_filter_node, sample_ohlcv_bars):
    """Test filter passes when current SMA > previous SMA and price > current SMA."""
    # Mock SMA calculator to return increasing values
    def mock_sma(prices, period):
        # Return increasing SMA values
        result = [None] * (len(prices) - 1)
        result.append(sum(prices[-period:]) / period)
        return {"sma": result}
    
    mock_calculate_sma.side_effect = mock_sma

    inputs = {
        "ohlcv_bundle": {AssetSymbol("TEST", AssetClass.STOCKS): sample_ohlcv_bars}
    }
    result = await ma_filter_node.execute(inputs)

    assert "filtered_ohlcv_bundle" in result
    # Should pass since closes are increasing and price > SMA
    assert AssetSymbol("TEST", AssetClass.STOCKS) in result["filtered_ohlcv_bundle"]


@pytest.mark.asyncio
@patch('nodes.core.market.filters.moving_average_filter_node.calculate_sma')
async def test_sma_filter_does_not_pass(mock_calculate_sma, ma_filter_node, sample_ohlcv_bars):
    """Test filter does not pass when price <= current SMA."""
    # Mock SMA to return values higher than current price
    def mock_sma(prices, period):
        result = [None] * (len(prices) - 1)
        result.append(200.0)  # SMA higher than any close price
        return {"sma": result}
    
    mock_calculate_sma.side_effect = mock_sma

    inputs = {
        "ohlcv_bundle": {AssetSymbol("TEST", AssetClass.STOCKS): sample_ohlcv_bars}
    }
    result = await ma_filter_node.execute(inputs)

    assert "filtered_ohlcv_bundle" in result
    assert AssetSymbol("TEST", AssetClass.STOCKS) not in result["filtered_ohlcv_bundle"]


@pytest.mark.asyncio
async def test_sma_filter_insufficient_data(ma_filter_node):
    """Test handling of insufficient data."""
    bars = []  # Empty data
    inputs = {
        "ohlcv_bundle": {AssetSymbol("TEST", AssetClass.STOCKS): bars}
    }
    result = await ma_filter_node.execute(inputs)

    assert result["filtered_ohlcv_bundle"] == {}


@pytest.mark.asyncio
@patch('nodes.core.market.filters.moving_average_filter_node.calculate_sma')
async def test_sma_filter_zero_prior_days(mock_calculate_sma, ma_filter_node, sample_ohlcv_bars):
    """Test handling of prior_days = 0."""
    ma_filter_node.params["prior_days"] = 0
    ma_filter_node._validate_indicator_params()
    
    def mock_sma(prices, period):
        result = [None] * (len(prices) - 1)
        result.append(sum(prices[-period:]) / period)
        return {"sma": result}
    
    mock_calculate_sma.side_effect = mock_sma

    inputs = {
        "ohlcv_bundle": {AssetSymbol("TEST", AssetClass.STOCKS): sample_ohlcv_bars}
    }
    result = await ma_filter_node.execute(inputs)

    # Should pass if price > SMA (no slope requirement)
    assert AssetSymbol("TEST", AssetClass.STOCKS) in result["filtered_ohlcv_bundle"]


@pytest.mark.asyncio
@patch('nodes.core.market.filters.moving_average_filter_node.calculate_ema')
async def test_ema_filter_happy_path(mock_calculate_ema, ema_filter_node, sample_ohlcv_bars):
    """Test EMA filter passes when current EMA > previous EMA and price > current EMA."""
    def mock_ema(prices, period):
        result = [None] * (len(prices) - 1)
        result.append(sum(prices[-period:]) / period)  # Simplified EMA mock
        return {"ema": result}
    
    mock_calculate_ema.side_effect = mock_ema

    inputs = {
        "ohlcv_bundle": {AssetSymbol("TEST", AssetClass.STOCKS): sample_ohlcv_bars}
    }
    result = await ema_filter_node.execute(inputs)

    assert "filtered_ohlcv_bundle" in result
    assert AssetSymbol("TEST", AssetClass.STOCKS) in result["filtered_ohlcv_bundle"]


@pytest.mark.asyncio
async def test_ma_filter_empty_bundle(ma_filter_node):
    """Test empty input bundle."""
    inputs = {"ohlcv_bundle": {}}
    result = await ma_filter_node.execute(inputs)

    assert result["filtered_ohlcv_bundle"] == {}


@pytest.mark.asyncio
async def test_ma_filter_ma_type_validation():
    """Test that invalid ma_type raises ValueError."""
    with pytest.raises(ValueError, match="ma_type must be 'SMA' or 'EMA'"):
        MovingAverageFilter(id=1, params={"period": 5, "prior_days": 1, "ma_type": "INVALID"})


@pytest.mark.asyncio
async def test_ma_filter_default_params():
    """Test that default params work correctly."""
    node = MovingAverageFilter(id=1, params={})
    assert node.params["ma_type"] == "SMA"
    assert node.params["period"] == 200
    assert node.params["prior_days"] == 1

