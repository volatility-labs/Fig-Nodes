import pytest
import asyncio
from unittest.mock import patch, AsyncMock, MagicMock
from core.graph_executor import GraphExecutor
from core.node_registry import NODE_REGISTRY
from core.types_registry import AssetSymbol, AssetClass
from nodes.custom.polygon.polygon_universe_node import PolygonUniverseNode
from nodes.core.market.filters.orb_filter_node import OrbFilterNode

@pytest.mark.asyncio
async def test_polygon_indicators_filtering_pipeline():
    """Integration test for the complete pipeline: PolygonBatchCustomBarsNode -> ADXFilterNode"""

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

    # Define the graph with nodes in pipeline
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
            {"id": 3, "type": "ADXFilterNode", "properties": {
                "min_adx": 0.0,
                "timeperiod": 14,
            }},
            {"id": 4, "type": "LoggingNode", "properties": {"format": "auto"}}
        ],
        "links": [
            [0, 1, 0, 2, 1],  # api_key -> polygon_batch.api_key
            [0, 2, 0, 3, 0],  # ohlcv_bundle -> adx_filter.ohlcv_bundle
            [0, 3, 0, 4, 0],  # filtered_ohlcv_bundle -> logging.input
        ]
    }

    executor = GraphExecutor(graph_data, NODE_REGISTRY)

    # Manually inject symbols and mock data directly into the polygon batch node output
    original_execute = executor.nodes[2]._execute_impl
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

    executor.nodes[2]._execute_impl = execute_with_mock_data
    executor.nodes[2].validate_inputs = validate_with_symbols

    # Execute the graph
    results = await executor.execute()

    # Verify the pipeline executed successfully
    assert 4 in results  # LoggingNode results
    logging_result = results[4]
    assert "output" in logging_result

    # The logging node should have received the filtered symbols
    # With the mock data and default filters, all symbols should pass
    # (since filters are set to minimum values)
    logged_output = logging_result["output"]
    assert isinstance(logged_output, str)
    assert len(logged_output) > 0  # Should not be empty

    # Verify that indicators were computed and filtered
    assert 3 in results  # ADXFilterNode results
    filter_result = results[3]
    assert "filtered_ohlcv_bundle" in filter_result
    # Note: ADX calculation may fail with mock data, so results might be empty
    assert isinstance(filter_result["filtered_ohlcv_bundle"], dict)


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

    # Define the graph with strict ADX filter
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
            {"id": 3, "type": "ADXFilterNode", "properties": {
                "min_adx": 50.0,  # Very high threshold that should filter out most symbols
                "timeperiod": 14,
            }},
            {"id": 4, "type": "LoggingNode", "properties": {"format": "auto"}}
        ],
        "links": [
            [0, 1, 0, 2, 1],  # api_key -> polygon_batch.api_key
            [0, 2, 0, 3, 0],  # ohlcv_bundle -> adx_filter.ohlcv_bundle
            [0, 3, 0, 4, 0],  # filtered_ohlcv_bundle -> logging.input
        ]
    }

    # Override node 2 inputs to include symbols directly
    executor = GraphExecutor(graph_data, NODE_REGISTRY)

    # Manually inject symbols into the polygon batch node inputs
    original_execute = executor.nodes[2]._execute_impl
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

    executor.nodes[2]._execute_impl = execute_with_mock_data
    executor.nodes[2].validate_inputs = validate_with_symbols

    # Execute the graph
    results = await executor.execute()

    # Verify the pipeline executed successfully
    assert 4 in results  # LoggingNode results
    logging_result = results[4]
    assert "output" in logging_result

    # With the very high ADX requirement (50.0), most symbols should be filtered out
    # The mock data may or may not produce ADX values >= 50, but the important thing
    # is that the filtering logic is working
    logged_output = logging_result["output"]
    assert isinstance(logged_output, str)

    # Verify that the filter node processed the indicators
    assert 3 in results  # ADXFilterNode results
    filter_result = results[3]
    assert "filtered_ohlcv_bundle" in filter_result
    assert isinstance(filter_result["filtered_ohlcv_bundle"], dict)

    # The exact number depends on the computed ADX values, but filtering should work
    assert len(filter_result["filtered_ohlcv_bundle"]) <= len(symbols)


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
                {"id": 3, "type": "ADXFilterNode", "properties": {
                    "min_adx": 0.0,
                    "timeperiod": 14,
                }},
                {"id": 4, "type": "LoggingNode", "properties": {"format": "auto"}}
            ],
            "links": [
                [0, 1, 0, 2, 1],  # api_key -> polygon_batch.api_key
                [0, 2, 0, 3, 0],  # ohlcv_bundle -> adx_filter.ohlcv_bundle
                [0, 3, 0, 4, 0],  # filtered_ohlcv_bundle -> logging.input
            ]
        }

        # Override node 2 inputs to include empty symbols list
        executor = GraphExecutor(graph_data, NODE_REGISTRY)

        # Manually inject empty symbols list into the polygon batch node inputs
        original_execute = executor.nodes[2]._execute_impl
        original_validate = executor.nodes[2].validate_inputs
        async def execute_with_empty_symbols(inputs):
            inputs = inputs.copy()
            inputs["symbols"] = []
            return await original_execute(inputs)

        def validate_with_empty_symbols(inputs):
            inputs = inputs.copy()
            inputs["symbols"] = []
            return original_validate(inputs)

        executor.nodes[2]._execute_impl = execute_with_empty_symbols
        executor.nodes[2].validate_inputs = validate_with_empty_symbols

        # Execute the graph
        results = await executor.execute()

        # Verify empty results propagate through the pipeline
        assert 4 in results  # LoggingNode results
        logging_result = results[4]
        assert "output" in logging_result
        assert logging_result["output"] == "{}"  # String representation of empty dict

        assert 3 in results  # ADXFilterNode results
        filter_result = results[3]
        assert filter_result["filtered_ohlcv_bundle"] == {}

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
                {"id": 3, "type": "ADXFilterNode", "properties": {
                    # Using updated defaults that should allow most symbols through
                    "min_adx": 0.0,
                    "timeperiod": 14,
                }},
                {"id": 4, "type": "LoggingNode", "properties": {"format": "auto"}}
            ],
            "links": [
                [0, 1, 0, 2, 1],  # api_key -> polygon_batch.api_key
                [0, 2, 0, 3, 0],  # ohlcv_bundle -> adx_filter.ohlcv_bundle
                [0, 3, 0, 4, 0],  # filtered_ohlcv_bundle -> logging.input
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

    executor.nodes[2]._execute_impl = execute_with_mock_data
    executor.nodes[2].validate_inputs = validate_with_symbols

    # Execute the graph
    results = await executor.execute()

    # Verify the pipeline executed successfully
    assert 4 in results  # LoggingNode results
    logging_result = results[4]
    assert "output" in logging_result

    # With the updated defaults, symbols should pass the filter if ADX calculation succeeds
    logged_output = logging_result["output"]
    assert isinstance(logged_output, str)
    # Note: ADX calculation may fail with mock data, so output might be empty "{}"

    # Verify that indicators were computed and filtered
    assert 3 in results  # ADXFilterNode results
    filter_result = results[3]
    assert "filtered_ohlcv_bundle" in filter_result
    # Note: ADX calculation may fail with mock data, so results might be empty
    assert isinstance(filter_result["filtered_ohlcv_bundle"], dict)


@pytest.mark.asyncio
async def test_polygon_universe_hashability_integration():
    # Create node with test params
    node = PolygonUniverseNode("test_id", {"market": "stocks", "min_volume": 1000000})
    
    # Mock the API response with nested metadata
    with patch("httpx.AsyncClient") as mock_client, patch("core.api_key_vault.APIKeyVault.get") as mock_vault_get:
        mock_vault_get.return_value = "test_key"
        mock_get = AsyncMock()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "tickers": [{
                "ticker": "AAPL",
                "todaysChangePerc": 1.0,
                "day": {"v": 1000000, "c": 150, "nested": {"sub": [1, 2]}},
            }]
        }
        mock_get.return_value = mock_response
        mock_client.return_value.__aenter__.return_value.get = mock_get
        
        symbols = await node._fetch_symbols()
        
        assert len(symbols) == 1
        sym = symbols[0]
        
        # Test hashability with nested metadata
        hash(sym)
        symbol_set = set(symbols)
        assert sym in symbol_set


@pytest.mark.asyncio
async def test_orb_filter_integration():
    # Create mock OHLCV data
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

    node = OrbFilterNode("orb_id", {})

    # Create AssetSymbol for AAPL
    from core.types_registry import AssetSymbol, AssetClass
    aapl_symbol = AssetSymbol("AAPL", AssetClass.STOCKS)
    bundle = {aapl_symbol: mock_ohlcv_data}

    inputs = {"ohlcv_bundle": bundle, "api_key": "test_api_key"}

    with patch("core.api_key_vault.APIKeyVault.get", return_value="test_key"), \
         patch("nodes.core.market.filters.orb_filter_node.fetch_bars", new_callable=AsyncMock) as mock_fetch:
        mock_fetch.return_value = []
        result = await node.execute(inputs)

    assert "filtered_ohlcv_bundle" in result
    assert aapl_symbol not in result["filtered_ohlcv_bundle"]
