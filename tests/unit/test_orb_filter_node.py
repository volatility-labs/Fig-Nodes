import pytest
import asyncio
import time
from unittest.mock import patch, AsyncMock, MagicMock
from nodes.core.market.filters.orb_filter_node import OrbFilter, RateLimiter
from core.types_registry import AssetSymbol, OHLCVBar, IndicatorResult, IndicatorType, AssetClass, IndicatorValue, NodeExecutionError
from core.api_key_vault import APIKeyVault
from services.polygon_service import fetch_bars
from datetime import datetime, timedelta
import pytz
import pandas as pd

@pytest.fixture
def sample_params():
    return {
        "or_minutes": 5,
        "rel_vol_threshold": 100.0,
        "direction": "both",
        "avg_period": 14,
        "max_concurrent": 10,
        "rate_limit_per_second": 95,
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
    params = {"or_minutes": 5, "rel_vol_threshold": 100.0, "direction": "both", "avg_period": 14, "max_concurrent": 10, "rate_limit_per_second": 95}
    return OrbFilter(id=1, params=params)

@pytest.fixture
def sample_symbols():
    return [
        AssetSymbol("AAPL", AssetClass.STOCKS),
        AssetSymbol("MSFT", AssetClass.STOCKS),
        AssetSymbol("GOOGL", AssetClass.STOCKS),
    ]

@pytest.fixture
def mock_ohlcv_bundle_extended(sample_symbols):
    return {
        symbol: [OHLCVBar(timestamp=1234567890, open=100.0, high=105.0, low=95.0, close=102.0, volume=1000000)]
        for symbol in sample_symbols
    }

class TestRateLimiter:
    """Tests for the RateLimiter class."""

    @pytest.fixture
    def rate_limiter(self):
        return RateLimiter(max_per_second=10)

    @pytest.mark.asyncio
    async def test_rate_limiter_basic(self, rate_limiter):
        """Test basic rate limiting functionality."""
        start_time = time.time()

        # Should allow 10 requests without delay
        for i in range(10):
            await rate_limiter.acquire()

        # 11th request should be delayed
        await rate_limiter.acquire()
        elapsed = time.time() - start_time

        # Should have taken at least 0.1 seconds (1/10 per second)
        assert elapsed >= 0.09  # Allow some tolerance

    @pytest.mark.asyncio
    async def test_rate_limiter_cleanup_old_requests(self, rate_limiter):
        """Test that old requests are cleaned up from the queue."""
        # Add some old requests manually
        old_time = time.time() - 2.0  # 2 seconds ago
        rate_limiter.requests = [old_time] * 5

        # New request should not be delayed since old ones are cleaned up
        start_time = time.time()
        await rate_limiter.acquire()
        elapsed = time.time() - start_time

        # Should not be delayed
        assert elapsed < 0.01

    @pytest.mark.asyncio
    async def test_rate_limiter_concurrent_access(self, rate_limiter):
        """Test rate limiter works correctly with concurrent access."""
        async def make_request():
            await rate_limiter.acquire()
            return time.time()

        # Launch multiple concurrent requests
        tasks = [asyncio.create_task(make_request()) for _ in range(15)]
        results = await asyncio.gather(*tasks)

        # First 10 should complete quickly, next 5 should be delayed
        sorted_times = sorted(results)
        time_span = sorted_times[-1] - sorted_times[0]

        # Should take at least 0.4 seconds for 15 requests at 10/sec
        assert time_span >= 0.4

    def test_rate_limiter_initialization(self):
        """Test RateLimiter initialization."""
        limiter = RateLimiter(max_per_second=50)
        assert limiter.max_per_second == 50
        assert limiter.requests == []
        assert isinstance(limiter.lock, asyncio.Lock)

class TestOrbFilter:
    @pytest.mark.asyncio
    @patch('nodes.core.market.filters.orb_filter_node.APIKeyVault')
    @patch('nodes.core.market.filters.orb_filter_node.fetch_bars')
    async def test_calculate_orb_indicator_success(self, mock_fetch_bars, mock_vault, orb_node, mock_symbol):
        # Mock API key
        mock_vault.return_value.get.return_value = "fake_api_key"

        # Mock bars data for multiple days to avoid insufficient days
        today = datetime.now(pytz.timezone('US/Eastern')).date()
        mock_bars = []
        for day_offset in range(15):  # Enough for avg_period=14
            date = today - timedelta(days=14 - day_offset)
            open_time_eastern = datetime.combine(date, datetime.strptime('09:30', '%H:%M').time()).replace(tzinfo=pytz.timezone('US/Eastern'))
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

    @pytest.mark.asyncio
    async def test_execute_empty_ohlcv_bundle(self, orb_node):
        """Test execution with empty OHLCV bundle."""
        with patch("core.api_key_vault.APIKeyVault.get", return_value="test_key"):
            result = await orb_node.execute({"ohlcv_bundle": {}})
        assert result == {"filtered_ohlcv_bundle": {}}

    @pytest.mark.asyncio
    async def test_execute_missing_api_key(self, orb_node, mock_ohlcv_bundle_extended):
        """Test error when API key is not found in vault."""
        with patch("core.api_key_vault.APIKeyVault.get", return_value=None):
            with pytest.raises(NodeExecutionError) as exc_info:
                await orb_node.execute({"ohlcv_bundle": mock_ohlcv_bundle_extended})
            assert isinstance(exc_info.value.original_exc, ValueError)
            assert str(exc_info.value.original_exc) == "Polygon API key not found in vault"

    @pytest.mark.asyncio
    async def test_execute_successful_concurrent_filtering(self, orb_node, mock_ohlcv_bundle_extended):
        """Test successful concurrent filtering of multiple symbols."""
        async def mock_calc(symbol, api_key):
            # Return passing result for all symbols
            return IndicatorResult(
                indicator_type=IndicatorType.ORB,
                timestamp=1234567890000,
                values=IndicatorValue(lines={"rel_vol": 150.0}, series=[{"direction": "bullish"}]),
                params=orb_node.params
            )

        orb_node._calculate_orb_indicator = mock_calc

        with patch("core.api_key_vault.APIKeyVault.get", return_value="test_key"):
            result = await orb_node.execute({"ohlcv_bundle": mock_ohlcv_bundle_extended})

        assert "filtered_ohlcv_bundle" in result
        bundle = result["filtered_ohlcv_bundle"]
        assert isinstance(bundle, dict)
        assert len(bundle) == 3  # All symbols should pass filter

        for symbol in mock_ohlcv_bundle_extended.keys():
            assert symbol in bundle
            assert bundle[symbol] == mock_ohlcv_bundle_extended[symbol]

    @pytest.mark.asyncio
    async def test_execute_partial_failures(self, orb_node, mock_ohlcv_bundle_extended):
        """Test handling of partial failures in concurrent filtering."""
        call_count = 0
        
        async def mock_calc_with_failure(symbol, api_key):
            nonlocal call_count
            call_count += 1
            if symbol.ticker == "MSFT":
                raise Exception("API rate limit exceeded")
            return IndicatorResult(
                indicator_type=IndicatorType.ORB,
                timestamp=1234567890000,
                values=IndicatorValue(lines={"rel_vol": 150.0}, series=[{"direction": "bullish"}]),
                params=orb_node.params
            )

        orb_node._calculate_orb_indicator = mock_calc_with_failure

        with patch("core.api_key_vault.APIKeyVault.get", return_value="test_key"):
            result = await orb_node.execute({"ohlcv_bundle": mock_ohlcv_bundle_extended})

        bundle = result["filtered_ohlcv_bundle"]
        # AAPL and GOOGL should succeed, MSFT should be missing due to error
        assert len(bundle) == 2
        symbols = list(mock_ohlcv_bundle_extended.keys())
        assert symbols[0] in bundle  # AAPL
        assert symbols[1] not in bundle  # MSFT (failed)
        assert symbols[2] in bundle  # GOOGL

    @pytest.mark.asyncio
    async def test_execute_no_symbol_limit(self, orb_node):
        """Test that there are no symbol limits."""
        # Create 60 symbols - should process all of them
        symbols = [AssetSymbol(f"SYMBOL_{i}", AssetClass.STOCKS) for i in range(60)]
        ohlcv_bundle = {
            symbol: [OHLCVBar(timestamp=1234567890, open=100.0, high=105.0, low=95.0, close=102.0, volume=1000000)]
            for symbol in symbols
        }

        async def mock_calc(symbol, api_key):
            return IndicatorResult(
                indicator_type=IndicatorType.ORB,
                timestamp=1234567890000,
                values=IndicatorValue(lines={"rel_vol": 150.0}, series=[{"direction": "bullish"}]),
                params=orb_node.params
            )

        orb_node._calculate_orb_indicator = mock_calc

        with patch("core.api_key_vault.APIKeyVault.get", return_value="test_key"):
            result = await orb_node.execute({"ohlcv_bundle": ohlcv_bundle})

        # Should process all 60 symbols
        bundle = result["filtered_ohlcv_bundle"]
        assert len(bundle) == 60

    @pytest.mark.asyncio
    async def test_execute_concurrency_control(self, orb_node):
        """Test concurrency limiting."""
        # Create many symbols to test concurrency
        symbols = [AssetSymbol(f"SYMBOL_{i}", AssetClass.STOCKS) for i in range(20)]
        ohlcv_bundle = {
            symbol: [OHLCVBar(timestamp=1234567890, open=100.0, high=105.0, low=95.0, close=102.0, volume=1000000)]
            for symbol in symbols
        }

        async def slow_calc(symbol, api_key):
            # Make calculation take some time to test concurrency
            await asyncio.sleep(0.01)
            return IndicatorResult(
                indicator_type=IndicatorType.ORB,
                timestamp=1234567890000,
                values=IndicatorValue(lines={"rel_vol": 150.0}, series=[{"direction": "bullish"}]),
                params=orb_node.params
            )

        orb_node._calculate_orb_indicator = slow_calc

        start_time = time.time()
        with patch("core.api_key_vault.APIKeyVault.get", return_value="test_key"):
            result = await orb_node.execute({"ohlcv_bundle": ohlcv_bundle})
        elapsed = time.time() - start_time

        # With max_concurrent=5, should take longer than if all ran in parallel
        # but faster than if they ran sequentially
        assert elapsed >= 0.04  # At least 4 batches of 5 concurrent requests

        assert len(result["filtered_ohlcv_bundle"]) == 20

    @pytest.mark.asyncio
    async def test_execute_rate_limiting(self, orb_node):
        """Test rate limiting functionality."""
        symbols = [AssetSymbol(f"SYMBOL_{i}", AssetClass.STOCKS) for i in range(20)]
        ohlcv_bundle = {
            symbol: [OHLCVBar(timestamp=1234567890, open=100.0, high=105.0, low=95.0, close=102.0, volume=1000000)]
            for symbol in symbols
        }

        async def rate_limited_calc(symbol, api_key):
            # Simulate some processing time and rate limiting
            await asyncio.sleep(0.01)
            return IndicatorResult(
                indicator_type=IndicatorType.ORB,
                timestamp=1234567890000,
                values=IndicatorValue(lines={"rel_vol": 150.0}, series=[{"direction": "bullish"}]),
                params=orb_node.params
            )

        orb_node._calculate_orb_indicator = rate_limited_calc

        start_time = time.time()
        with patch("core.api_key_vault.APIKeyVault.get", return_value="test_key"):
            result = await orb_node.execute({"ohlcv_bundle": ohlcv_bundle})
        elapsed = time.time() - start_time

        # With rate limiting and concurrency control, should take some time
        assert elapsed >= 0.03  # Should take at least some time due to concurrency and simulated calc time
        assert len(result["filtered_ohlcv_bundle"]) == 20

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
    async def test_execute_cancellation_during_calculation(self, orb_node, mock_ohlcv_bundle_extended):
        """Test handling of cancellation during ORB calculation."""

        async def slow_calc(symbol, api_key):
            await asyncio.sleep(1.0)  # Simulate long calculation
            return IndicatorResult(
                indicator_type=IndicatorType.ORB,
                timestamp=1234567890000,
                values=IndicatorValue(lines={"rel_vol": 150.0}, series=[{"direction": "bullish"}]),
                params=orb_node.params
            )

        orb_node._calculate_orb_indicator = slow_calc

        with patch("core.api_key_vault.APIKeyVault.get", return_value="test_key"):
            execute_task = asyncio.create_task(orb_node.execute({"ohlcv_bundle": mock_ohlcv_bundle_extended}))

            await asyncio.sleep(0.1)  # Let it start
            execute_task.cancel()

            with pytest.raises(asyncio.CancelledError):
                await execute_task

    @pytest.mark.asyncio
    async def test_force_stop_cancels_workers(self, orb_node, mock_ohlcv_bundle_extended):
        """Test that force_stop cancels internal workers."""
        async def slow_calc(symbol, api_key):
            await asyncio.sleep(0.5)  # Simulate ongoing calculation
            return IndicatorResult(
                indicator_type=IndicatorType.ORB,
                timestamp=1234567890000,
                values=IndicatorValue(lines={"rel_vol": 150.0}, series=[{"direction": "bullish"}]),
                params=orb_node.params
            )

        orb_node._calculate_orb_indicator = slow_calc

        with patch("core.api_key_vault.APIKeyVault.get", return_value="test_key"):
            execute_task = asyncio.create_task(orb_node.execute({"ohlcv_bundle": mock_ohlcv_bundle_extended}))

            await asyncio.sleep(0.1)  # Let workers start
            assert len(orb_node.workers) > 0
            assert any(not w.done() for w in orb_node.workers)

            orb_node.force_stop()

            # Workers should be cancelled
            await asyncio.sleep(0.1)
            assert all(w.cancelled() or w.done() for w in orb_node.workers)

            execute_task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await execute_task

    @pytest.mark.asyncio
    async def test_force_stop_idempotent(self, orb_node):
        """Test that force_stop is idempotent."""
        # Call force_stop multiple times
        orb_node.force_stop()
        orb_node.force_stop()
        orb_node.force_stop()

        # Should not raise any errors and be in stopped state
        assert orb_node._is_stopped is True

    @pytest.mark.asyncio
    async def test_progress_reporting_during_execution(self, orb_node, mock_ohlcv_bundle_extended):
        """Test that progress is reported during execution."""
        progress_calls = []

        def mock_report(progress, text):
            progress_calls.append((progress, text))

        orb_node.report_progress = mock_report

        async def slow_calc(symbol, api_key):
            await asyncio.sleep(0.01)  # Brief delay to ensure progress reporting
            return IndicatorResult(
                indicator_type=IndicatorType.ORB,
                timestamp=1234567890000,
                values=IndicatorValue(lines={"rel_vol": 150.0}, series=[{"direction": "bullish"}]),
                params=orb_node.params
            )

        orb_node._calculate_orb_indicator = slow_calc

        with patch("core.api_key_vault.APIKeyVault.get", return_value="test_key"):
            await orb_node.execute({"ohlcv_bundle": mock_ohlcv_bundle_extended})

        # Should have progress calls
        assert len(progress_calls) > 0
        # First call should be 0%
        assert progress_calls[0][0] == 0.0
        # Last call should be 100%
        assert progress_calls[-1][0] == 100.0

@pytest.mark.asyncio
async def test_execute_happy_path(sample_params, sample_ohlcv):
    node = OrbFilter(id=1, params=sample_params)
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
    node = OrbFilter(id=1, params=sample_params)
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
    node = OrbFilter(id=1, params=sample_params)
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
    node = OrbFilter(id=1, params=sample_params)
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
    node = OrbFilter(id=1, params=sample_params)
    inputs = {
        "ohlcv_bundle": {AssetSymbol("AAPL", AssetClass.STOCKS): sample_ohlcv},
    }
    mock_fetch_bars.side_effect = Exception("Fetch error")

    with patch("core.api_key_vault.APIKeyVault.get", return_value="test_key"):
        result = await node.execute(inputs)
        
        # With concurrent implementation, fetch errors are caught and logged, 
        # but execution continues and returns empty filtered bundle
        assert "filtered_ohlcv_bundle" in result
        assert result["filtered_ohlcv_bundle"] == {}

@pytest.mark.asyncio
async def test_execute_empty_ohlcv(sample_params):
    node = OrbFilter(id=1, params=sample_params)
    inputs = {
        "ohlcv_bundle": {AssetSymbol("AAPL", AssetClass.STOCKS): []},
    }

    with patch("core.api_key_vault.APIKeyVault.get", return_value="test_key"):
        result = await node.execute(inputs)

    assert "filtered_ohlcv_bundle" in result
    assert AssetSymbol("AAPL", AssetClass.STOCKS) not in result["filtered_ohlcv_bundle"]  # Empty data skipped

@pytest.mark.asyncio
async def test_execute_no_api_key(sample_params, sample_ohlcv):
    node = OrbFilter(id=1, params=sample_params)
    inputs = {
        "ohlcv_bundle": {AssetSymbol("AAPL", AssetClass.STOCKS): sample_ohlcv},
    }

    with pytest.raises(NodeExecutionError):
        with patch("core.api_key_vault.APIKeyVault.get", return_value=None):
            await node.execute(inputs)

@pytest.mark.asyncio
async def test_execute_direction_specific(sample_params, sample_ohlcv):
    params = sample_params.copy()
    params["direction"] = "bullish"
    node = OrbFilter(id=1, params=params)
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
    node = OrbFilter(id=1, params=params)  # Re-instantiate with bearish
    node._calculate_orb_indicator = mock_calc_bearish
    with patch("core.api_key_vault.APIKeyVault.get", return_value="test_key"):
        result = await node.execute(inputs)
    assert AssetSymbol("AAPL", AssetClass.STOCKS) in result["filtered_ohlcv_bundle"]  # Passes for bearish

    # Test both
    params["direction"] = "both"
    node = OrbFilter(id=1, params=params)
    node._calculate_orb_indicator = mock_calc_bullish  # Using bullish for variety, but either works
    with patch("core.api_key_vault.APIKeyVault.get", return_value="test_key"):
        result = await node.execute(inputs)
    assert AssetSymbol("AAPL", AssetClass.STOCKS) in result["filtered_ohlcv_bundle"]  # Passes for both


class TestOrbFilterAssetClassLogic:
    """Test asset class specific logic for ORB filter"""

    def test_get_target_date_for_orb_stocks_with_today_data(self):
        """Test that stocks use today's date when data is available"""
        node = OrbFilter(id=1, params={"or_minutes": 5, "rel_vol_threshold": 100.0, "direction": "both", "avg_period": 14})
        symbol = AssetSymbol("AAPL", AssetClass.STOCKS)
        today_date = datetime.now(pytz.timezone('US/Eastern')).date()
        
        # Mock DataFrame with today's data
        mock_df = pd.DataFrame({
            'date': [today_date, today_date - timedelta(days=1)]
        })
        
        target_date = node._get_target_date_for_orb(symbol, today_date, mock_df)
        assert target_date == today_date

    def test_get_target_date_for_orb_stocks_without_today_data(self):
        """Test that stocks use last trading day when today has no data"""
        node = OrbFilter(id=1, params={"or_minutes": 5, "rel_vol_threshold": 100.0, "direction": "both", "avg_period": 14})
        symbol = AssetSymbol("AAPL", AssetClass.STOCKS)
        today_date = datetime.now(pytz.timezone('US/Eastern')).date()
        last_trading_day = today_date - timedelta(days=1)
        
        # Mock DataFrame without today's data
        mock_df = pd.DataFrame({
            'date': [last_trading_day, last_trading_day - timedelta(days=1)]
        })
        
        target_date = node._get_target_date_for_orb(symbol, today_date, mock_df)
        assert target_date == last_trading_day

    def test_get_target_date_for_orb_crypto(self):
        """Test that crypto uses UTC midnight of prior day"""
        node = OrbFilter(id=1, params={"or_minutes": 5, "rel_vol_threshold": 100.0, "direction": "both", "avg_period": 14})
        symbol = AssetSymbol("BTC", AssetClass.CRYPTO)
        today_date = datetime.now(pytz.timezone('US/Eastern')).date()
        
        # Mock DataFrame (not used for crypto logic)
        mock_df = pd.DataFrame({'date': []})
        
        target_date = node._get_target_date_for_orb(symbol, today_date, mock_df)
        
        # Should be UTC prior day
        utc_now = datetime.now(pytz.timezone('UTC'))
        expected_date = utc_now.date() - timedelta(days=1)
        assert target_date == expected_date

    def test_crypto_opening_range_time_calculation(self):
        """Test that crypto ORB calculates opening range time correctly"""
        node = OrbFilter(id=1, params={"or_minutes": 5, "rel_vol_threshold": 100.0, "direction": "both", "avg_period": 14})
        symbol = AssetSymbol("BTC", AssetClass.CRYPTO)
        
        # Test date
        test_date = datetime.now(pytz.timezone('US/Eastern')).date()
        
        # Mock DataFrame with some data
        mock_df = pd.DataFrame({
            'date': [test_date],
            'timestamp': [datetime.now(pytz.timezone('US/Eastern'))]
        })
        
        # Test that crypto uses UTC midnight logic
        target_date = node._get_target_date_for_orb(symbol, test_date, mock_df)
        
        # Should be UTC prior day
        utc_now = datetime.now(pytz.timezone('UTC'))
        expected_date = utc_now.date() - timedelta(days=1)
        assert target_date == expected_date

    @pytest.mark.asyncio
    @patch('nodes.core.market.filters.orb_filter_node.APIKeyVault')
    @patch('nodes.core.market.filters.orb_filter_node.fetch_bars')
    async def test_calculate_orb_indicator_stocks_last_trading_day(self, mock_fetch_bars, mock_vault, orb_node):
        """Test that stocks ORB uses last trading day when today has no data"""
        # Mock API key
        mock_vault.return_value.get.return_value = "fake_api_key"
        
        symbol = AssetSymbol("AAPL", AssetClass.STOCKS)
        
        # Mock bars data for multiple trading days (no today data)
        today = datetime.now(pytz.timezone('US/Eastern')).date()
        mock_bars = []
        
        # Create bars for 15 days to satisfy avg_period=14 requirement
        for day_offset in range(15):
            date = today - timedelta(days=15 - day_offset)  # Start from 15 days ago
            
            # Create mock bars for 9:30 AM EST opening range
            est_open_time = datetime.combine(date, datetime.strptime('09:30', '%H:%M').time()).replace(tzinfo=pytz.timezone('US/Eastern'))
            est_open_time_ms = int(est_open_time.timestamp() * 1000)
            
            # Add 5 minutes of bars for opening range
            for minute in range(5):
                mock_bars.append({
                    "timestamp": est_open_time_ms + (minute * 60000),
                    "open": 100.0 + day_offset * 0.1,
                    "high": 105.0 + day_offset * 0.1,
                    "low": 95.0 + day_offset * 0.1,
                    "close": 102.0 + day_offset * 0.1,
                    "volume": 50000 if day_offset == 14 else 30000  # Higher volume on last day
                })
        
        mock_fetch_bars.return_value = mock_bars

        result = await orb_node._calculate_orb_indicator(symbol, "fake_api_key")

        assert result.indicator_type == IndicatorType.ORB
        assert result.error is None
        assert "rel_vol" in result.values.lines
        assert result.values.series[0]["direction"] in ["bullish", "bearish", "doji"]

