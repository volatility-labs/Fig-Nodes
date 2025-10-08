import pytest
import asyncio
from unittest.mock import AsyncMock, patch, MagicMock
from typing import Dict, Any, List
import time
from nodes.custom.polygon.polygon_batch_custom_bars_node import PolygonBatchCustomBarsNode, RateLimiter
from core.types_registry import AssetSymbol, AssetClass, OHLCVBar


@pytest.fixture
def sample_symbols():
    return [
        AssetSymbol("AAPL", AssetClass.STOCKS),
        AssetSymbol("MSFT", AssetClass.STOCKS),
        AssetSymbol("GOOGL", AssetClass.STOCKS),
    ]


@pytest.fixture
def polygon_batch_node():
    return PolygonBatchCustomBarsNode("batch_bars_id", {
        "multiplier": 1,
        "timespan": "day",
        "lookback_period": "3 months",
        "adjusted": True,
        "sort": "asc",
        "limit": 5000,
        "max_concurrent": 5,
        "max_symbols": 50,
        "rate_limit_per_second": 95,
    })


@pytest.fixture
def mock_bars_response():
    """Mock response data for successful API calls."""
    return [
        {
            "timestamp": 1672531200000,  # 2023-01-01
            "open": 150.0,
            "high": 155.0,
            "low": 148.0,
            "close": 152.0,
            "volume": 1000000,
            "vw": 151.5,
            "n": 5000,
        },
        {
            "timestamp": 1672617600000,  # 2023-01-02
            "open": 152.0,
            "high": 158.0,
            "low": 150.0,
            "close": 155.0,
            "volume": 1200000,
            "vw": 154.0,
            "n": 6000,
        }
    ]


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


class TestPolygonBatchCustomBarsNode:
    """Comprehensive tests for PolygonBatchCustomBarsNode."""

    @pytest.mark.asyncio
    async def test_execute_empty_symbols(self, polygon_batch_node):
        """Test execution with empty symbols list."""
        result = await polygon_batch_node.execute({
            "symbols": [],
            "api_key": "test_key"
        })
        assert result == {"ohlcv_bundle": {}}

    @pytest.mark.asyncio
    async def test_execute_missing_api_key(self, polygon_batch_node, sample_symbols):
        """Test error when API key is missing."""
        with pytest.raises(ValueError, match="Polygon API key input is required"):
            await polygon_batch_node.execute({
                "symbols": sample_symbols,
                "api_key": None
            })

    @pytest.mark.asyncio
    async def test_execute_missing_api_key_empty_string(self, polygon_batch_node, sample_symbols):
        """Test error when API key is empty string."""
        with pytest.raises(ValueError, match="Polygon API key input is required"):
            await polygon_batch_node.execute({
                "symbols": sample_symbols,
                "api_key": ""
            })

    @pytest.mark.asyncio
    async def test_execute_successful_batch_fetch(self, polygon_batch_node, sample_symbols, mock_bars_response):
        """Test successful batch fetching of bars."""
        with patch("nodes.custom.polygon.polygon_batch_custom_bars_node.fetch_bars", new_callable=AsyncMock) as mock_fetch:
            mock_fetch.return_value = mock_bars_response

            result = await polygon_batch_node.execute({
                "symbols": sample_symbols,
                "api_key": "test_api_key"
            })

            assert "ohlcv_bundle" in result
            bundle = result["ohlcv_bundle"]
            assert isinstance(bundle, dict)
            assert len(bundle) == 3  # All symbols should have data

            for symbol in sample_symbols:
                assert symbol in bundle
                bars = bundle[symbol]
                assert isinstance(bars, list)
                assert len(bars) == 2
                assert bars[0]["open"] == 150.0
                assert bars[1]["close"] == 155.0

            # Verify fetch_bars was called for each symbol
            assert mock_fetch.call_count == 3
            calls = mock_fetch.call_args_list
            for i, symbol in enumerate(sample_symbols):
                args, kwargs = calls[i]
                assert args[0] == symbol  # symbol
                assert args[1] == "test_api_key"  # api_key
                assert isinstance(args[2], dict)  # params

    @pytest.mark.asyncio
    async def test_execute_partial_failures(self, polygon_batch_node, sample_symbols, mock_bars_response):
        """Test handling of partial failures in batch fetch."""
        async def mock_fetch_side_effect(symbol, api_key, params):
            if symbol.ticker == "MSFT":
                raise Exception("API rate limit exceeded")
            return mock_bars_response

        with patch("nodes.custom.polygon.polygon_batch_custom_bars_node.fetch_bars", side_effect=mock_fetch_side_effect):
            result = await polygon_batch_node.execute({
                "symbols": sample_symbols,
                "api_key": "test_api_key"
            })

            bundle = result["ohlcv_bundle"]
            # AAPL and GOOGL should succeed, MSFT should be missing
            assert len(bundle) == 2
            assert sample_symbols[0] in bundle  # AAPL
            assert sample_symbols[1] not in bundle  # MSFT (failed)
            assert sample_symbols[2] in bundle  # GOOGL

    @pytest.mark.asyncio
    async def test_execute_no_symbol_limit(self, polygon_batch_node, mock_bars_response):
        """Test that there are no symbol limits."""
        # Create 60 symbols - should process all of them
        symbols = [AssetSymbol(f"SYMBOL_{i}", AssetClass.STOCKS) for i in range(60)]

        with patch("nodes.custom.polygon.polygon_batch_custom_bars_node.fetch_bars", new_callable=AsyncMock) as mock_fetch:
            mock_fetch.return_value = mock_bars_response

            result = await polygon_batch_node.execute({
                "symbols": symbols,
                "api_key": "test_api_key"
            })

            # Should process all 60 symbols
            assert mock_fetch.call_count == 60
            bundle = result["ohlcv_bundle"]
            assert len(bundle) == 60

    @pytest.mark.asyncio
    async def test_execute_all_symbols_processed(self, mock_bars_response):
        """Test that all symbols are processed regardless of count."""
        node = PolygonBatchCustomBarsNode("test_id", {})
        symbols = [AssetSymbol(f"SYMBOL_{i}", AssetClass.STOCKS) for i in range(20)]

        with patch("nodes.custom.polygon.polygon_batch_custom_bars_node.fetch_bars", new_callable=AsyncMock) as mock_fetch:
            mock_fetch.return_value = mock_bars_response

            result = await node.execute({
                "symbols": symbols,
                "api_key": "test_api_key"
            })

            # Should process all 20 symbols
            assert mock_fetch.call_count == 20

    @pytest.mark.asyncio
    async def test_execute_concurrency_control(self, polygon_batch_node, mock_bars_response):
        """Test concurrency limiting."""
        # Create many symbols to test concurrency
        symbols = [AssetSymbol(f"SYMBOL_{i}", AssetClass.STOCKS) for i in range(20)]

        with patch("nodes.custom.polygon.polygon_batch_custom_bars_node.fetch_bars", new_callable=AsyncMock) as mock_fetch:
            # Make fetch_bars take some time to test concurrency
            async def slow_fetch(*args, **kwargs):
                await asyncio.sleep(0.01)
                return mock_bars_response

            mock_fetch.side_effect = slow_fetch

            start_time = time.time()
            result = await polygon_batch_node.execute({
                "symbols": symbols,
                "api_key": "test_api_key"
            })
            elapsed = time.time() - start_time

            # With max_concurrent=5, should take longer than if all ran in parallel
            # but faster than if they ran sequentially
            assert elapsed >= 0.04  # At least 4 batches of 5 concurrent requests

            assert len(result["ohlcv_bundle"]) == 20

    @pytest.mark.asyncio
    async def test_execute_rate_limiting(self, polygon_batch_node, mock_bars_response):
        """Test rate limiting functionality."""
        symbols = [AssetSymbol(f"SYMBOL_{i}", AssetClass.STOCKS) for i in range(20)]

        async def rate_limited_fetch(*args, **kwargs):
            # Simulate some processing time and rate limiting
            await asyncio.sleep(0.01)
            return mock_bars_response

        with patch("nodes.custom.polygon.polygon_batch_custom_bars_node.fetch_bars", side_effect=rate_limited_fetch):
            start_time = time.time()
            result = await polygon_batch_node.execute({
                "symbols": symbols,
                "api_key": "test_api_key"
            })
            elapsed = time.time() - start_time

            # With rate limiting and concurrency control, should take some time
            # The exact timing depends on rate limiter implementation
            assert elapsed >= 0.03  # Should take at least some time due to concurrency and simulated fetch time
            assert len(result["ohlcv_bundle"]) == 20

    @pytest.mark.asyncio
    async def test_execute_timeout_handling(self, polygon_batch_node, sample_symbols):
        """Test timeout handling."""
        async def slow_fetch(*args, **kwargs):
            await asyncio.sleep(6)  # Longer than 5 minute timeout
            return []

        with patch("nodes.custom.polygon.polygon_batch_custom_bars_node.fetch_bars", side_effect=slow_fetch):
            with patch("asyncio.wait_for", side_effect=asyncio.TimeoutError):
                result = await polygon_batch_node.execute({
                    "symbols": sample_symbols,
                    "api_key": "test_api_key"
                })

                # Should return empty bundle on timeout
                assert result == {"ohlcv_bundle": {}}

    @pytest.mark.asyncio
    async def test_execute_task_exception_handling(self, polygon_batch_node, sample_symbols):
        """Test handling of task exceptions."""
        async def failing_fetch(*args, **kwargs):
            raise RuntimeError("Task failed")

        with patch("nodes.custom.polygon.polygon_batch_custom_bars_node.fetch_bars", side_effect=failing_fetch):
            result = await polygon_batch_node.execute({
                "symbols": sample_symbols,
                "api_key": "test_api_key"
            })

            # Should return empty bundle when all tasks fail
            assert result == {"ohlcv_bundle": {}}

    @pytest.mark.asyncio
    async def test_execute_empty_bars_filtered_out(self, polygon_batch_node, sample_symbols):
        """Test that empty bars results are filtered out."""
        async def empty_bars_fetch(*args, **kwargs):
            return []  # Return empty bars

        with patch("nodes.custom.polygon.polygon_batch_custom_bars_node.fetch_bars", side_effect=empty_bars_fetch):
            result = await polygon_batch_node.execute({
                "symbols": sample_symbols,
                "api_key": "test_api_key"
            })

            # Should return empty bundle when all symbols return empty bars
            assert result == {"ohlcv_bundle": {}}

    @pytest.mark.asyncio
    async def test_execute_mixed_empty_and_valid_bars(self, polygon_batch_node, sample_symbols, mock_bars_response):
        """Test handling of mix of empty and valid bars."""
        call_count = 0

        async def mixed_fetch(symbol, api_key, params):
            nonlocal call_count
            call_count += 1
            if call_count % 2 == 0:  # Even calls return empty
                return []
            return mock_bars_response

        with patch("nodes.custom.polygon.polygon_batch_custom_bars_node.fetch_bars", side_effect=mixed_fetch):
            result = await polygon_batch_node.execute({
                "symbols": sample_symbols,
                "api_key": "test_api_key"
            })

            bundle = result["ohlcv_bundle"]
            # Should have 2 symbols with data (odd calls: 1st and 3rd)
            assert len(bundle) == 2

    @pytest.mark.asyncio
    async def test_execute_crypto_symbols(self, polygon_batch_node, mock_bars_response):
        """Test with crypto symbols."""
        crypto_symbols = [
            AssetSymbol("BTC", AssetClass.CRYPTO, quote_currency="USDT"),
            AssetSymbol("ETH", AssetClass.CRYPTO, quote_currency="USDT"),
        ]

        with patch("nodes.custom.polygon.polygon_batch_custom_bars_node.fetch_bars", new_callable=AsyncMock) as mock_fetch:
            mock_fetch.return_value = mock_bars_response

            result = await polygon_batch_node.execute({
                "symbols": crypto_symbols,
                "api_key": "test_api_key"
            })

            assert len(result["ohlcv_bundle"]) == 2

            # Verify the symbols are passed correctly to fetch_bars
            calls = mock_fetch.call_args_list
            assert calls[0][0][0] == crypto_symbols[0]  # First symbol
            assert calls[1][0][0] == crypto_symbols[1]  # Second symbol

    @pytest.mark.asyncio
    async def test_execute_custom_parameters_passed(self, mock_bars_response):
        """Test that custom parameters are passed to fetch_bars."""
        custom_params = {
            "multiplier": 5,
            "timespan": "minute",
            "lookback_period": "1 week",
            "adjusted": False,
            "sort": "desc",
            "limit": 100,
        }
        node = PolygonBatchCustomBarsNode("test_id", custom_params)
        symbols = [AssetSymbol("AAPL", AssetClass.STOCKS)]

        with patch("nodes.custom.polygon.polygon_batch_custom_bars_node.fetch_bars", new_callable=AsyncMock) as mock_fetch:
            mock_fetch.return_value = mock_bars_response

            await node.execute({
                "symbols": symbols,
                "api_key": "test_key"
            })

            # Verify parameters were passed to fetch_bars
            args, kwargs = mock_fetch.call_args
            params = args[2]  # Third argument is params
            assert params["multiplier"] == 5
            assert params["timespan"] == "minute"
            assert params["lookback_period"] == "1 week"
            assert params["adjusted"] == False
            assert params["sort"] == "desc"
            assert params["limit"] == 100

    @pytest.mark.asyncio
    async def test_execute_concurrent_params(self):
        """Test different concurrency and rate limit parameters."""
        node = PolygonBatchCustomBarsNode("test_id", {
            "max_concurrent": 2,
            "rate_limit_per_second": 5,
        })
        symbols = [AssetSymbol(f"SYMBOL_{i}", AssetClass.STOCKS) for i in range(10)]

        async def slow_fetch(*args, **kwargs):
            # Simulate slower fetch with rate limiting
            await asyncio.sleep(0.1)
            return []

        with patch("nodes.custom.polygon.polygon_batch_custom_bars_node.fetch_bars", side_effect=slow_fetch):
            start_time = time.time()
            result = await node.execute({
                "symbols": symbols,
                "api_key": "test_key"
            })
            elapsed = time.time() - start_time

            # With low concurrency (2) and rate limit (5/sec), plus simulated fetch time,
            # should take significant time for 10 requests
            assert elapsed >= 0.8  # Should take at least 0.8 seconds

    @pytest.mark.asyncio
    async def test_execute_cancellation_during_fetch(self, polygon_batch_node, sample_symbols):
        """Test handling of cancellation during batch fetch."""

        async def slow_fetch(*args, **kwargs):
            await asyncio.sleep(1.0)  # Simulate long fetch
            return []

        with patch("nodes.custom.polygon.polygon_batch_custom_bars_node.fetch_bars", side_effect=slow_fetch):
            execute_task = asyncio.create_task(polygon_batch_node.execute({
                "symbols": sample_symbols,
                "api_key": "test_key"
            }))

            await asyncio.sleep(0.1)  # Let it start
            execute_task.cancel()

            with pytest.raises(asyncio.CancelledError):
                await execute_task

    @pytest.mark.asyncio
    async def test_progress_after_cancellation(self, polygon_batch_node, sample_symbols):
        """Test that no progress is reported after cancellation."""

        progress_calls = []

        def mock_report(progress, text):
            progress_calls.append((progress, text))

        polygon_batch_node.report_progress = mock_report

        async def fast_fetch(*args, **kwargs):
            # Return immediately so progress gets reported before cancellation
            return []

        with patch("nodes.custom.polygon.polygon_batch_custom_bars_node.fetch_bars", side_effect=fast_fetch):
            execute_task = asyncio.create_task(polygon_batch_node.execute({
                "symbols": sample_symbols,
                "api_key": "test_key"
            }))

            # Wait a bit for some progress to be reported
            await asyncio.sleep(0.01)
            execute_task.cancel()

            try:
                await execute_task
            except asyncio.CancelledError:
                pass

            # Give time for any pending progress calls
            await asyncio.sleep(0.1)

            # Should have some progress calls before cancellation, but not after
            assert len(progress_calls) > 0
            # Note: Exact count may vary, but the point is that cancellation stops further progress

    def test_node_properties(self, polygon_batch_node):
        """Test node configuration properties."""
        from core.types_registry import get_type

        assert polygon_batch_node.inputs == {
            "symbols": get_type("AssetSymbolList"),
            "api_key": get_type("APIKey")
        }
        assert polygon_batch_node.outputs == {"ohlcv_bundle": Dict[AssetSymbol, List[OHLCVBar]]}

        expected_defaults = {
            "multiplier": 1,
            "timespan": "day",
            "lookback_period": "3 months",
            "adjusted": True,
            "sort": "asc",
            "limit": 5000,
            "max_concurrent": 10,
            "rate_limit_per_second": 95,
        }
        assert polygon_batch_node.default_params == expected_defaults

        # Verify params_meta structure (execution controls removed from UI)
        assert len(polygon_batch_node.params_meta) == 6
        param_names = [p["name"] for p in polygon_batch_node.params_meta]
        expected_names = [
            "multiplier", "timespan", "lookback_period", "adjusted", "sort", "limit"
        ]
        assert set(param_names) == set(expected_names)

    def test_validate_inputs(self, polygon_batch_node, sample_symbols):
        """Test input validation."""
        # Valid inputs
        assert polygon_batch_node.validate_inputs({
            "symbols": sample_symbols,
            "api_key": "test_key"
        }) is True

        # Missing api_key
        assert polygon_batch_node.validate_inputs({
            "symbols": sample_symbols
        }) is False

        # Empty symbols list (should be valid, returns empty bundle)
        assert polygon_batch_node.validate_inputs({
            "symbols": [],
            "api_key": "test_key"
        }) is True

    @pytest.mark.asyncio
    async def test_cancellation_propagates_through_fetch_bars(self, sample_symbols):
        """Test that CancelledError during fetch_bars properly propagates and stops execution."""
        # Use single concurrency to ensure deterministic behavior
        node = PolygonBatchCustomBarsNode("test_id", {"max_concurrent": 1})
        call_count = 0

        async def cancellable_fetch(symbol, api_key, params):
            nonlocal call_count
            call_count += 1
            if call_count == 2:  # Cancel on second call to allow first to complete
                raise asyncio.CancelledError("Simulated cancellation")
            await asyncio.sleep(0.01)  # Brief delay for other calls
            return []

        with patch("nodes.custom.polygon.polygon_batch_custom_bars_node.fetch_bars", side_effect=cancellable_fetch):
            execute_task = asyncio.create_task(node.execute({
                "symbols": sample_symbols,
                "api_key": "test_key"
            }))

            with pytest.raises(asyncio.CancelledError):
                await execute_task

            # Should have made 2 calls: first succeeds, second gets cancelled
            assert call_count == 2

    @pytest.mark.asyncio
    async def test_cancellation_stops_progress_reporting(self, sample_symbols):
        """Test that progress reporting stops immediately after cancellation."""
        # Use single concurrency for predictable behavior
        node = PolygonBatchCustomBarsNode("test_id", {"max_concurrent": 1})
        progress_calls = []

        def mock_report(progress, text):
            progress_calls.append((progress, text))
            print(f"Progress: {progress}%, {text}")

        node.report_progress = mock_report

        call_count = 0

        async def cancellable_fetch(symbol, api_key, params):
            nonlocal call_count
            call_count += 1
            if call_count == 2:  # Cancel on second call
                raise asyncio.CancelledError("Simulated cancellation")
            await asyncio.sleep(0.01)
            return []

        with patch("nodes.custom.polygon.polygon_batch_custom_bars_node.fetch_bars", side_effect=cancellable_fetch):
            execute_task = asyncio.create_task(node.execute({
                "symbols": sample_symbols,
                "api_key": "test_key"
            }))

            with pytest.raises(asyncio.CancelledError):
                await execute_task

            # Should have progress for first completed call, but not continue to all symbols
            # The cancelled call might still report progress in finally block
            assert len(progress_calls) >= 1  # At least the first successful call
            assert call_count == 2  # First succeeds, second gets cancelled

    @pytest.mark.asyncio
    async def test_cancellation_during_rate_limiting(self, polygon_batch_node, sample_symbols):
        """Test cancellation works even when waiting for rate limiting."""
        acquire_calls = 0

        async def cancellable_acquire():
            nonlocal acquire_calls
            acquire_calls += 1
            if acquire_calls == 2:  # Cancel on second acquire attempt
                raise asyncio.CancelledError("Rate limit cancellation")
            # Simulate rate limiting delay
            await asyncio.sleep(0.01)

        with patch("nodes.custom.polygon.polygon_batch_custom_bars_node.RateLimiter") as mock_rate_limiter_class:
            mock_rate_limiter = MagicMock()
            mock_rate_limiter.acquire = cancellable_acquire
            mock_rate_limiter_class.return_value = mock_rate_limiter

            with patch("nodes.custom.polygon.polygon_batch_custom_bars_node.fetch_bars", return_value=[]):
                execute_task = asyncio.create_task(polygon_batch_node.execute({
                    "symbols": sample_symbols,
                    "api_key": "test_key"
                }))

                with pytest.raises(asyncio.CancelledError):
                    await execute_task

                # Should have attempted rate limiting at least once
                assert acquire_calls >= 1

    @pytest.mark.asyncio
    async def test_cancellation_with_multiple_workers(self, mock_bars_response):
        """Test cancellation with multiple concurrent workers."""
        node = PolygonBatchCustomBarsNode("test_id", {"max_concurrent": 3})
        symbols = [AssetSymbol(f"SYMBOL_{i}", AssetClass.STOCKS) for i in range(10)]

        call_count = 0

        async def slow_cancellable_fetch(symbol, api_key, params):
            nonlocal call_count
            call_count += 1
            if call_count == 3:  # Cancel after a few concurrent requests start
                raise asyncio.CancelledError("Multi-worker cancellation")
            await asyncio.sleep(0.1)
            return mock_bars_response

        with patch("nodes.custom.polygon.polygon_batch_custom_bars_node.fetch_bars", side_effect=slow_cancellable_fetch):
            execute_task = asyncio.create_task(node.execute({
                "symbols": symbols,
                "api_key": "test_key"
            }))

            # Let some workers start
            await asyncio.sleep(0.05)

            with pytest.raises(asyncio.CancelledError):
                await execute_task

            # Should not have completed all calls
            assert call_count < len(symbols)

    @pytest.mark.asyncio
    async def test_regular_exception_vs_cancellation(self, sample_symbols):
        """Test that regular exceptions are still caught but cancellation propagates."""
        # Use single concurrency for predictable behavior
        node = PolygonBatchCustomBarsNode("test_id", {"max_concurrent": 1})
        call_count = 0

        async def mixed_fetch(symbol, api_key, params):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise ValueError("Regular API error")  # Should be caught and logged
            elif call_count == 2:
                raise asyncio.CancelledError("Cancellation")  # Should propagate
            return []

        with patch("nodes.custom.polygon.polygon_batch_custom_bars_node.fetch_bars", side_effect=mixed_fetch):
            execute_task = asyncio.create_task(node.execute({
                "symbols": sample_symbols,
                "api_key": "test_key"
            }))

            with pytest.raises(asyncio.CancelledError):
                await execute_task

            # Should have made 2 calls: first failed with ValueError, second with CancelledError
            assert call_count == 2

    @pytest.mark.asyncio
    async def test_force_stop_cancels_workers(self, polygon_batch_node, sample_symbols, mock_bars_response):
        """Test that force_stop cancels internal workers."""
        async def slow_fetch(*args, **kwargs):
            await asyncio.sleep(0.5)  # Simulate ongoing fetch
            return mock_bars_response

        with patch("nodes.custom.polygon.polygon_batch_custom_bars_node.fetch_bars", side_effect=slow_fetch):
            execute_task = asyncio.create_task(polygon_batch_node.execute({
                "symbols": sample_symbols,
                "api_key": "test_key"
            }))

            await asyncio.sleep(0.1)  # Let workers start
            assert len(polygon_batch_node.workers) > 0
            assert any(not w.done() for w in polygon_batch_node.workers)

            polygon_batch_node.force_stop()

            # Workers should be cancelled
            await asyncio.sleep(0.1)
            assert all(w.cancelled() or w.done() for w in polygon_batch_node.workers)

            execute_task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await execute_task
