import pytest
from unittest.mock import patch, AsyncMock, MagicMock
from nodes.core.market.filters.orb_filter_node import OrbFilterNode
from core.types_registry import AssetSymbol, OHLCVBar, IndicatorResult, IndicatorType, AssetClass, IndicatorValue
from core.api_key_vault import APIKeyVault
from services.polygon_service import fetch_bars
import datetime
import pytz
from datetime import timedelta

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

@pytest.fixture
def mock_symbol():
    return AssetSymbol("AAPL", AssetClass.STOCKS)

@pytest.fixture
def mock_ohlcv_bundle(mock_symbol):
    return {mock_symbol: [OHLCVBar(timestamp=1234567890, open=100.0, high=105.0, low=95.0, close=102.0, volume=1000000)]}

@pytest.fixture
def orb_node():
    params = {"or_minutes": 5, "rel_vol_threshold": 100.0, "direction": "both", "avg_period": 14}
    return OrbFilterNode(id=1, params=params)

class TestOrbFilterNode:
    @pytest.mark.asyncio
    @patch('nodes.core.market.filters.orb_filter_node.APIKeyVault')
    @patch('nodes.core.market.filters.orb_filter_node.fetch_bars')
    async def test_calculate_orb_indicator_success(self, mock_fetch_bars, mock_vault, orb_node, mock_symbol):
        # Mock API key
        mock_vault.return_value.get.return_value = "fake_api_key"

        # Mock bars data for multiple days to avoid insufficient days
        today = datetime.datetime.now(pytz.timezone('US/Eastern')).date()
        mock_bars = []
        for day_offset in range(15):  # Enough for avg_period=14
            date = today - datetime.timedelta(days=14 - day_offset)
            open_time_eastern = datetime.datetime.combine(date, datetime.time(9, 30)).replace(tzinfo=pytz.timezone('US/Eastern'))
            open_time_utc = open_time_eastern.astimezone(pytz.utc)
            day_start = int(open_time_utc.timestamp() * 1000)
            is_last_day = (day_offset == 14)
            mock_bars.append({
                "timestamp": day_start,
                "open": 100.0 + day_offset * 0.1,
                "high": 105.0 + day_offset * 0.1,
                "low": 95.0 + day_offset * 0.1,
                "close": 102.0 + day_offset * 0.1,
                "volume": 50000 if is_last_day else 30000  # Higher volume on last day
            })
            # Add a second bar for OR range
            mock_bars.append({
                "timestamp": day_start + 60000,  # Next minute
                "open": 102.0 + day_offset * 0.1,
                "high": 103.0 + day_offset * 0.1,
                "low": 101.0 + day_offset * 0.1,
                "close": 102.5 + day_offset * 0.1,
                "volume": 60000 if is_last_day else 25000
            })
        mock_fetch_bars.return_value = mock_bars

        result = await orb_node._calculate_orb_indicator(mock_symbol, "fake_api_key")

        assert result.indicator_type == IndicatorType.ORB
        assert result.error is None
        assert "rel_vol" in result.values.lines
        assert result.values.series[0]["direction"] in ["bullish", "bearish", "doji"]

    @patch('nodes.core.market.filters.orb_filter_node.APIKeyVault')
    def test_should_pass_filter_bullish_high_vol(self, mock_vault, orb_node):
        # Mock passing result
        mock_result = IndicatorResult(
            indicator_type=IndicatorType.ORB,
            values=IndicatorValue(lines={"rel_vol": 150.0}, series=[{"direction": "bullish"}]),
            params=orb_node.params
        )
        assert orb_node._should_pass_filter(mock_result) is True

    @patch('nodes.core.market.filters.orb_filter_node.APIKeyVault')
    def test_should_pass_filter_bearish_high_vol(self, mock_vault, orb_node):
        # Mock passing result
        mock_result = IndicatorResult(
            indicator_type=IndicatorType.ORB,
            values=IndicatorValue(lines={"rel_vol": 150.0}, series=[{"direction": "bearish"}]),
            params=orb_node.params
        )
        assert orb_node._should_pass_filter(mock_result) is True

    @patch('nodes.core.market.filters.orb_filter_node.APIKeyVault')
    def test_should_pass_filter_low_vol(self, mock_vault, orb_node):
        # Mock failing result - low volume
        mock_result = IndicatorResult(
            indicator_type=IndicatorType.ORB,
            values=IndicatorValue(lines={"rel_vol": 50.0}, series=[{"direction": "bullish"}]),
            params=orb_node.params
        )
        assert orb_node._should_pass_filter(mock_result) is False

    @patch('nodes.core.market.filters.orb_filter_node.APIKeyVault')
    def test_should_pass_filter_doji(self, mock_vault, orb_node):
        # Mock doji
        mock_result = IndicatorResult(
            indicator_type=IndicatorType.ORB,
            values=IndicatorValue(lines={"rel_vol": 150.0}, series=[{"direction": "doji"}]),
            params=orb_node.params
        )
        assert orb_node._should_pass_filter(mock_result) is False

    @pytest.mark.asyncio
    @patch('nodes.core.market.filters.orb_filter_node.APIKeyVault')
    @patch('nodes.core.market.filters.orb_filter_node.fetch_bars')
    async def test_execute_no_data(self, mock_fetch_bars, mock_vault, orb_node):
        mock_vault.return_value.get.return_value = "fake_api_key"
        mock_fetch_bars.return_value = []

        result = await orb_node.execute({"ohlcv_bundle": {}})

        assert result["filtered_ohlcv_bundle"] == {}

    @pytest.mark.asyncio
    @patch('nodes.core.market.filters.orb_filter_node.APIKeyVault')
    @patch('nodes.core.market.filters.orb_filter_node.fetch_bars')
    async def test_execute_error(self, mock_fetch_bars, mock_vault, orb_node, mock_ohlcv_bundle, mock_symbol):
        mock_vault.return_value.get.return_value = "fake_api_key"
        mock_fetch_bars.side_effect = Exception("API error")

        result = await orb_node.execute({"ohlcv_bundle": {mock_symbol: []}})

        assert mock_symbol not in result["filtered_ohlcv_bundle"]

@pytest.mark.asyncio
async def test_execute_happy_path(sample_params, sample_ohlcv):
    node = OrbFilterNode(id=1, params=sample_params)
    inputs = {
        "ohlcv_bundle": {AssetSymbol("AAPL", AssetClass.STOCKS): sample_ohlcv}
    }

    # Mock the calculation to return passing result
    async def mock_calc(symbol, api_key):
        return IndicatorResult(
            indicator_type=IndicatorType.ORB,
            timestamp=1234567890000,
            values=IndicatorValue(lines={"rel_vol": 150.0}, series=[{"direction": "bullish"}]),
            params=sample_params
        )
    node._calculate_orb_indicator = mock_calc

    with patch("core.api_key_vault.APIKeyVault.get", return_value="test_key"):
        result = await node.execute(inputs)

    assert "filtered_ohlcv_bundle" in result
    assert AssetSymbol("AAPL", AssetClass.STOCKS) in result["filtered_ohlcv_bundle"]
    assert result["filtered_ohlcv_bundle"][AssetSymbol("AAPL", AssetClass.STOCKS)] == sample_ohlcv

@pytest.mark.asyncio
async def test_execute_insufficient_days(sample_params, sample_ohlcv):
    node = OrbFilterNode(id=1, params=sample_params)
    inputs = {
        "ohlcv_bundle": {AssetSymbol("AAPL", AssetClass.STOCKS): sample_ohlcv},
    }

    async def mock_calc(symbol, api_key):
        return IndicatorResult(
            indicator_type=IndicatorType.ORB,
            timestamp=1234567890000,
            values=IndicatorValue(lines={"rel_vol": 0.0}),
            params=sample_params,
            error="Insufficient days"
        )
    node._calculate_orb_indicator = mock_calc

    with patch("core.api_key_vault.APIKeyVault.get", return_value="test_key"):
        result = await node.execute(inputs)

    assert result["filtered_ohlcv_bundle"] == {}

@pytest.mark.asyncio
async def test_execute_doji_direction(sample_params, sample_ohlcv):
    node = OrbFilterNode(id=1, params=sample_params)
    inputs = {
        "ohlcv_bundle": {AssetSymbol("AAPL", AssetClass.STOCKS): sample_ohlcv},
    }

    async def mock_calc(symbol, api_key):
        return IndicatorResult(
            indicator_type=IndicatorType.ORB,
            timestamp=1234567890000,
            values=IndicatorValue(lines={"rel_vol": 150.0}, series=[{"direction": "doji"}]),
            params=sample_params
        )
    node._calculate_orb_indicator = mock_calc

    with patch("core.api_key_vault.APIKeyVault.get", return_value="test_key"):
        result = await node.execute(inputs)

    assert result["filtered_ohlcv_bundle"] == {}

@pytest.mark.asyncio
async def test_execute_low_rel_vol(sample_params, sample_ohlcv):
    node = OrbFilterNode(id=1, params=sample_params)
    inputs = {
        "ohlcv_bundle": {AssetSymbol("AAPL", AssetClass.STOCKS): sample_ohlcv},
    }

    async def mock_calc(symbol, api_key):
        return IndicatorResult(
            indicator_type=IndicatorType.ORB,
            timestamp=1234567890000,
            values=IndicatorValue(lines={"rel_vol": 50.0}, series=[{"direction": "bullish"}]),
            params=sample_params
        )
    node._calculate_orb_indicator = mock_calc

    with patch("core.api_key_vault.APIKeyVault.get", return_value="test_key"):
        result = await node.execute(inputs)

    assert result["filtered_ohlcv_bundle"] == {}

@pytest.mark.asyncio
@patch('nodes.core.market.filters.orb_filter_node.fetch_bars')
async def test_execute_fetch_error(mock_fetch_bars, sample_params, sample_ohlcv):
    node = OrbFilterNode(id=1, params=sample_params)
    inputs = {
        "ohlcv_bundle": {AssetSymbol("AAPL", AssetClass.STOCKS): sample_ohlcv},
    }
    mock_fetch_bars.side_effect = Exception("Fetch error")

    with patch("core.api_key_vault.APIKeyVault.get", return_value="test_key"):
        result = await node.execute(inputs)

    assert result["filtered_ohlcv_bundle"] == {}

@pytest.mark.asyncio
async def test_execute_empty_ohlcv(sample_params):
    node = OrbFilterNode(id=1, params=sample_params)
    inputs = {
        "ohlcv_bundle": {AssetSymbol("AAPL", AssetClass.STOCKS): []},
    }

    with patch("core.api_key_vault.APIKeyVault.get", return_value="test_key"):
        result = await node.execute(inputs)

    assert "filtered_ohlcv_bundle" in result
    assert AssetSymbol("AAPL", AssetClass.STOCKS) not in result["filtered_ohlcv_bundle"]  # Empty data skipped

@pytest.mark.asyncio
async def test_execute_no_api_key(sample_params, sample_ohlcv):
    node = OrbFilterNode(id=1, params=sample_params)
    inputs = {
        "ohlcv_bundle": {AssetSymbol("AAPL", AssetClass.STOCKS): sample_ohlcv},
    }

    with pytest.raises(ValueError, match="Polygon API key not found in vault"):
        with patch("core.api_key_vault.APIKeyVault.get", return_value=None):
            await node.execute(inputs)

@pytest.mark.asyncio
async def test_execute_direction_specific(sample_params, sample_ohlcv):
    params = sample_params.copy()
    params["direction"] = "bullish"
    node = OrbFilterNode(id=1, params=params)
    inputs = {
        "ohlcv_bundle": {AssetSymbol("AAPL", AssetClass.STOCKS): sample_ohlcv},
    }

    async def mock_calc_bullish(symbol, api_key):
        return IndicatorResult(
            indicator_type=IndicatorType.ORB,
            timestamp=1234567890000,
            values=IndicatorValue(lines={"rel_vol": 150.0}, series=[{"direction": "bullish"}]),
            params=params
        )

    async def mock_calc_bearish(symbol, api_key):
        return IndicatorResult(
            indicator_type=IndicatorType.ORB,
            timestamp=1234567890000,
            values=IndicatorValue(lines={"rel_vol": 150.0}, series=[{"direction": "bearish"}]),
            params=params
        )

    node._calculate_orb_indicator = mock_calc_bullish
    with patch("core.api_key_vault.APIKeyVault.get", return_value="test_key"):
        result = await node.execute(inputs)

    assert AssetSymbol("AAPL", AssetClass.STOCKS) in result["filtered_ohlcv_bundle"]  # Passes for bullish

    # Test bearish
    params["direction"] = "bearish"
    node = OrbFilterNode(id=1, params=params)  # Re-instantiate with bearish
    node._calculate_orb_indicator = mock_calc_bearish
    with patch("core.api_key_vault.APIKeyVault.get", return_value="test_key"):
        result = await node.execute(inputs)
    assert AssetSymbol("AAPL", AssetClass.STOCKS) in result["filtered_ohlcv_bundle"]  # Passes for bearish

    # Test both
    params["direction"] = "both"
    node = OrbFilterNode(id=1, params=params)
    node._calculate_orb_indicator = mock_calc_bullish  # Using bullish for variety, but either works
    with patch("core.api_key_vault.APIKeyVault.get", return_value="test_key"):
        result = await node.execute(inputs)
    assert AssetSymbol("AAPL", AssetClass.STOCKS) in result["filtered_ohlcv_bundle"]  # Passes for both

