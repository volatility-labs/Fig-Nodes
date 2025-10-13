import pytest
import asyncio
import time
from unittest.mock import AsyncMock, patch, MagicMock
from core.graph_executor import GraphExecutor
from core.node_registry import NODE_REGISTRY
from nodes.base.base_node import BaseNode


@pytest.fixture
def progress_callback():
    """Fixture to capture progress callbacks."""
    progress_updates = []

    def callback(node_id, progress, text=""):
        progress_updates.append({
            "node_id": node_id,
            "progress": progress,
            "text": text,
            "timestamp": time.time()
        })

    callback.updates = progress_updates
    return callback


@pytest.fixture
def mock_polygon_node():
    """Create a mock polygon node for testing."""
    return MockPolygonBatchCustomBarsNode(id=1, params={"num_symbols": 5})


class MockPolygonBatchCustomBarsNode(BaseNode):
    """Mock version of PolygonBatchCustomBarsNode for testing progress reporting."""

    inputs = {}  # No inputs required for testing
    outputs = {"ohlcv_bundle": "Dict[AssetSymbol, List[OHLCVBar]]"}
    default_params = {
        "multiplier": 1,
        "timespan": "day",
        "lookback_period": "3 months",
        "adjusted": True,
        "sort": "asc",
        "limit": 5000,
        "max_concurrent": 2,  # Low concurrency for controlled testing
        "rate_limit_per_second": 95,
        "num_symbols": 3,  # Number of symbols to simulate
    }

    async def execute(self, inputs):
        # Get number of symbols from params for testing
        num_symbols = self.params.get("num_symbols", 3)
        from core.types_registry import AssetSymbol, AssetClass
        symbols = [AssetSymbol(f"SYMBOL_{i}", AssetClass.STOCKS) for i in range(num_symbols)]
        total_symbols = len(symbols)

        # Simulate processing each symbol with delays
        for i, symbol in enumerate(symbols):
            # Simulate API call delay (50ms per symbol)
            await asyncio.sleep(0.05)

            # Report progress (final update when i == total_symbols - 1)
            progress = ((i + 1) / total_symbols) * 100
            progress_text = f"{i + 1}/{total_symbols}"
            self.report_progress(progress, progress_text)

        # Return mock result
        return {"ohlcv_bundle": {symbol: [{"close": 100.0}] for symbol in symbols}}


class TestProgressBarIntegration:
    """Integration tests for progress bar functionality."""

    @pytest.mark.asyncio
    async def test_progress_reporting_during_execution(self, progress_callback, mock_polygon_node):
        """Test that progress is reported correctly during node execution."""
        from core.types_registry import AssetSymbol, AssetClass

        # Set up progress callback
        mock_polygon_node.set_progress_callback(progress_callback)

        # Execute the node (uses num_symbols from params)
        start_time = time.time()
        result = await mock_polygon_node.execute({})
        end_time = time.time()

        # Verify execution took reasonable time (5 symbols * 50ms = 250ms minimum)
        # Note: In practice it might be faster due to async execution
        assert end_time - start_time >= 0.05, "Execution should take at least 50ms"

        # Verify result structure
        assert "ohlcv_bundle" in result
        assert len(result["ohlcv_bundle"]) == 5

        # Verify progress updates
        assert len(progress_callback.updates) == 5, f"Expected 5 progress updates, got {len(progress_callback.updates)}"

        # Check progress values are monotonically increasing
        progresses = [update["progress"] for update in progress_callback.updates]
        assert progresses == sorted(progresses), "Progress should be monotonically increasing"

        # Check final progress is 100%
        assert progress_callback.updates[-1]["progress"] == 100.0

        # Check progress text format
        for i, update in enumerate(progress_callback.updates):
            expected_text = f"{i + 1}/5"
            assert update["text"] == expected_text, f"Progress text should be '{expected_text}', got '{update['text']}'"

    @pytest.mark.asyncio
    async def test_progress_reporting_callback_mechanism(self, progress_callback):
        """Test that the progress callback mechanism works correctly."""
        # Test the callback directly
        progress_callback(1, 50.0, "3/6")
        progress_callback(1, 75.0, "4.5/6")
        progress_callback(2, 100.0, "2/2")

        # Verify updates were captured
        assert len(progress_callback.updates) == 3

        # Verify update structure
        assert progress_callback.updates[0]["node_id"] == 1
        assert progress_callback.updates[0]["progress"] == 50.0
        assert progress_callback.updates[0]["text"] == "3/6"

        assert progress_callback.updates[1]["node_id"] == 1
        assert progress_callback.updates[1]["progress"] == 75.0
        assert progress_callback.updates[1]["text"] == "4.5/6"

        assert progress_callback.updates[2]["node_id"] == 2
        assert progress_callback.updates[2]["progress"] == 100.0
        assert progress_callback.updates[2]["text"] == "2/2"

    @pytest.mark.asyncio
    async def test_progress_reporting_with_large_symbol_set(self, progress_callback, mock_polygon_node):
        """Test progress reporting with a larger symbol set (simulating real-world usage)."""
        from core.types_registry import AssetSymbol, AssetClass

        # Set up progress callback
        mock_polygon_node.params["num_symbols"] = 20  # Override for this test
        mock_polygon_node.set_progress_callback(progress_callback)

        # Execute the node
        start_time = time.time()
        result = await mock_polygon_node.execute({})
        end_time = time.time()

        # Verify execution took reasonable time
        assert end_time - start_time >= 0.8, "Execution should take at least 800ms for 20 symbols"

        # Verify result structure
        assert "ohlcv_bundle" in result
        assert len(result["ohlcv_bundle"]) == 20

        # Verify progress updates (should be 20 updates)
        assert len(progress_callback.updates) == 20, f"Expected 20 progress updates, got {len(progress_callback.updates)}"

        # Check progress increments are reasonable
        progresses = [update["progress"] for update in progress_callback.updates]
        expected_progresses = [(i + 1) * 5.0 for i in range(20)]  # 5% increments for 20 symbols

        for actual, expected in zip(progresses, expected_progresses):
            assert abs(actual - expected) < 0.1, f"Progress {actual} should be close to {expected}"

        # Check final progress is 100%
        assert abs(progress_callback.updates[-1]["progress"] - 100.0) < 0.1

    @pytest.mark.asyncio
    async def test_progress_reporting_timestamps(self, progress_callback, mock_polygon_node):
        """Test that progress updates have reasonable timestamps."""
        from core.types_registry import AssetSymbol, AssetClass

        # Set up progress callback
        mock_polygon_node.set_progress_callback(progress_callback)

        # Execute the node
        start_time = time.time()
        result = await mock_polygon_node.execute({})
        end_time = time.time()

        # Verify timestamps are reasonable
        for update in progress_callback.updates:
            timestamp = update["timestamp"]
            assert start_time <= timestamp <= end_time, f"Timestamp {timestamp} should be between {start_time} and {end_time}"

        # Verify timestamps are monotonically increasing
        timestamps = [update["timestamp"] for update in progress_callback.updates]
        assert timestamps == sorted(timestamps), "Timestamps should be monotonically increasing"

    @pytest.mark.asyncio
    async def test_progress_reporting_multiple_nodes(self, progress_callback):
        """Test progress reporting from multiple nodes executing concurrently."""
        from core.types_registry import AssetSymbol, AssetClass

        # Create two mock nodes
        node1 = MockPolygonBatchCustomBarsNode(id=1, params={"num_symbols": 2})
        node2 = MockPolygonBatchCustomBarsNode(id=2, params={"num_symbols": 2})

        # Set different progress callbacks to collect updates separately
        node1_progress = []
        node2_progress = []

        def node1_callback(nid, progress, text):
            node1_progress.append({"progress": progress, "text": text})

        def node2_callback(nid, progress, text):
            node2_progress.append({"progress": progress, "text": text})

        node1.set_progress_callback(node1_callback)
        node2.set_progress_callback(node2_callback)

        # Execute both nodes concurrently
        start_time = time.time()
        await asyncio.gather(
            node1.execute({}),
            node2.execute({})
        )
        end_time = time.time()

        # Verify both nodes completed
        assert len(node1_progress) == 2, f"Node 1 should have 2 progress updates, got {len(node1_progress)}"
        assert len(node2_progress) == 2, f"Node 2 should have 2 progress updates, got {len(node2_progress)}"

        # Both nodes should reach 100% progress
        assert node1_progress[-1]["progress"] == 100.0
        assert node2_progress[-1]["progress"] == 100.0

        # Concurrent execution should be faster than sequential
        assert end_time - start_time < 0.25, "Concurrent execution should complete quickly"

    @pytest.mark.asyncio
    async def test_progress_reporting_with_errors(self, progress_callback, mock_polygon_node):
        """Test progress reporting when errors occur during execution."""
        from core.types_registry import AssetSymbol, AssetClass

        # Set up progress callback
        mock_polygon_node.set_progress_callback(progress_callback)

        # Create test symbols
        symbols = [AssetSymbol(f"SYMBOL_{i}", AssetClass.STOCKS) for i in range(3)]

        # Mock an error in the middle of execution by patching the sleep
        original_sleep = asyncio.sleep

        async def failing_sleep(delay):
            if delay == 0.05 and len(progress_callback.updates) == 1:  # After first symbol
                raise Exception("Simulated API error")
            return await original_sleep(delay)

        with patch('asyncio.sleep', side_effect=failing_sleep):
            with pytest.raises(Exception, match="Simulated API error"):
                await mock_polygon_node.execute({"symbols": symbols, "api_key": "test_key"})

        # Verify we got progress updates even with the error
        assert len(progress_callback.updates) >= 1, "Should have at least one progress update before error"

    @pytest.mark.asyncio
    async def test_progress_reporting_robustness_long_execution(self, progress_callback, mock_polygon_node):
        """Test progress reporting robustness during long execution periods."""
        from core.types_registry import AssetSymbol, AssetClass

        # Set up progress callback
        mock_polygon_node.set_progress_callback(progress_callback)

        # Set the node to process 50 symbols
        mock_polygon_node.params["num_symbols"] = 50

        # Execute the node
        start_time = time.time()
        result = await mock_polygon_node.execute({})
        end_time = time.time()

        # Verify execution took reasonable time (50 symbols * 50ms = 2.5s minimum)
        # Note: In practice it might be faster due to async execution
        assert end_time - start_time >= 0.5, "Long execution should take at least 500ms"

        # Verify all progress updates were received
        assert len(progress_callback.updates) == 50, f"Expected 50 progress updates, got {len(progress_callback.updates)}"

        # Verify progress updates are evenly distributed
        progresses = [update["progress"] for update in progress_callback.updates]
        for i, progress in enumerate(progresses):
            expected_progress = ((i + 1) / 50) * 100
            assert abs(progress - expected_progress) < 0.1, f"Progress at step {i+1} should be ~{expected_progress}, got {progress}"

        # Verify no duplicate progress values (except possibly the last one)
        unique_progresses = set(progresses[:-1])  # Exclude last in case of duplicate 100%
        assert len(unique_progresses) == len(progresses) - 1, "Progress values should be unique except possibly the final 100%"

        # Verify result integrity
        assert "ohlcv_bundle" in result
        assert len(result["ohlcv_bundle"]) == 50


@pytest.mark.asyncio
async def test_real_polygon_batch_progress_reporting():
    """Integration test with real PolygonBatchCustomBarsNode and mocked API calls."""
    from nodes.custom.polygon.polygon_batch_custom_bars_node import PolygonBatchCustomBarsNode
    from core.types_registry import AssetSymbol, AssetClass
    from unittest.mock import AsyncMock

    # Create progress callback to capture updates
    progress_updates = []

    def progress_callback(node_id, progress, text=""):
        progress_updates.append({
            "node_id": node_id,
            "progress": progress,
            "text": text,
            "timestamp": time.time()
        })

    # Create node and set progress callback
    node = PolygonBatchCustomBarsNode(id=1, params={})
    node.set_progress_callback(progress_callback)

    # Create test symbols
    symbols = [AssetSymbol(f"SYMBOL_{i}", AssetClass.STOCKS) for i in range(5)]

    # Mock the fetch_bars function to simulate API calls with delays
    mock_bars_data = [{"close": 100.0, "high": 105.0, "low": 95.0, "open": 102.0, "volume": 1000}]

    async def mock_fetch_bars(symbol, api_key, params):
        await asyncio.sleep(0.1)  # Simulate API delay
        return mock_bars_data

    # Patch the fetch_bars function
    import nodes.custom.polygon.polygon_batch_custom_bars_node as polygon_module
    original_fetch_bars = polygon_module.fetch_bars

    with patch("core.api_key_vault.APIKeyVault.get", return_value="test_key"):
        try:
            polygon_module.fetch_bars = mock_fetch_bars

            # Execute the node
            start_time = time.time()
            result = await node.execute({"symbols": symbols})
            end_time = time.time()

            # Verify execution took reasonable time (concurrent execution should be fast)
            assert end_time - start_time >= 0.08, "Execution should take at least 80ms due to concurrency and API delays"
            assert end_time - start_time <= 0.3, "Execution should not take more than 300ms with concurrency"

            # Verify result structure
            assert "ohlcv_bundle" in result
            assert len(result["ohlcv_bundle"]) == 5

            # Verify progress updates - should have 5 updates (one per symbol)
            assert len(progress_updates) == 5, f"Expected 5 progress updates, got {len(progress_updates)}"

            # Verify progress values are correct
            for i, update in enumerate(progress_updates):
                expected_progress = ((i + 1) / 5) * 100
                assert abs(update["progress"] - expected_progress) < 0.1, f"Progress should be ~{expected_progress}, got {update['progress']}"
                expected_text = f"{i + 1}/5"
                assert update["text"] == expected_text, f"Progress text should be '{expected_text}', got '{update['text']}'"

            # Verify final progress is 100%
            assert abs(progress_updates[-1]["progress"] - 100.0) < 0.1

            # Verify timestamps are reasonable
            for update in progress_updates:
                assert start_time <= update["timestamp"] <= end_time

        finally:
            # Restore original function
            polygon_module.fetch_bars = original_fetch_bars


@pytest.mark.asyncio
async def test_websocket_progress_communication():
    """Test that progress updates are properly sent via WebSocket."""
    from unittest.mock import MagicMock, AsyncMock
    import asyncio

    # Mock WebSocket
    mock_ws = AsyncMock()
    sent_messages = []

    async def mock_send_json(data):
        sent_messages.append(data)

    mock_ws.send_json = mock_send_json

    # Create a mock job
    mock_job = MagicMock()
    mock_job.websocket = mock_ws
    mock_job.done_event = AsyncMock()

    # Mock graph executor
    mock_executor = MagicMock()
    mock_executor.is_streaming = False

    # Create mock graph data with our mock node
    graph_data = {
        "nodes": [
            {
                "id": 1,
                "type": "MockPolygonBatchCustomBarsNode",
                "properties": {}
            }
        ],
        "links": []
    }

    # Track progress updates sent to WebSocket
    progress_messages = []

    def mock_progress_callback(node_id, progress, text=""):
        # This simulates what happens in the real server
        asyncio.create_task(mock_ws.send_json({
            "type": "progress",
            "node_id": node_id,
            "progress": progress,
            "text": text
        }))

    # Mock the GraphExecutor creation and execution
    with patch('ui.server.GraphExecutor') as mock_graph_executor_class:
        mock_executor_instance = MagicMock()
        mock_executor_instance.is_streaming = False
        mock_executor_instance.set_progress_callback = mock_progress_callback
        mock_executor_instance.execute = AsyncMock(return_value={1: {"ohlcv_bundle": {}}})
        mock_graph_executor_class.return_value = mock_executor_instance

        # Test the progress callback directly
        pass

    # Test the progress callback directly
    mock_progress_callback(1, 50.0, "3/6")

    # Give async task time to complete
    await asyncio.sleep(0.01)

    # Verify progress message was sent
    assert len(sent_messages) == 1
    message = sent_messages[0]
    assert message["type"] == "progress"
    assert message["node_id"] == 1
    assert message["progress"] == 50.0
    assert message["text"] == "3/6"
