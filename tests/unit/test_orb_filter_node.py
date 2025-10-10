import pytest
from unittest.mock import patch, AsyncMock
from nodes.core.market.filters.orb_filter_node import OrbFilterNode
from core.types_registry import AssetSymbol, OHLCVBar, IndicatorResult, IndicatorType, AssetClass

@pytest.fixture
def sample_params():
    return {
        "or_minutes": 5,
        "rel_vol_threshold": 100.0,
        "direction": "both",
        "avg_period": 14,
    }

@pytest.fixture
def empty_ohlcv():
    return []

@pytest.fixture
def sample_ohlcv():
    return [{"timestamp": 1234567890000, "open": 100, "high": 110, "low": 90, "close": 105, "volume": 1000}]

@pytest.mark.asyncio
async def test_execute_happy_path(sample_params, sample_ohlcv):
    node = OrbFilterNode("test_id", sample_params)
    inputs = {
        "ohlcv_bundle": {AssetSymbol("AAPL", AssetClass.STOCKS): sample_ohlcv},
        "api_key": "test_key"
    }

    mock_bars = [
        # Mock bars for multiple days, with OR data that leads to rel_vol > 100, bullish
        # For simplicity, assume fetch returns bars that compute to pass
        {"timestamp": 1234567890000, "open": 100, "high": 110, "low": 90, "close": 105, "volume": 1000},
        # ... more bars for past days with lower volume
    ]

    with patch('nodes.core.market.filters.orb_filter_node.fetch_bars', new_callable=AsyncMock) as mock_fetch:
        mock_fetch.return_value = mock_bars
        # Mock the calculation to return passing result
        async def mock_calc(symbol, api_key):
            return IndicatorResult(
                indicator_type=IndicatorType.ORB,
                timestamp=1234567890000,
                values={"rel_vol": 150.0, "direction": "bullish"},
                params=sample_params
            )
        node._calculate_orb_indicator = mock_calc

        result = await node.execute(inputs)

        assert "filtered_ohlcv_bundle" in result
        assert AssetSymbol("AAPL", AssetClass.STOCKS) in result["filtered_ohlcv_bundle"]
        assert result["filtered_ohlcv_bundle"][AssetSymbol("AAPL", AssetClass.STOCKS)] == sample_ohlcv

@pytest.mark.asyncio
async def test_execute_insufficient_days(sample_params, sample_ohlcv):
    node = OrbFilterNode("test_id", sample_params)
    inputs = {
        "ohlcv_bundle": {AssetSymbol("AAPL", AssetClass.STOCKS): sample_ohlcv},
        "api_key": "test_key"
    }

    with patch('nodes.core.market.filters.orb_filter_node.fetch_bars', new_callable=AsyncMock) as mock_fetch:
        mock_fetch.return_value = [{"timestamp": 1234567890000, "open": 100, "high": 110, "low": 90, "close": 105, "volume": 1000}]  # Only one day

        result = await node.execute(inputs)

        assert "filtered_ohlcv_bundle" in result
        assert AssetSymbol("AAPL", AssetClass.STOCKS) not in result["filtered_ohlcv_bundle"]  # Should not pass due to insufficient days

@pytest.mark.asyncio
async def test_execute_doji_direction(sample_params, sample_ohlcv):
    node = OrbFilterNode("test_id", sample_params)
    inputs = {
        "ohlcv_bundle": {AssetSymbol("AAPL", AssetClass.STOCKS): sample_ohlcv},
        "api_key": "test_key"
    }

    async def mock_calc(symbol, api_key):
        return IndicatorResult(
            indicator_type=IndicatorType.ORB,
            timestamp=1234567890000,
            values={"rel_vol": 150.0, "direction": "doji"},
            params=sample_params
        )
    node._calculate_orb_indicator = mock_calc

    result = await node.execute(inputs)

    assert "filtered_ohlcv_bundle" in result
    assert AssetSymbol("AAPL", AssetClass.STOCKS) not in result["filtered_ohlcv_bundle"]  # Fails on doji

@pytest.mark.asyncio
async def test_execute_low_rel_vol(sample_params, sample_ohlcv):
    node = OrbFilterNode("test_id", sample_params)
    inputs = {
        "ohlcv_bundle": {AssetSymbol("AAPL", AssetClass.STOCKS): sample_ohlcv},
        "api_key": "test_key"
    }

    async def mock_calc(symbol, api_key):
        return IndicatorResult(
            indicator_type=IndicatorType.ORB,
            timestamp=1234567890000,
            values={"rel_vol": 50.0, "direction": "bullish"},
            params=sample_params
        )
    node._calculate_orb_indicator = mock_calc

    result = await node.execute(inputs)

    assert "filtered_ohlcv_bundle" in result
    assert AssetSymbol("AAPL", AssetClass.STOCKS) not in result["filtered_ohlcv_bundle"]  # Fails on low rel_vol

@pytest.mark.asyncio
async def test_execute_fetch_error(sample_params, empty_ohlcv):
    node = OrbFilterNode("test_id", sample_params)
    inputs = {
        "ohlcv_bundle": {AssetSymbol("AAPL", AssetClass.STOCKS): empty_ohlcv},
        "api_key": "test_key"
    }

    with patch('nodes.core.market.filters.orb_filter_node.fetch_bars', new_callable=AsyncMock) as mock_fetch:
        mock_fetch.side_effect = Exception("Fetch error")

        result = await node.execute(inputs)

        assert "filtered_ohlcv_bundle" in result
        assert AssetSymbol("AAPL", AssetClass.STOCKS) not in result["filtered_ohlcv_bundle"]  # Skipped due to error

@pytest.mark.asyncio
async def test_execute_empty_ohlcv(sample_params):
    node = OrbFilterNode("test_id", sample_params)
    inputs = {
        "ohlcv_bundle": {AssetSymbol("AAPL", AssetClass.STOCKS): []},
        "api_key": "test_key"
    }

    result = await node.execute(inputs)

    assert "filtered_ohlcv_bundle" in result
    assert AssetSymbol("AAPL", AssetClass.STOCKS) not in result["filtered_ohlcv_bundle"]  # Empty data skipped

@pytest.mark.asyncio
async def test_execute_no_api_key(sample_params, sample_ohlcv):
    node = OrbFilterNode("test_id", sample_params)
    inputs = {
        "ohlcv_bundle": {AssetSymbol("AAPL", AssetClass.STOCKS): sample_ohlcv},
        "api_key": None
    }

    with pytest.raises(ValueError, match="API key is required"):
        await node.execute(inputs)

@pytest.mark.asyncio
async def test_execute_direction_specific(sample_params, sample_ohlcv):
    params = sample_params.copy()
    params["direction"] = "bullish"
    node = OrbFilterNode("test_id", params)
    inputs = {
        "ohlcv_bundle": {AssetSymbol("AAPL", AssetClass.STOCKS): sample_ohlcv},
        "api_key": "test_key"
    }

    async def mock_calc_bullish(symbol, api_key):
        return IndicatorResult(values={"rel_vol": 150.0, "direction": "bullish"})

    async def mock_calc_bearish(symbol, api_key):
        return IndicatorResult(values={"rel_vol": 150.0, "direction": "bearish"})

    node._calculate_orb_indicator = mock_calc_bullish
    result = await node.execute(inputs)
    assert AssetSymbol("AAPL", AssetClass.STOCKS) in result["filtered_ohlcv_bundle"]  # Passes for bullish

    node._calculate_orb_indicator = mock_calc_bearish
    result = await node.execute(inputs)
    assert AssetSymbol("AAPL", AssetClass.STOCKS) not in result["filtered_ohlcv_bundle"]  # Fails for bearish

