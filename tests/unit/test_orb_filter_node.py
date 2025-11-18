import asyncio
import time
from datetime import datetime, timedelta
from typing import Any
from unittest.mock import Mock, patch

import pandas as pd
import pytest
import pytz

from core.types_registry import (
    AssetClass,
    AssetSymbol,
    IndicatorResult,
    IndicatorType,
    IndicatorValue,
    NodeExecutionError,
    OHLCVBar,
)
from nodes.core.market.filters.orb_filter_node import OrbFilter, RateLimiter


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
def empty_ohlcv() -> list[dict[str, int]]:
    return []


@pytest.fixture
def sample_ohlcv() -> list[dict[str, int]]:
    return [
        {
            "timestamp": 1234567890000,
            "open": 100,
            "high": 110,
            "low": 90,
            "close": 105,
            "volume": 1000,
        }
    ]


@pytest.fixture
def mock_symbol():
    return AssetSymbol("AAPL", AssetClass.STOCKS)


@pytest.fixture
def mock_ohlcv_bundle(mock_symbol: AssetSymbol) -> dict[AssetSymbol, list[OHLCVBar]]:
    return {
        mock_symbol: [
            OHLCVBar(
                timestamp=1234567890, open=100.0, high=105.0, low=95.0, close=102.0, volume=1000000
            )
        ]
    }


@pytest.fixture
def orb_node():
    params = {
        "or_minutes": 5,
        "rel_vol_threshold": 100.0,
        "direction": "both",
        "avg_period": 14,
        "max_concurrent": 10,
        "rate_limit_per_second": 95,
    }
    return OrbFilter(id=1, params=params)


@pytest.fixture
def sample_symbols():
    return [
        AssetSymbol("AAPL", AssetClass.STOCKS),
        AssetSymbol("MSFT", AssetClass.STOCKS),
        AssetSymbol("GOOGL", AssetClass.STOCKS),
    ]


@pytest.fixture
def mock_ohlcv_bundle_extended(
    sample_symbols: list[AssetSymbol],
) -> dict[AssetSymbol, list[OHLCVBar]]:
    return {
        symbol: [
            OHLCVBar(
                timestamp=1234567890, open=100.0, high=105.0, low=95.0, close=102.0, volume=1000000
            )
        ]
        for symbol in sample_symbols
    }


class TestRateLimiter:
    """Tests for the RateLimiter class."""

    @pytest.fixture
    def rate_limiter(self) -> RateLimiter:
        return RateLimiter(max_per_second=10)

    @pytest.mark.asyncio
    async def test_rate_limiter_basic(self, rate_limiter: RateLimiter) -> None:
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
    async def test_rate_limiter_cleanup_old_requests(self, rate_limiter: RateLimiter) -> None:
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
    async def test_rate_limiter_concurrent_access(self, rate_limiter: RateLimiter) -> None:
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

    def test_rate_limiter_initialization(self) -> None:
        """Test RateLimiter initialization."""
        limiter = RateLimiter(max_per_second=50)
        assert limiter.max_per_second == 50
        assert limiter.requests == []
        assert isinstance(limiter.lock, asyncio.Lock)


class TestOrbFilter:
    @pytest.mark.asyncio
    @patch("nodes.core.market.filters.orb_filter_node.APIKeyVault")
    @patch("nodes.core.market.filters.orb_filter_node.fetch_bars")
    async def test_calculate_orb_indicator_success(
        self, mock_fetch_bars: Mock, mock_vault: Mock, orb_node: OrbFilter, mock_symbol: AssetSymbol
    ) -> None:
        # Mock API key
        mock_vault.return_value.get.return_value = "fake_api_key"

        # Mock bars data for multiple days to avoid insufficient days
        # Using 5-minute bars instead of 1-minute bars
        today = datetime.now(pytz.timezone("US/Eastern")).date()
        mock_bars: list[dict[str, Any]] = []
        for day_offset in range(15):  # Enough for avg_period=14
            date = today - timedelta(days=14 - day_offset)
            open_time_eastern = datetime.combine(
                date, datetime.strptime("09:30", "%H:%M").time()
            ).replace(tzinfo=pytz.timezone("US/Eastern"))
            open_time_utc = open_time_eastern.astimezone(pytz.utc)
            day_start = int(open_time_utc.timestamp() * 1000)
            is_last_day = day_offset == 14
            # Add single 5-minute bar for opening range
            mock_bars.append(
                {
                    "timestamp": day_start,
                    "open": 100.0 + day_offset * 0.1,
                    "high": 105.0 + day_offset * 0.1,
                    "low": 95.0 + day_offset * 0.1,
                    "close": 102.0 + day_offset * 0.1,
                    "volume": 50000 if is_last_day else 30000,  # Higher volume on last day
                }
            )
        mock_fetch_bars.return_value = mock_bars

        result: IndicatorResult = await orb_node._calculate_orb_indicator(
            mock_symbol, "fake_api_key"
        )  # pyright: ignore[reportPrivateUsage]

        assert result.indicator_type == IndicatorType.ORB
        assert result.error is None
        assert "rel_vol" in result.values.lines
        assert result.values.series[0]["direction"] in ["bullish", "bearish", "doji"]

    @pytest.mark.asyncio
    async def test_execute_empty_ohlcv_bundle(self, orb_node: OrbFilter) -> None:
        """Test execution with empty OHLCV bundle."""
        with patch("core.api_key_vault.APIKeyVault.get", return_value="test_key"):
            result = await orb_node.execute({"ohlcv_bundle": {}})
        assert result == {"filtered_ohlcv_bundle": {}}

    @pytest.mark.asyncio
    async def test_execute_missing_api_key(
        self, orb_node: OrbFilter, mock_ohlcv_bundle_extended: dict[AssetSymbol, list[OHLCVBar]]
    ) -> None:
        """Test error when API key is not found in vault."""
        with patch("core.api_key_vault.APIKeyVault.get", return_value=None):
            with pytest.raises(NodeExecutionError) as exc_info:
                await orb_node.execute({"ohlcv_bundle": mock_ohlcv_bundle_extended})
            assert isinstance(exc_info.value.original_exc, ValueError)
            assert str(exc_info.value.original_exc) == "Polygon API key not found in vault"

    @pytest.mark.asyncio
    async def test_execute_successful_concurrent_filtering(
        self, orb_node: OrbFilter, mock_ohlcv_bundle_extended: dict[AssetSymbol, list[OHLCVBar]]
    ) -> None:
        """Test successful concurrent filtering of multiple symbols."""

        async def mock_calc(symbol: AssetSymbol, api_key: str) -> IndicatorResult:
            # Return passing result for all symbols
            return IndicatorResult(
                indicator_type=IndicatorType.ORB,
                timestamp=1234567890000,
                values=IndicatorValue(lines={"rel_vol": 150.0}, series=[{"direction": "bullish"}]),
                params=orb_node.params,
            )

        orb_node._calculate_orb_indicator = mock_calc

        with patch("core.api_key_vault.APIKeyVault.get", return_value="test_key"):
            result: dict[str, dict[AssetSymbol, list[OHLCVBar]]] = await orb_node.execute(
                {"ohlcv_bundle": mock_ohlcv_bundle_extended}
            )

        assert "filtered_ohlcv_bundle" in result
        bundle: dict[AssetSymbol, list[OHLCVBar]] = result["filtered_ohlcv_bundle"]
        assert isinstance(bundle, dict)
        assert len(bundle) == 3  # All symbols should pass filter

        for symbol in mock_ohlcv_bundle_extended.keys():
            assert symbol in bundle
            assert bundle[symbol] == mock_ohlcv_bundle_extended[symbol]

    @pytest.mark.asyncio
    async def test_execute_partial_failures(
        self, orb_node: OrbFilter, mock_ohlcv_bundle_extended: dict[AssetSymbol, list[OHLCVBar]]
    ) -> None:
        """Test handling of partial failures in concurrent filtering."""
        call_count = 0

        async def mock_calc_with_failure(symbol: AssetSymbol, api_key: str) -> IndicatorResult:
            nonlocal call_count
            call_count += 1
            if symbol.ticker == "MSFT":
                raise Exception("API rate limit exceeded")
            return IndicatorResult(
                indicator_type=IndicatorType.ORB,
                timestamp=1234567890000,
                values=IndicatorValue(lines={"rel_vol": 150.0}, series=[{"direction": "bullish"}]),
                params=orb_node.params,
            )

        orb_node._calculate_orb_indicator = mock_calc_with_failure

        with patch("core.api_key_vault.APIKeyVault.get", return_value="test_key"):
            result: dict[str, dict[AssetSymbol, list[OHLCVBar]]] = await orb_node.execute(
                {"ohlcv_bundle": mock_ohlcv_bundle_extended}
            )

        bundle: dict[AssetSymbol, list[OHLCVBar]] = result["filtered_ohlcv_bundle"]
        # AAPL and GOOGL should succeed, MSFT should be missing due to error
        assert len(bundle) == 2
        symbols = list(mock_ohlcv_bundle_extended.keys())
        assert symbols[0] in bundle  # AAPL
        assert symbols[1] not in bundle  # MSFT (failed)
        assert symbols[2] in bundle  # GOOGL

    @pytest.mark.asyncio
    async def test_execute_no_symbol_limit(self, orb_node: OrbFilter) -> None:
        """Test that there are no symbol limits."""
        # Create 60 symbols - should process all of them
        symbols: list[AssetSymbol] = [
            AssetSymbol(f"SYMBOL_{_}", AssetClass.STOCKS) for _ in range(60)
        ]
        ohlcv_bundle = {
            symbol: [
                OHLCVBar(
                    timestamp=1234567890,
                    open=100.0,
                    high=105.0,
                    low=95.0,
                    close=102.0,
                    volume=1000000,
                )
            ]
            for symbol in symbols
        }

        async def mock_calc(symbol: AssetSymbol, api_key: str) -> IndicatorResult:
            return IndicatorResult(
                indicator_type=IndicatorType.ORB,
                timestamp=1234567890000,
                values=IndicatorValue(lines={"rel_vol": 150.0}, series=[{"direction": "bullish"}]),
                params=orb_node.params,
            )

        orb_node._calculate_orb_indicator = mock_calc

        with patch("core.api_key_vault.APIKeyVault.get", return_value="test_key"):
            result: dict[str, dict[AssetSymbol, list[OHLCVBar]]] = await orb_node.execute(
                {"ohlcv_bundle": ohlcv_bundle}
            )

        # Should process all 60 symbols
        bundle: dict[AssetSymbol, list[OHLCVBar]] = result["filtered_ohlcv_bundle"]
        assert len(bundle) == 60

    @pytest.mark.asyncio
    async def test_execute_concurrency_control(self, orb_node: OrbFilter) -> None:
        """Test concurrency limiting."""
        # Create many symbols to test concurrency
        symbols: list[AssetSymbol] = [
            AssetSymbol(f"SYMBOL_{_}", AssetClass.STOCKS) for _ in range(20)
        ]
        ohlcv_bundle = {
            symbol: [
                OHLCVBar(
                    timestamp=1234567890,
                    open=100.0,
                    high=105.0,
                    low=95.0,
                    close=102.0,
                    volume=1000000,
                )
            ]
            for symbol in symbols
        }

        async def slow_calc(symbol: AssetSymbol, api_key: str) -> IndicatorResult:
            # Make calculation take some time to test concurrency
            await asyncio.sleep(0.01)
            return IndicatorResult(
                indicator_type=IndicatorType.ORB,
                timestamp=1234567890000,
                values=IndicatorValue(lines={"rel_vol": 150.0}, series=[{"direction": "bullish"}]),
                params=orb_node.params,
            )

        orb_node._calculate_orb_indicator = slow_calc

        start_time = time.time()
        with patch("core.api_key_vault.APIKeyVault.get", return_value="test_key"):
            result: dict[str, dict[AssetSymbol, list[OHLCVBar]]] = await orb_node.execute(
                {"ohlcv_bundle": ohlcv_bundle}
            )
        elapsed = time.time() - start_time

        # With max_concurrent=5, should take longer than if all ran in parallel
        # but faster than if they ran sequentially
        assert elapsed >= 0.04  # At least 4 batches of 5 concurrent requests

        assert len(result["filtered_ohlcv_bundle"]) == 20

    @pytest.mark.asyncio
    async def test_execute_rate_limiting(self, orb_node: OrbFilter) -> None:
        """Test rate limiting functionality."""
        symbols = [AssetSymbol(f"SYMBOL_{_}", AssetClass.STOCKS) for _ in range(20)]
        ohlcv_bundle = {
            symbol: [
                OHLCVBar(
                    timestamp=1234567890,
                    open=100.0,
                    high=105.0,
                    low=95.0,
                    close=102.0,
                    volume=1000000,
                )
            ]
            for symbol in symbols
        }

        async def rate_limited_calc(symbol: AssetSymbol, api_key: str) -> IndicatorResult:
            # Simulate some processing time and rate limiting
            await asyncio.sleep(0.01)
            return IndicatorResult(
                indicator_type=IndicatorType.ORB,
                timestamp=1234567890000,
                values=IndicatorValue(lines={"rel_vol": 150.0}, series=[{"direction": "bullish"}]),
                params=orb_node.params,
            )

        orb_node._calculate_orb_indicator = rate_limited_calc

        start_time = time.time()
        with patch("core.api_key_vault.APIKeyVault.get", return_value="test_key"):
            result: dict[str, dict[AssetSymbol, list[OHLCVBar]]] = await orb_node.execute(
                {"ohlcv_bundle": ohlcv_bundle}
            )
        elapsed = time.time() - start_time

        # With rate limiting and concurrency control, should take some time
        assert (
            elapsed >= 0.03
        )  # Should take at least some time due to concurrency and simulated calc time
        assert len(result["filtered_ohlcv_bundle"]) == 20

    @patch("nodes.core.market.filters.orb_filter_node.APIKeyVault")
    def test_should_pass_filter_bullish_high_vol(
        self, mock_vault: Mock, orb_node: OrbFilter
    ) -> None:
        # Mock passing result
        mock_result = IndicatorResult(
            indicator_type=IndicatorType.ORB,
            values=IndicatorValue(lines={"rel_vol": 150.0}, series=[{"direction": "bullish"}]),
            params=orb_node.params,
        )
        assert orb_node._should_pass_filter(mock_result) is True  # pyright: ignore[reportPrivateUsage]

    @patch("nodes.core.market.filters.orb_filter_node.APIKeyVault")
    def test_should_pass_filter_bearish_high_vol(
        self, mock_vault: Mock, orb_node: OrbFilter
    ) -> None:
        # Mock passing result
        mock_result = IndicatorResult(
            indicator_type=IndicatorType.ORB,
            values=IndicatorValue(lines={"rel_vol": 150.0}, series=[{"direction": "bearish"}]),
            params=orb_node.params,
        )
        assert orb_node._should_pass_filter(mock_result) is True  # pyright: ignore[reportPrivateUsage]

    @patch("nodes.core.market.filters.orb_filter_node.APIKeyVault")
    def test_should_pass_filter_low_vol(self, mock_vault: Mock, orb_node: OrbFilter) -> None:
        # Mock failing result - low volume
        mock_result = IndicatorResult(
            indicator_type=IndicatorType.ORB,
            values=IndicatorValue(lines={"rel_vol": 50.0}, series=[{"direction": "bullish"}]),
            params=orb_node.params,
        )
        assert orb_node._should_pass_filter(mock_result) is False

    @patch("nodes.core.market.filters.orb_filter_node.APIKeyVault")
    def test_should_pass_filter_doji(self, mock_vault: Mock, orb_node: OrbFilter) -> None:
        # Mock doji
        mock_result = IndicatorResult(
            indicator_type=IndicatorType.ORB,
            values=IndicatorValue(lines={"rel_vol": 150.0}, series=[{"direction": "doji"}]),
            params=orb_node.params,
        )
        assert orb_node._should_pass_filter(mock_result) is False

    @pytest.mark.asyncio
    @patch("nodes.core.market.filters.orb_filter_node.APIKeyVault")
    @patch("nodes.core.market.filters.orb_filter_node.fetch_bars")
    async def test_execute_no_data(
        self, mock_fetch_bars: Mock, mock_vault: Mock, orb_node: OrbFilter
    ) -> None:
        mock_vault.return_value.get.return_value = "fake_api_key"
        mock_fetch_bars.return_value = []

        result = await orb_node.execute({"ohlcv_bundle": {}})

        assert result["filtered_ohlcv_bundle"] == {}

    @pytest.mark.asyncio
    @patch("nodes.core.market.filters.orb_filter_node.APIKeyVault")
    @patch("nodes.core.market.filters.orb_filter_node.fetch_bars")
    async def test_execute_error(
        self,
        mock_fetch_bars: Mock,
        mock_vault: Mock,
        orb_node: OrbFilter,
        mock_ohlcv_bundle: dict[AssetSymbol, list[OHLCVBar]],
        mock_symbol: AssetSymbol,
    ) -> None:
        mock_vault.return_value.get.return_value = "fake_api_key"
        mock_fetch_bars.side_effect = Exception("API error")

        result = await orb_node.execute({"ohlcv_bundle": {mock_symbol: []}})

        assert mock_symbol not in result["filtered_ohlcv_bundle"]

    @pytest.mark.asyncio
    async def test_execute_cancellation_during_calculation(
        self, orb_node: OrbFilter, mock_ohlcv_bundle_extended: dict[AssetSymbol, list[OHLCVBar]]
    ) -> None:
        """Test handling of cancellation during ORB calculation."""

        async def slow_calc(symbol: AssetSymbol, api_key: str) -> IndicatorResult:
            await asyncio.sleep(1.0)  # Simulate long calculation
            return IndicatorResult(
                indicator_type=IndicatorType.ORB,
                timestamp=1234567890000,
                values=IndicatorValue(lines={"rel_vol": 150.0}, series=[{"direction": "bullish"}]),
                params=orb_node.params,
            )

        orb_node._calculate_orb_indicator = slow_calc

        with patch("core.api_key_vault.APIKeyVault.get", return_value="test_key"):
            execute_task = asyncio.create_task(
                orb_node.execute({"ohlcv_bundle": mock_ohlcv_bundle_extended})
            )

            await asyncio.sleep(0.1)  # Let it start
            execute_task.cancel()

            with pytest.raises(asyncio.CancelledError):
                await execute_task

    @pytest.mark.asyncio
    async def test_force_stop_cancels_workers(
        self, orb_node: OrbFilter, mock_ohlcv_bundle_extended: dict[AssetSymbol, list[OHLCVBar]]
    ) -> None:
        """Test that force_stop cancels internal workers."""

        async def slow_calc(symbol: AssetSymbol, api_key: str) -> IndicatorResult:
            await asyncio.sleep(0.5)  # Simulate ongoing calculation
            return IndicatorResult(
                indicator_type=IndicatorType.ORB,
                timestamp=1234567890000,
                values=IndicatorValue(lines={"rel_vol": 150.0}, series=[{"direction": "bullish"}]),
                params=orb_node.params,
            )

        orb_node._calculate_orb_indicator = slow_calc

        with patch("core.api_key_vault.APIKeyVault.get", return_value="test_key"):
            execute_task = asyncio.create_task(
                orb_node.execute({"ohlcv_bundle": mock_ohlcv_bundle_extended})
            )

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
    async def test_force_stop_idempotent(self, orb_node: OrbFilter) -> None:
        """Test that force_stop is idempotent."""
        # Call force_stop multiple times
        orb_node.force_stop()
        orb_node.force_stop()
        orb_node.force_stop()

        # Should not raise any errors and be in stopped state
        assert orb_node._is_stopped is True

    @pytest.mark.asyncio
    async def test_progress_reporting_during_execution(
        self, orb_node: OrbFilter, mock_ohlcv_bundle_extended: dict[AssetSymbol, list[OHLCVBar]]
    ) -> None:
        """Test that progress is reported during execution."""
        progress_calls = []

        def mock_report(progress, text):
            progress_calls.append((progress, text))

        orb_node.report_progress = mock_report

        async def slow_calc(symbol: AssetSymbol, api_key: str) -> IndicatorResult:
            await asyncio.sleep(0.01)  # Brief delay to ensure progress reporting
            return IndicatorResult(
                indicator_type=IndicatorType.ORB,
                timestamp=1234567890000,
                values=IndicatorValue(lines={"rel_vol": 150.0}, series=[{"direction": "bullish"}]),
                params=orb_node.params,
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
    inputs = {"ohlcv_bundle": {AssetSymbol("AAPL", AssetClass.STOCKS): sample_ohlcv}}

    # Mock the calculation to return passing result
    async def mock_calc(symbol, api_key):
        return IndicatorResult(
            indicator_type=IndicatorType.ORB,
            timestamp=1234567890000,
            values=IndicatorValue(lines={"rel_vol": 150.0}, series=[{"direction": "bullish"}]),
            params=sample_params,
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
            error="Insufficient days",
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
            params=sample_params,
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
            params=sample_params,
        )

    node._calculate_orb_indicator = mock_calc

    with patch("core.api_key_vault.APIKeyVault.get", return_value="test_key"):
        result = await node.execute(inputs)
    assert result["filtered_ohlcv_bundle"] == {}


@pytest.mark.asyncio
@patch("nodes.core.market.filters.orb_filter_node.fetch_bars")
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
    assert (
        AssetSymbol("AAPL", AssetClass.STOCKS) not in result["filtered_ohlcv_bundle"]
    )  # Empty data skipped


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
            params=params,
        )

    async def mock_calc_bearish(symbol, api_key):
        return IndicatorResult(
            indicator_type=IndicatorType.ORB,
            timestamp=1234567890000,
            values=IndicatorValue(lines={"rel_vol": 150.0}, series=[{"direction": "bearish"}]),
            params=params,
        )

    node._calculate_orb_indicator = mock_calc_bullish
    with patch("core.api_key_vault.APIKeyVault.get", return_value="test_key"):
        result = await node.execute(inputs)

    assert (
        AssetSymbol("AAPL", AssetClass.STOCKS) in result["filtered_ohlcv_bundle"]
    )  # Passes for bullish

    # Test bearish
    params["direction"] = "bearish"
    node = OrbFilter(id=1, params=params)  # Re-instantiate with bearish
    node._calculate_orb_indicator = mock_calc_bearish
    with patch("core.api_key_vault.APIKeyVault.get", return_value="test_key"):
        result = await node.execute(inputs)
    assert (
        AssetSymbol("AAPL", AssetClass.STOCKS) in result["filtered_ohlcv_bundle"]
    )  # Passes for bearish

    # Test both
    params["direction"] = "both"
    node = OrbFilter(id=1, params=params)
    node._calculate_orb_indicator = mock_calc_bullish  # Using bullish for variety, but either works
    with patch("core.api_key_vault.APIKeyVault.get", return_value="test_key"):
        result = await node.execute(inputs)
    assert (
        AssetSymbol("AAPL", AssetClass.STOCKS) in result["filtered_ohlcv_bundle"]
    )  # Passes for both


class TestOrbFilterAssetClassLogic:
    """Test asset class specific logic for ORB filter"""

    def test_get_target_date_for_orb_stocks_with_today_data(self):
        """Test that stocks use today's date when data is available"""
        node = OrbFilter(
            id=1,
            params={
                "or_minutes": 5,
                "rel_vol_threshold": 100.0,
                "direction": "both",
                "avg_period": 14,
            },
        )
        symbol = AssetSymbol("AAPL", AssetClass.STOCKS)
        today_date = datetime.now(pytz.timezone("US/Eastern")).date()

        # Mock DataFrame with today's data
        mock_df = pd.DataFrame({"date": [today_date, today_date - timedelta(days=1)]})

        target_date = node._get_target_date_for_orb(symbol, today_date, mock_df)
        assert target_date == today_date

    def test_get_target_date_for_orb_stocks_without_today_data(self):
        """Test that stocks use last trading day when today has no data"""
        node = OrbFilter(
            id=1,
            params={
                "or_minutes": 5,
                "rel_vol_threshold": 100.0,
                "direction": "both",
                "avg_period": 14,
            },
        )
        symbol = AssetSymbol("AAPL", AssetClass.STOCKS)
        today_date = datetime.now(pytz.timezone("US/Eastern")).date()
        last_trading_day = today_date - timedelta(days=1)

        # Mock DataFrame without today's data
        mock_df = pd.DataFrame({"date": [last_trading_day, last_trading_day - timedelta(days=1)]})

        target_date = node._get_target_date_for_orb(symbol, today_date, mock_df)
        assert target_date == last_trading_day

    def test_get_target_date_for_orb_crypto(self):
        """Test that crypto uses UTC midnight of prior day"""
        node = OrbFilter(
            id=1,
            params={
                "or_minutes": 5,
                "rel_vol_threshold": 100.0,
                "direction": "both",
                "avg_period": 14,
            },
        )
        symbol = AssetSymbol("BTC", AssetClass.CRYPTO)
        today_date = datetime.now(pytz.timezone("US/Eastern")).date()

        # Mock DataFrame (not used for crypto logic)
        mock_df = pd.DataFrame({"date": []})

        target_date = node._get_target_date_for_orb(symbol, today_date, mock_df)

        # Should be UTC prior day
        utc_now = datetime.now(pytz.timezone("UTC"))
        expected_date = utc_now.date() - timedelta(days=1)
        assert target_date == expected_date

    def test_crypto_opening_range_time_calculation(self):
        """Test that crypto ORB calculates opening range time correctly"""
        node = OrbFilter(
            id=1,
            params={
                "or_minutes": 5,
                "rel_vol_threshold": 100.0,
                "direction": "both",
                "avg_period": 14,
            },
        )
        symbol = AssetSymbol("BTC", AssetClass.CRYPTO)

        # Test date
        test_date = datetime.now(pytz.timezone("US/Eastern")).date()

        # Mock DataFrame with some data
        mock_df = pd.DataFrame(
            {"date": [test_date], "timestamp": [datetime.now(pytz.timezone("US/Eastern"))]}
        )

        # Test that crypto uses UTC midnight logic
        target_date = node._get_target_date_for_orb(symbol, test_date, mock_df)

        # Should be UTC prior day
        utc_now = datetime.now(pytz.timezone("UTC"))
        expected_date = utc_now.date() - timedelta(days=1)
        assert target_date == expected_date

    @pytest.mark.asyncio
    @patch("nodes.core.market.filters.orb_filter_node.APIKeyVault")
    @patch("nodes.core.market.filters.orb_filter_node.fetch_bars")
    async def test_calculate_orb_indicator_stocks_last_trading_day(
        self, mock_fetch_bars: Mock, mock_vault: Mock, orb_node: OrbFilter
    ) -> None:
        """Test that stocks ORB uses last trading day when today has no data"""
        # Mock API key
        mock_vault.return_value.get.return_value = "fake_api_key"

        symbol = AssetSymbol("AAPL", AssetClass.STOCKS)

        # Mock bars data for multiple trading days (no today data)
        today = datetime.now(pytz.timezone("US/Eastern")).date()
        mock_bars: list[dict[str, Any]] = []

        # Create bars for 15 days to satisfy avg_period=14 requirement
        for day_offset in range(15):
            date = today - timedelta(days=15 - day_offset)  # Start from 15 days ago

            # Create mock bars for 9:30 AM EST opening range
            est_open_time = datetime.combine(
                date, datetime.strptime("09:30", "%H:%M").time()
            ).replace(tzinfo=pytz.timezone("US/Eastern"))
            est_open_time_ms = int(est_open_time.timestamp() * 1000)

            # Add single 5-minute bar for opening range
            mock_bars.append(
                {
                    "timestamp": est_open_time_ms,
                    "open": 100.0 + day_offset * 0.1,
                    "high": 105.0 + day_offset * 0.1,
                    "low": 95.0 + day_offset * 0.1,
                    "close": 102.0 + day_offset * 0.1,
                    "volume": 50000 if day_offset == 14 else 30000,  # Higher volume on last day
                }
            )

        mock_fetch_bars.return_value = mock_bars

        result = await orb_node._calculate_orb_indicator(symbol, "fake_api_key")  # pyright: ignore[reportPrivateUsage]

        assert result.indicator_type == IndicatorType.ORB
        assert result.error is None
        assert "rel_vol" in result.values.lines
        assert result.values.series[0]["direction"] in ["bullish", "bearish", "doji"]

    @pytest.mark.asyncio
    async def test_orb_during_hours_partial_data_fallback(self, orb_node, mock_symbol):
        """Test fallback to prior day when partial OR data available during market hours."""
        # Simulate run time: 9:35 AM ET on test day
        now_eastern = datetime(2023, 10, 1, 9, 35, tzinfo=pytz.timezone("US/Eastern"))

        def mock_now_func(tz=None):
            if tz is None:
                return now_eastern
            return now_eastern.astimezone(tz)

        # Mock bars: Using 5-minute bars
        today_start_ms = int(
            datetime(2023, 10, 1, 9, 30, tzinfo=pytz.timezone("US/Eastern")).timestamp() * 1000
        )
        prior_start_ms = int(
            datetime(2023, 9, 30, 9, 30, tzinfo=pytz.timezone("US/Eastern")).timestamp() * 1000
        )
        prior2_start_ms = int(
            datetime(2023, 9, 29, 9, 30, tzinfo=pytz.timezone("US/Eastern")).timestamp() * 1000
        )

        mock_bars = [
            # Prior2 day: Single 5-minute bar (bullish OR)
            {
                "timestamp": prior2_start_ms,
                "open": 100,
                "high": 105,
                "low": 95,
                "close": 103,
                "volume": 5000,
            },
            # Prior day: Single 5-minute bar (bearish OR)
            {
                "timestamp": prior_start_ms,
                "open": 105,
                "high": 105.5,
                "low": 103.5,
                "close": 104,
                "volume": 5000,
            },
            # Today: Single 5-minute bar (bullish OR)
            {
                "timestamp": today_start_ms,
                "open": 110,
                "high": 115,
                "low": 109,
                "close": 113,
                "volume": 10000,
            },
        ]

        with patch("nodes.core.market.filters.orb_filter_node.fetch_bars", return_value=mock_bars):
            with patch("core.api_key_vault.APIKeyVault.get", return_value="fake_key"):
                with patch("nodes.core.market.filters.orb_filter_node.calculate_orb") as mock_calc:
                    from services.indicator_calculators.orb_calculator import (
                        calculate_orb as real_calc,
                    )

                    # Call the real calculator with our mock now_func
                    def calc_wrapper(bars, symbol, or_minutes, avg_period):
                        return real_calc(
                            bars, symbol, or_minutes, avg_period, now_func=mock_now_func
                        )

                    mock_calc.side_effect = calc_wrapper
                    result = await orb_node._calculate_orb_indicator(mock_symbol, "fake_key")

        assert result.values.lines["rel_vol"] == 100
        assert result.values.series[0]["direction"] == "bearish"

    @pytest.mark.asyncio
    async def test_orb_after_hours_complete_data(self, orb_node, mock_symbol):
        """Test using today's complete data when run after market hours."""
        # Simulate run time: 5:00 PM ET on test day
        now_eastern = datetime(2023, 10, 1, 17, 0, tzinfo=pytz.timezone("US/Eastern"))

        def mock_now_func(tz=None):
            if tz is None:
                return now_eastern
            return now_eastern.astimezone(tz)

        # Mock bars: Complete today (single 5-minute bar)
        today_start_ms = int(
            datetime(2023, 10, 1, 9, 30, tzinfo=pytz.timezone("US/Eastern")).timestamp() * 1000
        )

        mock_bars = [
            {
                "timestamp": today_start_ms,
                "open": 100,
                "high": 105,
                "low": 95,
                "close": 103,
                "volume": 5000,
            },
        ]

        with patch("nodes.core.market.filters.orb_filter_node.fetch_bars", return_value=mock_bars):
            with patch("core.api_key_vault.APIKeyVault.get", return_value="fake_key"):
                with patch("nodes.core.market.filters.orb_filter_node.calculate_orb") as mock_calc:
                    from services.indicator_calculators.orb_calculator import (
                        calculate_orb as real_calc,
                    )

                    # Call the real calculator with our mock now_func
                    def calc_wrapper(bars, symbol, or_minutes, avg_period):
                        return real_calc(
                            bars, symbol, or_minutes, avg_period, now_func=mock_now_func
                        )

                    mock_calc.side_effect = calc_wrapper
                    result = await orb_node._calculate_orb_indicator(mock_symbol, "fake_key")

        # Should use today's data, direction bullish (close > open overall)
        assert result.values.series[0]["direction"] == "bullish"


class TestOrbFilterEdgeCases:
    """Comprehensive edge case tests for ORB filter robustness."""

    @pytest.fixture
    def edge_case_params(self):
        return {
            "or_minutes": 5,
            "rel_vol_threshold": 100.0,
            "direction": "both",
            "avg_period": 14,
            "max_concurrent": 10,
            "rate_limit_per_second": 95,
        }

    @pytest.fixture
    def edge_case_node(self, edge_case_params):
        return OrbFilter(id=1, params=edge_case_params)

    @pytest.mark.asyncio
    async def test_decimal_avg_period_lookback_fix(self, edge_case_node):
        """Test that decimal avg_period values are properly converted to integers for lookback."""
        # Set a decimal avg_period that would cause the original bug
        edge_case_node.params["avg_period"] = 7.780725097656255

        async def mock_calc(symbol, api_key):
            # Verify the lookback_period is properly formatted
            return IndicatorResult(
                indicator_type=IndicatorType.ORB,
                timestamp=1234567890000,
                values=IndicatorValue(lines={"rel_vol": 150.0}, series=[{"direction": "bullish"}]),
                params=edge_case_node.params,
            )

        edge_case_node._calculate_orb_indicator = mock_calc

        with patch("core.api_key_vault.APIKeyVault.get", return_value="test_key"):
            # This should not raise an error about decimal lookback period
            result = await edge_case_node.execute(
                {
                    "ohlcv_bundle": {
                        AssetSymbol("AAPL", AssetClass.STOCKS): [
                            OHLCVBar(
                                timestamp=1234567890,
                                open=100.0,
                                high=105.0,
                                low=95.0,
                                close=102.0,
                                volume=1000000,
                            )
                        ]
                    }
                }
            )

        assert "filtered_ohlcv_bundle" in result

    @pytest.mark.asyncio
    async def test_zero_avg_period_edge_case(self, edge_case_node):
        """Test handling of zero avg_period (should be caught by validation)."""
        edge_case_node.params["avg_period"] = 0

        with pytest.raises(ValueError, match="Average period must be positive"):
            edge_case_node._validate_indicator_params()

    @pytest.mark.asyncio
    async def test_negative_avg_period_edge_case(self, edge_case_node):
        """Test handling of negative avg_period."""
        edge_case_node.params["avg_period"] = -5

        with pytest.raises(ValueError, match="Average period must be positive"):
            edge_case_node._validate_indicator_params()

    @pytest.mark.asyncio
    async def test_very_large_avg_period(self, edge_case_node):
        """Test handling of very large avg_period values."""
        edge_case_node.params["avg_period"] = 1000

        async def mock_calc(symbol, api_key):
            return IndicatorResult(
                indicator_type=IndicatorType.ORB,
                timestamp=1234567890000,
                values=IndicatorValue(lines={"rel_vol": 150.0}, series=[{"direction": "bullish"}]),
                params=edge_case_node.params,
            )

        edge_case_node._calculate_orb_indicator = mock_calc

        with patch("core.api_key_vault.APIKeyVault.get", return_value="test_key"):
            result = await edge_case_node.execute(
                {
                    "ohlcv_bundle": {
                        AssetSymbol("AAPL", AssetClass.STOCKS): [
                            OHLCVBar(
                                timestamp=1234567890,
                                open=100.0,
                                high=105.0,
                                low=95.0,
                                close=102.0,
                                volume=1000000,
                            )
                        ]
                    }
                }
            )

        assert "filtered_ohlcv_bundle" in result

    @pytest.mark.asyncio
    async def test_zero_or_minutes_edge_case(self, edge_case_node):
        """Test handling of zero or_minutes."""
        edge_case_node.params["or_minutes"] = 0

        with pytest.raises(ValueError, match="Opening range minutes must be positive"):
            edge_case_node._validate_indicator_params()

    @pytest.mark.asyncio
    async def test_negative_or_minutes_edge_case(self, edge_case_node):
        """Test handling of negative or_minutes."""
        edge_case_node.params["or_minutes"] = -5

        with pytest.raises(ValueError, match="Opening range minutes must be positive"):
            edge_case_node._validate_indicator_params()

    @pytest.mark.asyncio
    async def test_very_large_or_minutes(self, edge_case_node):
        """Test handling of very large or_minutes values."""
        edge_case_node.params["or_minutes"] = 1440  # 24 hours

        async def mock_calc(symbol, api_key):
            return IndicatorResult(
                indicator_type=IndicatorType.ORB,
                timestamp=1234567890000,
                values=IndicatorValue(lines={"rel_vol": 150.0}, series=[{"direction": "bullish"}]),
                params=edge_case_node.params,
            )

        edge_case_node._calculate_orb_indicator = mock_calc

        with patch("core.api_key_vault.APIKeyVault.get", return_value="test_key"):
            result = await edge_case_node.execute(
                {
                    "ohlcv_bundle": {
                        AssetSymbol("AAPL", AssetClass.STOCKS): [
                            OHLCVBar(
                                timestamp=1234567890,
                                open=100.0,
                                high=105.0,
                                low=95.0,
                                close=102.0,
                                volume=1000000,
                            )
                        ]
                    }
                }
            )

        assert "filtered_ohlcv_bundle" in result

    @pytest.mark.asyncio
    async def test_negative_rel_vol_threshold_edge_case(self, edge_case_node):
        """Test handling of negative rel_vol_threshold."""
        edge_case_node.params["rel_vol_threshold"] = -50.0

        with pytest.raises(ValueError, match="Relative volume threshold cannot be negative"):
            edge_case_node._validate_indicator_params()

    @pytest.mark.asyncio
    async def test_zero_rel_vol_threshold(self, edge_case_node):
        """Test handling of zero rel_vol_threshold."""
        edge_case_node.params["rel_vol_threshold"] = 0.0

        # Should not raise validation error
        edge_case_node._validate_indicator_params()

        async def mock_calc(symbol, api_key):
            return IndicatorResult(
                indicator_type=IndicatorType.ORB,
                timestamp=1234567890000,
                values=IndicatorValue(lines={"rel_vol": 50.0}, series=[{"direction": "bullish"}]),
                params=edge_case_node.params,
            )

        edge_case_node._calculate_orb_indicator = mock_calc

        with patch("core.api_key_vault.APIKeyVault.get", return_value="test_key"):
            result = await edge_case_node.execute(
                {
                    "ohlcv_bundle": {
                        AssetSymbol("AAPL", AssetClass.STOCKS): [
                            OHLCVBar(
                                timestamp=1234567890,
                                open=100.0,
                                high=105.0,
                                low=95.0,
                                close=102.0,
                                volume=1000000,
                            )
                        ]
                    }
                }
            )

        # With threshold 0, any positive rel_vol should pass
        assert AssetSymbol("AAPL", AssetClass.STOCKS) in result["filtered_ohlcv_bundle"]

    @pytest.mark.asyncio
    async def test_extremely_high_rel_vol_threshold(self, edge_case_node):
        """Test handling of extremely high rel_vol_threshold."""
        edge_case_node.params["rel_vol_threshold"] = 10000.0

        async def mock_calc(symbol, api_key):
            return IndicatorResult(
                indicator_type=IndicatorType.ORB,
                timestamp=1234567890000,
                values=IndicatorValue(lines={"rel_vol": 5000.0}, series=[{"direction": "bullish"}]),
                params=edge_case_node.params,
            )

        edge_case_node._calculate_orb_indicator = mock_calc

        with patch("core.api_key_vault.APIKeyVault.get", return_value="test_key"):
            result = await edge_case_node.execute(
                {
                    "ohlcv_bundle": {
                        AssetSymbol("AAPL", AssetClass.STOCKS): [
                            OHLCVBar(
                                timestamp=1234567890,
                                open=100.0,
                                high=105.0,
                                low=95.0,
                                close=102.0,
                                volume=1000000,
                            )
                        ]
                    }
                }
            )

        # Should not pass with very high threshold
        assert AssetSymbol("AAPL", AssetClass.STOCKS) not in result["filtered_ohlcv_bundle"]

    @pytest.mark.asyncio
    async def test_invalid_direction_edge_case(self, edge_case_node):
        """Test handling of invalid direction values."""
        # Test with invalid direction - should be caught by UI validation, but test robustness
        edge_case_node.params["direction"] = "invalid_direction"

        async def mock_calc(symbol, api_key):
            return IndicatorResult(
                indicator_type=IndicatorType.ORB,
                timestamp=1234567890000,
                values=IndicatorValue(lines={"rel_vol": 150.0}, series=[{"direction": "bullish"}]),
                params=edge_case_node.params,
            )

        edge_case_node._calculate_orb_indicator = mock_calc

        with patch("core.api_key_vault.APIKeyVault.get", return_value="test_key"):
            result = await edge_case_node.execute(
                {
                    "ohlcv_bundle": {
                        AssetSymbol("AAPL", AssetClass.STOCKS): [
                            OHLCVBar(
                                timestamp=1234567890,
                                open=100.0,
                                high=105.0,
                                low=95.0,
                                close=102.0,
                                volume=1000000,
                            )
                        ]
                    }
                }
            )

        # Should still work - direction filtering happens in _should_pass_filter
        assert "filtered_ohlcv_bundle" in result

    @pytest.mark.asyncio
    async def test_empty_symbol_ticker_edge_case(self, edge_case_node):
        """Test handling of empty symbol ticker."""
        empty_symbol = AssetSymbol("", AssetClass.STOCKS)

        async def mock_calc(symbol, api_key):
            if symbol.ticker == "":
                return IndicatorResult(
                    indicator_type=IndicatorType.ORB,
                    timestamp=0,
                    values=IndicatorValue(),
                    params=edge_case_node.params,
                    error="Empty ticker",
                )
            return IndicatorResult(
                indicator_type=IndicatorType.ORB,
                timestamp=1234567890000,
                values=IndicatorValue(lines={"rel_vol": 150.0}, series=[{"direction": "bullish"}]),
                params=edge_case_node.params,
            )

        edge_case_node._calculate_orb_indicator = mock_calc

        with patch("core.api_key_vault.APIKeyVault.get", return_value="test_key"):
            result = await edge_case_node.execute(
                {
                    "ohlcv_bundle": {
                        empty_symbol: [
                            OHLCVBar(
                                timestamp=1234567890,
                                open=100.0,
                                high=105.0,
                                low=95.0,
                                close=102.0,
                                volume=1000000,
                            )
                        ]
                    }
                }
            )

        # Empty ticker should not pass filter
        assert empty_symbol not in result["filtered_ohlcv_bundle"]

    @pytest.mark.asyncio
    async def test_none_ohlcv_data_edge_case(self, edge_case_node):
        """Test handling of None OHLCV data."""
        with patch("core.api_key_vault.APIKeyVault.get", return_value="test_key"):
            result = await edge_case_node.execute(
                {"ohlcv_bundle": {AssetSymbol("AAPL", AssetClass.STOCKS): None}}
            )

        # None data should be skipped
        assert AssetSymbol("AAPL", AssetClass.STOCKS) not in result["filtered_ohlcv_bundle"]

    @pytest.mark.asyncio
    async def test_malformed_ohlcv_data_edge_case(self, edge_case_node):
        """Test handling of malformed OHLCV data."""
        # Use valid structure to pass validation, but mock the calculation to return error
        valid_data = [
            OHLCVBar(
                timestamp=1234567890,
                open=100.0,
                high=105.0,
                low=95.0,
                close=102.0,
                volume=1000000,
            )
        ]

        async def mock_calc(symbol, api_key):
            return IndicatorResult(
                indicator_type=IndicatorType.ORB,
                timestamp=0,
                values=IndicatorValue(),
                params=edge_case_node.params,
                error="Malformed data",
            )

        edge_case_node._calculate_orb_indicator = mock_calc

        with patch("core.api_key_vault.APIKeyVault.get", return_value="test_key"):
            result = await edge_case_node.execute(
                {"ohlcv_bundle": {AssetSymbol("AAPL", AssetClass.STOCKS): valid_data}}
            )

        # Malformed data should not pass filter
        assert AssetSymbol("AAPL", AssetClass.STOCKS) not in result["filtered_ohlcv_bundle"]

    @pytest.mark.asyncio
    async def test_zero_volume_edge_case(self, edge_case_node):
        """Test handling of zero volume scenarios."""

        async def mock_calc_zero_vol(symbol, api_key):
            return IndicatorResult(
                indicator_type=IndicatorType.ORB,
                timestamp=1234567890000,
                values=IndicatorValue(lines={"rel_vol": 0.0}, series=[{"direction": "bullish"}]),
                params=edge_case_node.params,
            )

        edge_case_node._calculate_orb_indicator = mock_calc_zero_vol

        with patch("core.api_key_vault.APIKeyVault.get", return_value="test_key"):
            result = await edge_case_node.execute(
                {
                    "ohlcv_bundle": {
                        AssetSymbol("AAPL", AssetClass.STOCKS): [
                            OHLCVBar(
                                timestamp=1234567890,
                                open=100.0,
                                high=105.0,
                                low=95.0,
                                close=102.0,
                                volume=0,
                            )
                        ]
                    }
                }
            )

        # Zero volume should not pass threshold
        assert AssetSymbol("AAPL", AssetClass.STOCKS) not in result["filtered_ohlcv_bundle"]

    @pytest.mark.asyncio
    async def test_infinite_rel_vol_edge_case(self, edge_case_node):
        """Test handling of infinite relative volume values."""

        async def mock_calc_infinite_vol(symbol, api_key):
            return IndicatorResult(
                indicator_type=IndicatorType.ORB,
                timestamp=1234567890000,
                values=IndicatorValue(
                    lines={"rel_vol": float("inf")}, series=[{"direction": "bullish"}]
                ),
                params=edge_case_node.params,
            )

        edge_case_node._calculate_orb_indicator = mock_calc_infinite_vol

        with patch("core.api_key_vault.APIKeyVault.get", return_value="test_key"):
            result = await edge_case_node.execute(
                {
                    "ohlcv_bundle": {
                        AssetSymbol("AAPL", AssetClass.STOCKS): [
                            OHLCVBar(
                                timestamp=1234567890,
                                open=100.0,
                                high=105.0,
                                low=95.0,
                                close=102.0,
                                volume=1000000,
                            )
                        ]
                    }
                }
            )

        # Infinite volume should pass any threshold
        assert AssetSymbol("AAPL", AssetClass.STOCKS) in result["filtered_ohlcv_bundle"]

    @pytest.mark.asyncio
    async def test_nan_rel_vol_edge_case(self, edge_case_node):
        """Test handling of NaN relative volume values."""

        async def mock_calc_nan_vol(symbol, api_key):
            return IndicatorResult(
                indicator_type=IndicatorType.ORB,
                timestamp=1234567890000,
                values=IndicatorValue(
                    lines={"rel_vol": float("nan")}, series=[{"direction": "bullish"}]
                ),
                params=edge_case_node.params,
            )

        edge_case_node._calculate_orb_indicator = mock_calc_nan_vol

        with patch("core.api_key_vault.APIKeyVault.get", return_value="test_key"):
            result = await edge_case_node.execute(
                {
                    "ohlcv_bundle": {
                        AssetSymbol("AAPL", AssetClass.STOCKS): [
                            OHLCVBar(
                                timestamp=1234567890,
                                open=100.0,
                                high=105.0,
                                low=95.0,
                                close=102.0,
                                volume=1000000,
                            )
                        ]
                    }
                }
            )

        # NaN volume should not pass filter
        assert AssetSymbol("AAPL", AssetClass.STOCKS) not in result["filtered_ohlcv_bundle"]

    @pytest.mark.asyncio
    async def test_missing_direction_in_series_edge_case(self, edge_case_node):
        """Test handling of missing direction in series."""

        async def mock_calc_no_direction(symbol, api_key):
            return IndicatorResult(
                indicator_type=IndicatorType.ORB,
                timestamp=1234567890000,
                values=IndicatorValue(lines={"rel_vol": 150.0}, series=[{"other_field": "value"}]),
                params=edge_case_node.params,
            )

        edge_case_node._calculate_orb_indicator = mock_calc_no_direction

        with patch("core.api_key_vault.APIKeyVault.get", return_value="test_key"):
            result = await edge_case_node.execute(
                {
                    "ohlcv_bundle": {
                        AssetSymbol("AAPL", AssetClass.STOCKS): [
                            OHLCVBar(
                                timestamp=1234567890,
                                open=100.0,
                                high=105.0,
                                low=95.0,
                                close=102.0,
                                volume=1000000,
                            )
                        ]
                    }
                }
            )

        # Missing direction should default to "doji" and not pass
        assert AssetSymbol("AAPL", AssetClass.STOCKS) not in result["filtered_ohlcv_bundle"]

    @pytest.mark.asyncio
    async def test_empty_series_edge_case(self, edge_case_node):
        """Test handling of empty series."""

        async def mock_calc_empty_series(symbol, api_key):
            return IndicatorResult(
                indicator_type=IndicatorType.ORB,
                timestamp=1234567890000,
                values=IndicatorValue(lines={"rel_vol": 150.0}, series=[]),
                params=edge_case_node.params,
            )

        edge_case_node._calculate_orb_indicator = mock_calc_empty_series

        with patch("core.api_key_vault.APIKeyVault.get", return_value="test_key"):
            result = await edge_case_node.execute(
                {
                    "ohlcv_bundle": {
                        AssetSymbol("AAPL", AssetClass.STOCKS): [
                            OHLCVBar(
                                timestamp=1234567890,
                                open=100.0,
                                high=105.0,
                                low=95.0,
                                close=102.0,
                                volume=1000000,
                            )
                        ]
                    }
                }
            )

        # Empty series should not pass filter
        assert AssetSymbol("AAPL", AssetClass.STOCKS) not in result["filtered_ohlcv_bundle"]

    @pytest.mark.asyncio
    async def test_missing_rel_vol_in_lines_edge_case(self, edge_case_node):
        """Test handling of missing rel_vol in lines."""

        async def mock_calc_no_rel_vol(symbol, api_key):
            return IndicatorResult(
                indicator_type=IndicatorType.ORB,
                timestamp=1234567890000,
                values=IndicatorValue(
                    lines={"other_field": 150.0}, series=[{"direction": "bullish"}]
                ),
                params=edge_case_node.params,
            )

        edge_case_node._calculate_orb_indicator = mock_calc_no_rel_vol

        with patch("core.api_key_vault.APIKeyVault.get", return_value="test_key"):
            result = await edge_case_node.execute(
                {
                    "ohlcv_bundle": {
                        AssetSymbol("AAPL", AssetClass.STOCKS): [
                            OHLCVBar(
                                timestamp=1234567890,
                                open=100.0,
                                high=105.0,
                                low=95.0,
                                close=102.0,
                                volume=1000000,
                            )
                        ]
                    }
                }
            )

        # Missing rel_vol should not pass filter
        assert AssetSymbol("AAPL", AssetClass.STOCKS) not in result["filtered_ohlcv_bundle"]

    @pytest.mark.asyncio
    async def test_empty_lines_edge_case(self, edge_case_node):
        """Test handling of empty lines."""

        async def mock_calc_empty_lines(symbol, api_key):
            return IndicatorResult(
                indicator_type=IndicatorType.ORB,
                timestamp=1234567890000,
                values=IndicatorValue(lines={}, series=[{"direction": "bullish"}]),
                params=edge_case_node.params,
            )

        edge_case_node._calculate_orb_indicator = mock_calc_empty_lines

        with patch("core.api_key_vault.APIKeyVault.get", return_value="test_key"):
            result = await edge_case_node.execute(
                {
                    "ohlcv_bundle": {
                        AssetSymbol("AAPL", AssetClass.STOCKS): [
                            OHLCVBar(
                                timestamp=1234567890,
                                open=100.0,
                                high=105.0,
                                low=95.0,
                                close=102.0,
                                volume=1000000,
                            )
                        ]
                    }
                }
            )

        # Empty lines should not pass filter
        assert AssetSymbol("AAPL", AssetClass.STOCKS) not in result["filtered_ohlcv_bundle"]

    @pytest.mark.asyncio
    async def test_concurrent_limit_edge_cases(self, edge_case_node):
        """Test various concurrent limit edge cases."""
        # Test with max_concurrent = 0
        edge_case_node.params["max_concurrent"] = 0

        async def mock_calc(symbol, api_key):
            return IndicatorResult(
                indicator_type=IndicatorType.ORB,
                timestamp=1234567890000,
                values=IndicatorValue(lines={"rel_vol": 150.0}, series=[{"direction": "bullish"}]),
                params=edge_case_node.params,
            )

        edge_case_node._calculate_orb_indicator = mock_calc

        with patch("core.api_key_vault.APIKeyVault.get", return_value="test_key"):
            result = await edge_case_node.execute(
                {
                    "ohlcv_bundle": {
                        AssetSymbol("AAPL", AssetClass.STOCKS): [
                            OHLCVBar(
                                timestamp=1234567890,
                                open=100.0,
                                high=105.0,
                                low=95.0,
                                close=102.0,
                                volume=1000000,
                            )
                        ]
                    }
                }
            )

        # Should still work with 0 concurrency (sequential processing)
        assert "filtered_ohlcv_bundle" in result

    @pytest.mark.asyncio
    async def test_rate_limit_edge_cases(self, edge_case_node):
        """Test various rate limit edge cases."""
        # Test with rate_limit_per_second = 0
        edge_case_node.params["rate_limit_per_second"] = 0

        async def mock_calc(symbol, api_key):
            return IndicatorResult(
                indicator_type=IndicatorType.ORB,
                timestamp=1234567890000,
                values=IndicatorValue(lines={"rel_vol": 150.0}, series=[{"direction": "bullish"}]),
                params=edge_case_node.params,
            )

        edge_case_node._calculate_orb_indicator = mock_calc

        with patch("core.api_key_vault.APIKeyVault.get", return_value="test_key"):
            result = await edge_case_node.execute(
                {
                    "ohlcv_bundle": {
                        AssetSymbol("AAPL", AssetClass.STOCKS): [
                            OHLCVBar(
                                timestamp=1234567890,
                                open=100.0,
                                high=105.0,
                                low=95.0,
                                close=102.0,
                                volume=1000000,
                            )
                        ]
                    }
                }
            )

        # Should still work with 0 rate limit
        assert "filtered_ohlcv_bundle" in result

    @pytest.mark.asyncio
    async def test_memory_intensive_large_dataset(self, edge_case_node):
        """Test handling of memory-intensive large datasets."""
        # Create a large number of symbols to test memory usage
        large_symbols = [AssetSymbol(f"SYMBOL_{_}", AssetClass.STOCKS) for _ in range(1000)]
        large_bundle = {
            symbol: [
                OHLCVBar(
                    timestamp=1234567890,
                    open=100.0,
                    high=105.0,
                    low=95.0,
                    close=102.0,
                    volume=1000000,
                )
            ]
            for symbol in large_symbols
        }

        async def mock_calc(symbol, api_key):
            return IndicatorResult(
                indicator_type=IndicatorType.ORB,
                timestamp=1234567890000,
                values=IndicatorValue(lines={"rel_vol": 150.0}, series=[{"direction": "bullish"}]),
                params=edge_case_node.params,
            )

        edge_case_node._calculate_orb_indicator = mock_calc

        with patch("core.api_key_vault.APIKeyVault.get", return_value="test_key"):
            result = await edge_case_node.execute({"ohlcv_bundle": large_bundle})

        # Should handle large datasets without memory issues
        assert len(result["filtered_ohlcv_bundle"]) == 1000

    @pytest.mark.asyncio
    async def test_crypto_vs_stocks_timing_edge_cases(self, edge_case_node):
        """Test crypto vs stocks timing edge cases."""
        # Test crypto symbol
        crypto_symbol = AssetSymbol("BTC", AssetClass.CRYPTO)

        async def mock_calc_crypto(symbol, api_key):
            if symbol.asset_class.name == "CRYPTO":
                return IndicatorResult(
                    indicator_type=IndicatorType.ORB,
                    timestamp=1234567890000,
                    values=IndicatorValue(
                        lines={"rel_vol": 150.0}, series=[{"direction": "bullish"}]
                    ),
                    params=edge_case_node.params,
                )
            return IndicatorResult(
                indicator_type=IndicatorType.ORB,
                timestamp=1234567890000,
                values=IndicatorValue(lines={"rel_vol": 150.0}, series=[{"direction": "bullish"}]),
                params=edge_case_node.params,
            )

        edge_case_node._calculate_orb_indicator = mock_calc_crypto

        with patch("core.api_key_vault.APIKeyVault.get", return_value="test_key"):
            result = await edge_case_node.execute(
                {
                    "ohlcv_bundle": {
                        crypto_symbol: [
                            OHLCVBar(
                                timestamp=1234567890,
                                open=100.0,
                                high=105.0,
                                low=95.0,
                                close=102.0,
                                volume=1000000,
                            )
                        ],
                        AssetSymbol("AAPL", AssetClass.STOCKS): [
                            OHLCVBar(
                                timestamp=1234567890,
                                open=100.0,
                                high=105.0,
                                low=95.0,
                                close=102.0,
                                volume=1000000,
                            )
                        ],
                    }
                }
            )

        # Both crypto and stocks should be processed
        assert crypto_symbol in result["filtered_ohlcv_bundle"]
        assert AssetSymbol("AAPL", AssetClass.STOCKS) in result["filtered_ohlcv_bundle"]

    @pytest.mark.asyncio
    async def test_timezone_edge_cases(self, edge_case_node):
        """Test timezone-related edge cases."""

        # Test with different timezone scenarios
        async def mock_calc_timezone(symbol, api_key):
            return IndicatorResult(
                indicator_type=IndicatorType.ORB,
                timestamp=1234567890000,  # Different timestamp
                values=IndicatorValue(lines={"rel_vol": 150.0}, series=[{"direction": "bullish"}]),
                params=edge_case_node.params,
            )

        edge_case_node._calculate_orb_indicator = mock_calc_timezone

        with patch("core.api_key_vault.APIKeyVault.get", return_value="test_key"):
            result = await edge_case_node.execute(
                {
                    "ohlcv_bundle": {
                        AssetSymbol("AAPL", AssetClass.STOCKS): [
                            OHLCVBar(
                                timestamp=1234567890,
                                open=100.0,
                                high=105.0,
                                low=95.0,
                                close=102.0,
                                volume=1000000,
                            )
                        ]
                    }
                }
            )

        # Should handle different timestamps correctly
        assert "filtered_ohlcv_bundle" in result

    @pytest.mark.asyncio
    async def test_api_key_edge_cases(self, edge_case_node):
        """Test various API key edge cases."""
        # Test with empty API key
        with patch("core.api_key_vault.APIKeyVault.get", return_value=""):
            with pytest.raises(NodeExecutionError) as exc_info:
                await edge_case_node.execute(
                    {
                        "ohlcv_bundle": {
                            AssetSymbol("AAPL", AssetClass.STOCKS): [
                                OHLCVBar(
                                    timestamp=1234567890,
                                    open=100.0,
                                    high=105.0,
                                    low=95.0,
                                    close=102.0,
                                    volume=1000000,
                                )
                            ]
                        }
                    }
                )
            assert isinstance(exc_info.value.original_exc, ValueError)

        # Test with whitespace-only API key
        with patch("core.api_key_vault.APIKeyVault.get", return_value="   "):
            with pytest.raises(NodeExecutionError) as exc_info:
                await edge_case_node.execute(
                    {
                        "ohlcv_bundle": {
                            AssetSymbol("AAPL", AssetClass.STOCKS): [
                                OHLCVBar(
                                    timestamp=1234567890,
                                    open=100.0,
                                    high=105.0,
                                    low=95.0,
                                    close=102.0,
                                    volume=1000000,
                                )
                            ]
                        }
                    }
                )
            assert isinstance(exc_info.value.original_exc, ValueError)

    @pytest.mark.asyncio
    async def test_network_timeout_edge_case(self, edge_case_node):
        """Test handling of network timeout scenarios."""

        async def mock_calc_timeout(symbol, api_key):
            # Simulate network timeout
            raise TimeoutError("Network timeout")

        edge_case_node._calculate_orb_indicator = mock_calc_timeout

        with patch("core.api_key_vault.APIKeyVault.get", return_value="test_key"):
            result = await edge_case_node.execute(
                {
                    "ohlcv_bundle": {
                        AssetSymbol("AAPL", AssetClass.STOCKS): [
                            OHLCVBar(
                                timestamp=1234567890,
                                open=100.0,
                                high=105.0,
                                low=95.0,
                                close=102.0,
                                volume=1000000,
                            )
                        ]
                    }
                }
            )

        # Should handle timeout gracefully
        assert AssetSymbol("AAPL", AssetClass.STOCKS) not in result["filtered_ohlcv_bundle"]

    @pytest.mark.asyncio
    async def test_mixed_success_failure_scenarios(self, edge_case_node):
        """Test mixed success/failure scenarios."""
        symbols = [
            AssetSymbol("SUCCESS1", AssetClass.STOCKS),
            AssetSymbol("FAIL1", AssetClass.STOCKS),
            AssetSymbol("SUCCESS2", AssetClass.STOCKS),
            AssetSymbol("FAIL2", AssetClass.STOCKS),
        ]

        async def mock_calc_mixed(symbol, api_key):
            if "FAIL" in symbol.ticker:
                raise Exception("Simulated failure")
            return IndicatorResult(
                indicator_type=IndicatorType.ORB,
                timestamp=1234567890000,
                values=IndicatorValue(lines={"rel_vol": 150.0}, series=[{"direction": "bullish"}]),
                params=edge_case_node.params,
            )

        edge_case_node._calculate_orb_indicator = mock_calc_mixed

        ohlcv_bundle = {
            symbol: [
                OHLCVBar(
                    timestamp=1234567890,
                    open=100.0,
                    high=105.0,
                    low=95.0,
                    close=102.0,
                    volume=1000000,
                )
            ]
            for symbol in symbols
        }

        with patch("core.api_key_vault.APIKeyVault.get", return_value="test_key"):
            result = await edge_case_node.execute({"ohlcv_bundle": ohlcv_bundle})

        # Only successful symbols should be in result
        assert AssetSymbol("SUCCESS1", AssetClass.STOCKS) in result["filtered_ohlcv_bundle"]
        assert AssetSymbol("FAIL1", AssetClass.STOCKS) not in result["filtered_ohlcv_bundle"]
        assert AssetSymbol("SUCCESS2", AssetClass.STOCKS) in result["filtered_ohlcv_bundle"]
        assert AssetSymbol("FAIL2", AssetClass.STOCKS) not in result["filtered_ohlcv_bundle"]

    @pytest.mark.asyncio
    async def test_progress_reporting_edge_cases(self, edge_case_node):
        """Test progress reporting edge cases."""
        progress_calls = []

        def mock_report(progress, text):
            progress_calls.append((progress, text))

        edge_case_node.report_progress = mock_report

        async def mock_calc(symbol, api_key):
            return IndicatorResult(
                indicator_type=IndicatorType.ORB,
                timestamp=1234567890000,
                values=IndicatorValue(lines={"rel_vol": 150.0}, series=[{"direction": "bullish"}]),
                params=edge_case_node.params,
            )

        edge_case_node._calculate_orb_indicator = mock_calc

        # Test with single symbol
        with patch("core.api_key_vault.APIKeyVault.get", return_value="test_key"):
            await edge_case_node.execute(
                {
                    "ohlcv_bundle": {
                        AssetSymbol("AAPL", AssetClass.STOCKS): [
                            OHLCVBar(
                                timestamp=1234567890,
                                open=100.0,
                                high=105.0,
                                low=95.0,
                                close=102.0,
                                volume=1000000,
                            )
                        ]
                    }
                }
            )

        # Should have progress calls
        assert len(progress_calls) > 0
        # First call should be 0%
        assert progress_calls[0][0] == 0.0
        # Last call should be 100%
        assert progress_calls[-1][0] == 100.0

    @pytest.mark.asyncio
    async def test_worker_cancellation_edge_cases(self, edge_case_node):
        """Test worker cancellation edge cases."""

        async def slow_calc(symbol, api_key):
            await asyncio.sleep(0.1)  # Simulate slow calculation
            return IndicatorResult(
                indicator_type=IndicatorType.ORB,
                timestamp=1234567890000,
                values=IndicatorValue(lines={"rel_vol": 150.0}, series=[{"direction": "bullish"}]),
                params=edge_case_node.params,
            )

        edge_case_node._calculate_orb_indicator = slow_calc

        symbols = [AssetSymbol(f"SYMBOL_{_}", AssetClass.STOCKS) for _ in range(10)]
        ohlcv_bundle = {
            symbol: [
                OHLCVBar(
                    timestamp=1234567890,
                    open=100.0,
                    high=105.0,
                    low=95.0,
                    close=102.0,
                    volume=1000000,
                )
            ]
            for symbol in symbols
        }

        with patch("core.api_key_vault.APIKeyVault.get", return_value="test_key"):
            execute_task = asyncio.create_task(
                edge_case_node.execute({"ohlcv_bundle": ohlcv_bundle})
            )

            await asyncio.sleep(0.05)  # Let workers start
            assert len(edge_case_node.workers) > 0

            # Cancel execution
            execute_task.cancel()

            with pytest.raises(asyncio.CancelledError):
                await execute_task

            # Workers should be cancelled
            await asyncio.sleep(0.1)
            assert all(w.cancelled() or w.done() for w in edge_case_node.workers)
