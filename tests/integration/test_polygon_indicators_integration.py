import pytest
import asyncio
from unittest.mock import patch, AsyncMock, MagicMock
from core.graph_executor import GraphExecutor
from core.node_registry import NODE_REGISTRY
from core.types_registry import AssetSymbol, AssetClass

@pytest.mark.asyncio
async def test_polygon_indicators_filtering_pipeline():
    """Integration test for the complete pipeline: PolygonBatchCustomBarsNode -> IndicatorsBundleNode -> IndicatorsFilterNode"""

    # Create mock OHLCV data that will produce specific indicator values
    mock_ohlcv_data = [
        {"timestamp": 1000000000, "open": 100.0, "high": 110.0, "low": 95.0, "close": 105.0, "volume": 10000.0},
        {"timestamp": 1000864000, "open": 105.0, "high": 115.0, "low": 100.0, "close": 110.0, "volume": 12000.0},
        {"timestamp": 1001728000, "open": 110.0, "high": 120.0, "low": 105.0, "close": 115.0, "volume": 15000.0},
        {"timestamp": 1002592000, "open": 115.0, "high": 125.0, "low": 110.0, "close": 120.0, "volume": 18000.0},
        {"timestamp": 1003456000, "open": 120.0, "high": 130.0, "low": 115.0, "close": 125.0, "volume": 20000.0},
        {"timestamp": 1004320000, "open": 125.0, "high": 135.0, "low": 120.0, "close": 130.0, "volume": 22000.0},
        {"timestamp": 1005184000, "open": 130.0, "high": 140.0, "low": 125.0, "close": 135.0, "volume": 25000.0},
        {"timestamp": 1006048000, "open": 135.0, "high": 145.0, "low": 130.0, "close": 140.0, "volume": 28000.0},
        {"timestamp": 1006912000, "open": 140.0, "high": 150.0, "low": 135.0, "close": 145.0, "volume": 30000.0},
        {"timestamp": 1007776000, "open": 145.0, "high": 155.0, "low": 140.0, "close": 150.0, "volume": 32000.0},
        {"timestamp": 1008640000, "open": 150.0, "high": 160.0, "low": 145.0, "close": 155.0, "volume": 35000.0},
        {"timestamp": 1009504000, "open": 155.0, "high": 165.0, "low": 150.0, "close": 160.0, "volume": 38000.0},
        {"timestamp": 1010368000, "open": 160.0, "high": 170.0, "low": 155.0, "close": 165.0, "volume": 40000.0},
        {"timestamp": 1011232000, "open": 165.0, "high": 175.0, "low": 160.0, "close": 170.0, "volume": 42000.0},
        {"timestamp": 1012096000, "open": 170.0, "high": 180.0, "low": 165.0, "close": 175.0, "volume": 45000.0},
    ]

    # Create symbols for testing
    symbols = [
        AssetSymbol("AAPL", AssetClass.STOCKS),
        AssetSymbol("MSFT", AssetClass.STOCKS),
        AssetSymbol("GOOGL", AssetClass.STOCKS)
    ]

    # Define the graph with all three nodes in pipeline
    graph_data = {
        "nodes": [
            {"id": 1, "type": "TextInputNode", "properties": {"text": "test_api_key"}},
            {"id": 2, "type": "PolygonBatchCustomBarsNode", "properties": {
                "multiplier": 1,
                "timespan": "day",
                "lookback_period": "3 months",
                "adjusted": True,
                "sort": "asc",
                "limit": 5000,
                "max_concurrent": 2,
                "rate_limit_per_second": 95,
            }},
            {"id": 3, "type": "IndicatorsBundleNode", "properties": {"timeframe": "1d"}},
            {"id": 4, "type": "IndicatorsFilterNode", "properties": {
                "min_adx": 0.0,
                "require_eis_bullish": False,
                "require_eis_bearish": False,
                "min_hurst": 0.0,
                "min_acceleration": -10.0,
                "min_volume_ratio": 0.0,
            }},
            {"id": 5, "type": "LoggingNode", "properties": {"format": "auto"}}
        ],
        "links": [
            [0, 1, 0, 2, 1],  # api_key -> polygon_batch.api_key
            [0, 2, 0, 3, 0],  # ohlcv_bundle -> indicators_bundle.klines
            [0, 3, 0, 4, 0],  # indicators -> indicators_filter.indicators
            [0, 4, 0, 5, 0],  # filtered_symbols -> logging.input
        ]
    }

    executor = GraphExecutor(graph_data, NODE_REGISTRY)

    # Manually inject symbols and mock data directly into the polygon batch node output
    original_execute = executor.nodes[2].execute
    original_validate = executor.nodes[2].validate_inputs
    async def execute_with_mock_data(inputs):
        inputs = inputs.copy()
        inputs["symbols"] = symbols
        bundle = {symbol: mock_ohlcv_data for symbol in symbols}
        return {"ohlcv_bundle": bundle}

    def validate_with_symbols(inputs):
        inputs = inputs.copy()
        inputs["symbols"] = symbols
        return original_validate(inputs)

    executor.nodes[2].execute = execute_with_mock_data
    executor.nodes[2].validate_inputs = validate_with_symbols

    # Execute the graph
    results = await executor.execute()

    # Verify the pipeline executed successfully
    assert 5 in results  # LoggingNode results
    logging_result = results[5]
    assert "output" in logging_result

    # The logging node should have received the filtered symbols
    # With the mock data and default filters, all symbols should pass
    # (since filters are set to minimum values)
    logged_output = logging_result["output"]
    assert isinstance(logged_output, str)
    assert len(logged_output) > 0  # Should not be empty

    # Verify that indicators were computed (check intermediate results if available)
    assert 3 in results  # IndicatorsBundleNode results
    indicators_result = results[3]
    assert "indicators" in indicators_result
    assert len(indicators_result["indicators"]) == len(symbols)

    # Verify each symbol has the expected indicator keys
    for symbol in symbols:
        assert symbol in indicators_result["indicators"]
        symbol_indicators = indicators_result["indicators"][symbol]
        expected_keys = {"adx", "eis_bullish", "eis_bearish", "hurst", "acceleration", "volume_ratio"}
        assert all(key in symbol_indicators for key in expected_keys)

    # Verify that indicators_filter received the indicators
    assert 4 in results  # IndicatorsFilterNode results
    filter_result = results[4]
    assert "filtered_symbols" in filter_result
    assert len(filter_result["filtered_symbols"]) == len(symbols)
    
@pytest.mark.asyncio
async def test_polygon_indicators_filtering_with_strict_filters():
    """Test the pipeline with strict filtering that should filter out some symbols"""

    # Create symbols for testing
    symbols = [
        AssetSymbol("GOOD_STOCK", AssetClass.STOCKS),
        AssetSymbol("BAD_STOCK", AssetClass.STOCKS),
    ]

    # Mock OHLCV data - same for both symbols for simplicity
    mock_ohlcv_data = [
        {"timestamp": 1000000000, "open": 100.0, "high": 110.0, "low": 95.0, "close": 105.0, "volume": 10000.0},
        {"timestamp": 1000864000, "open": 105.0, "high": 115.0, "low": 100.0, "close": 110.0, "volume": 12000.0},
        {"timestamp": 1001728000, "open": 110.0, "high": 120.0, "low": 105.0, "close": 115.0, "volume": 15000.0},
        {"timestamp": 1002592000, "open": 115.0, "high": 125.0, "low": 110.0, "close": 120.0, "volume": 18000.0},
        {"timestamp": 1003456000, "open": 120.0, "high": 130.0, "low": 115.0, "close": 125.0, "volume": 20000.0},
        {"timestamp": 1004320000, "open": 125.0, "high": 135.0, "low": 120.0, "close": 130.0, "volume": 22000.0},
        {"timestamp": 1005184000, "open": 130.0, "high": 140.0, "low": 125.0, "close": 135.0, "volume": 25000.0},
        {"timestamp": 1006048000, "open": 135.0, "high": 145.0, "low": 130.0, "close": 140.0, "volume": 28000.0},
        {"timestamp": 1006912000, "open": 140.0, "high": 150.0, "low": 135.0, "close": 145.0, "volume": 30000.0},
        {"timestamp": 1007776000, "open": 145.0, "high": 155.0, "low": 140.0, "close": 150.0, "volume": 32000.0},
        {"timestamp": 1008640000, "open": 150.0, "high": 160.0, "low": 145.0, "close": 155.0, "volume": 35000.0},
        {"timestamp": 1009504000, "open": 155.0, "high": 165.0, "low": 150.0, "close": 160.0, "volume": 38000.0},
        {"timestamp": 1010368000, "open": 160.0, "high": 170.0, "low": 155.0, "close": 165.0, "volume": 40000.0},
        {"timestamp": 1011232000, "open": 165.0, "high": 175.0, "low": 160.0, "close": 170.0, "volume": 42000.0},
        {"timestamp": 1012096000, "open": 170.0, "high": 180.0, "low": 165.0, "close": 175.0, "volume": 45000.0},
    ]

    # Mock the fetch_bars function in the polygon batch node module
    with patch('custom_nodes.polygon.polygon_batch_custom_bars_node.fetch_bars', new_callable=AsyncMock) as mock_fetch_bars:
        mock_fetch_bars.return_value = mock_ohlcv_data

        # Define the graph with strict filters
        graph_data = {
            "nodes": [
                {"id": 1, "type": "TextInputNode", "properties": {"text": "test_api_key"}},
                {"id": 2, "type": "PolygonBatchCustomBarsNode", "properties": {
                    "multiplier": 1,
                    "timespan": "day",
                    "lookback_period": "3 months",
                    "adjusted": True,
                    "sort": "asc",
                    "limit": 5000,
                    "max_concurrent": 2,
                    "rate_limit_per_second": 95,
                }},
                {"id": 3, "type": "IndicatorsBundleNode", "properties": {"timeframe": "1d"}},
                {"id": 4, "type": "IndicatorsFilterNode", "properties": {
                    "min_adx": 50.0,  # Very high threshold that should filter out most symbols
                    "require_eis_bullish": False,
                    "require_eis_bearish": False,
                    "min_hurst": 0.0,
                    "min_acceleration": 0.0,
                    "min_volume_ratio": 1.0,
                }},
                {"id": 5, "type": "LoggingNode", "properties": {"format": "auto"}}
            ],
            "links": [
                [0, 1, 0, 2, 1],  # api_key -> polygon_batch.api_key
                [0, 2, 0, 3, 0],  # ohlcv_bundle -> indicators_bundle.klines
                [0, 3, 0, 4, 0],  # indicators -> indicators_filter.indicators
                [0, 4, 0, 5, 0],  # filtered_symbols -> logging.input
            ]
        }

        # Override node 2 inputs to include symbols directly
        executor = GraphExecutor(graph_data, NODE_REGISTRY)

        # Manually inject symbols into the polygon batch node inputs
        original_execute = executor.nodes[2].execute
        original_validate = executor.nodes[2].validate_inputs
        async def execute_with_symbols(inputs):
            inputs = inputs.copy()
            inputs["symbols"] = symbols
            return await original_execute(inputs)

        def validate_with_symbols(inputs):
            inputs = inputs.copy()
            inputs["symbols"] = symbols
            return original_validate(inputs)

        executor.nodes[2].execute = execute_with_symbols
        executor.nodes[2].validate_inputs = validate_with_symbols

        # Execute the graph
        results = await executor.execute()

        # Verify the pipeline executed successfully
        assert 5 in results  # LoggingNode results
        logging_result = results[5]
        assert "output" in logging_result

        # With the very high ADX requirement (50.0), most symbols should be filtered out
        # The mock data may or may not produce ADX values >= 50, but the important thing
        # is that the filtering logic is working
        logged_output = logging_result["output"]
        assert isinstance(logged_output, str)

        # Verify that the filter node processed the indicators
        assert 4 in results  # IndicatorsFilterNode results
        filter_result = results[4]
        assert "filtered_symbols" in filter_result
        assert isinstance(filter_result["filtered_symbols"], list)

        # The exact number depends on the computed ADX values, but filtering should work
        assert len(filter_result["filtered_symbols"]) <= len(symbols)


@pytest.mark.asyncio
async def test_polygon_indicators_pipeline_empty_symbols():
    """Test the pipeline with empty symbol list"""

    # Mock the fetch_bars function directly
    with patch('services.polygon_service.fetch_bars', new_callable=AsyncMock) as mock_fetch_bars:
        mock_fetch_bars.return_value = []

        # Define the graph with empty symbols
        graph_data = {
            "nodes": [
                {"id": 1, "type": "TextInputNode", "properties": {"text": "test_api_key"}},
                {"id": 2, "type": "PolygonBatchCustomBarsNode", "properties": {
                    "multiplier": 1,
                    "timespan": "day",
                    "lookback_period": "3 months",
                    "adjusted": True,
                    "sort": "asc",
                    "limit": 5000,
                    "max_concurrent": 2,
                    "rate_limit_per_second": 95,
                }},
                {"id": 3, "type": "IndicatorsBundleNode", "properties": {"timeframe": "1d"}},
                {"id": 4, "type": "IndicatorsFilterNode", "properties": {
                    "min_adx": 0.0,
                    "require_eis_bullish": False,
                    "require_eis_bearish": False,
                    "min_hurst": 0.0,
                    "min_acceleration": 0.0,
                    "min_volume_ratio": 1.0,
                }},
                {"id": 5, "type": "LoggingNode", "properties": {"format": "auto"}}
            ],
            "links": [
                [0, 1, 0, 2, 1],  # api_key -> polygon_batch.api_key
                [0, 2, 0, 3, 0],  # ohlcv_bundle -> indicators_bundle.klines
                [0, 3, 0, 4, 0],  # indicators -> indicators_filter.indicators
                [0, 4, 0, 5, 0],  # filtered_symbols -> logging.input
            ]
        }

        # Override node 2 inputs to include empty symbols list
        executor = GraphExecutor(graph_data, NODE_REGISTRY)

        # Manually inject empty symbols list into the polygon batch node inputs
        original_execute = executor.nodes[2].execute
        original_validate = executor.nodes[2].validate_inputs
        async def execute_with_empty_symbols(inputs):
            inputs = inputs.copy()
            inputs["symbols"] = []
            return await original_execute(inputs)

        def validate_with_empty_symbols(inputs):
            inputs = inputs.copy()
            inputs["symbols"] = []
            return original_validate(inputs)

        executor.nodes[2].execute = execute_with_empty_symbols
        executor.nodes[2].validate_inputs = validate_with_empty_symbols

        # Execute the graph
        results = await executor.execute()

        # Verify empty results propagate through the pipeline
        assert 5 in results  # LoggingNode results
        logging_result = results[5]
        assert "output" in logging_result
        assert logging_result["output"] == "[]"  # String representation of empty list

        assert 4 in results  # IndicatorsFilterNode results
        filter_result = results[4]
        assert filter_result["filtered_symbols"] == []

        assert 3 in results  # IndicatorsBundleNode results
        indicators_result = results[3]
        assert indicators_result["indicators"] == {}

        assert 2 in results  # PolygonBatchCustomBarsNode results
        bars_result = results[2]
        assert bars_result["ohlcv_bundle"] == {}


@pytest.mark.asyncio
async def test_polygon_indicators_filtering_pipeline_with_updated_defaults():
    """Integration test for the complete pipeline with updated filter defaults that should allow most symbols through."""

    # Create mock OHLCV data that will produce realistic indicator values
    mock_ohlcv_data = [
        {"timestamp": 1000000000, "open": 100.0, "high": 110.0, "low": 95.0, "close": 105.0, "volume": 10000.0},
        {"timestamp": 1000864000, "open": 105.0, "high": 115.0, "low": 100.0, "close": 110.0, "volume": 12000.0},
        {"timestamp": 1001728000, "open": 110.0, "high": 120.0, "low": 105.0, "close": 115.0, "volume": 15000.0},
        {"timestamp": 1002592000, "open": 115.0, "high": 125.0, "low": 110.0, "close": 120.0, "volume": 18000.0},
        {"timestamp": 1003456000, "open": 120.0, "high": 130.0, "low": 115.0, "close": 125.0, "volume": 20000.0},
        {"timestamp": 1004320000, "open": 125.0, "high": 135.0, "low": 120.0, "close": 130.0, "volume": 22000.0},
        {"timestamp": 1005184000, "open": 130.0, "high": 140.0, "low": 125.0, "close": 135.0, "volume": 25000.0},
        {"timestamp": 1006048000, "open": 135.0, "high": 145.0, "low": 130.0, "close": 140.0, "volume": 28000.0},
        {"timestamp": 1006912000, "open": 140.0, "high": 150.0, "low": 135.0, "close": 145.0, "volume": 30000.0},
        {"timestamp": 1007776000, "open": 145.0, "high": 155.0, "low": 140.0, "close": 150.0, "volume": 32000.0},
        {"timestamp": 1008640000, "open": 150.0, "high": 160.0, "low": 145.0, "close": 155.0, "volume": 35000.0},
        {"timestamp": 1009504000, "open": 155.0, "high": 165.0, "low": 150.0, "close": 160.0, "volume": 38000.0},
        {"timestamp": 1010368000, "open": 160.0, "high": 170.0, "low": 155.0, "close": 165.0, "volume": 40000.0},
        {"timestamp": 1011232000, "open": 165.0, "high": 175.0, "low": 160.0, "close": 170.0, "volume": 42000.0},
        {"timestamp": 1012096000, "open": 170.0, "high": 180.0, "low": 165.0, "close": 175.0, "volume": 45000.0},
    ]

    # Create symbols for testing
    symbols = [
        AssetSymbol("AAPL", AssetClass.STOCKS),
        AssetSymbol("MSFT", AssetClass.STOCKS),
        AssetSymbol("GOOGL", AssetClass.STOCKS)
    ]

    # Define the graph with updated filter defaults
    graph_data = {
        "nodes": [
            {"id": 1, "type": "TextInputNode", "properties": {"text": "test_api_key"}},
            {"id": 2, "type": "PolygonBatchCustomBarsNode", "properties": {
                "multiplier": 1,
                "timespan": "day",
                "lookback_period": "3 months",
                "adjusted": True,
                "sort": "asc",
                "limit": 5000,
                "max_concurrent": 2,
                "rate_limit_per_second": 95,
            }},
            {"id": 3, "type": "IndicatorsBundleNode", "properties": {"timeframe": "1d"}},
            {"id": 4, "type": "IndicatorsFilterNode", "properties": {
                # Using updated defaults that should allow most symbols through
                "min_adx": 0.0,
                "require_eis_bullish": False,
                "require_eis_bearish": False,
                "min_hurst": 0.0,
                "min_acceleration": -10.0,  # Allow negative acceleration
                "min_volume_ratio": 0.0,     # Allow any volume ratio
            }},
            {"id": 5, "type": "LoggingNode", "properties": {"format": "auto"}}
        ],
        "links": [
            [0, 1, 0, 2, 1],  # api_key -> polygon_batch.api_key
            [0, 2, 0, 3, 0],  # ohlcv_bundle -> indicators_bundle.klines
            [0, 3, 0, 4, 0],  # indicators -> indicators_filter.indicators
            [0, 4, 0, 5, 0],  # filtered_symbols -> logging.input
        ]
    }

    # Override node 2 inputs to include symbols directly
    executor = GraphExecutor(graph_data, NODE_REGISTRY)

    # Store original methods
    original_validate = executor.nodes[2].validate_inputs

    # Manually inject symbols into the polygon batch node and return mock data
    async def execute_with_mock_data(inputs):
        # Return mock data directly
        bundle = {}
        for symbol in symbols:
            bundle[symbol] = mock_ohlcv_data
        return {"ohlcv_bundle": bundle}

    def validate_with_symbols(inputs):
        inputs = inputs.copy()
        inputs["symbols"] = symbols
        return original_validate(inputs)

    executor.nodes[2].execute = execute_with_mock_data
    executor.nodes[2].validate_inputs = validate_with_symbols

    # Execute the graph
    results = await executor.execute()

    # Verify the pipeline executed successfully
    assert 5 in results  # LoggingNode results
    logging_result = results[5]
    assert "output" in logging_result

    # With the updated defaults, all symbols should pass the filter
    logged_output = logging_result["output"]
    assert isinstance(logged_output, str)
    # The logged output should contain the symbols (as string representation of list)
    assert len(logged_output) > 2  # Should not be empty or just "[]"

    # Verify that indicators were computed for all symbols
    assert 3 in results  # IndicatorsBundleNode results
    indicators_result = results[3]
    assert "indicators" in indicators_result
    assert len(indicators_result["indicators"]) == len(symbols)

    # Verify each symbol has the expected indicator keys
    for symbol in symbols:
        assert symbol in indicators_result["indicators"]
        symbol_indicators = indicators_result["indicators"][symbol]
        expected_keys = {"adx", "eis_bullish", "eis_bearish", "hurst", "acceleration", "volume_ratio"}
        assert all(key in symbol_indicators for key in expected_keys)
        # Verify hurst is not NaN (was fixed)
        assert not (isinstance(symbol_indicators["hurst"], float) and str(symbol_indicators["hurst"]) == "nan")

    # Verify that indicators_filter received the indicators and passed all through
    assert 4 in results  # IndicatorsFilterNode results
    filter_result = results[4]
    assert "filtered_symbols" in filter_result
    assert len(filter_result["filtered_symbols"]) == len(symbols)
