import pytest
import pandas as pd
from typing import Dict, Any, List
from nodes.core.market.filters.sma_crossover_filter_node import SMACrossoverFilterNode
from nodes.core.market.filters.adx_filter_node import ADXFilterNode
from nodes.core.market.filters.rsi_filter_node import RSIFilterNode
from core.types_registry import AssetSymbol, AssetClass, OHLCVBar
from core.types_registry import IndicatorType


@pytest.fixture
def sample_symbols():
    return [
        AssetSymbol("AAPL", AssetClass.STOCKS),
        AssetSymbol("BTC", AssetClass.CRYPTO),
        AssetSymbol("ETH", AssetClass.CRYPTO),
        AssetSymbol("TSLA", AssetClass.STOCKS),
    ]


@pytest.fixture
def sample_ohlcv_bundle(sample_symbols):
    """Sample OHLCV bundle for testing."""
    # Create sample OHLCV data for each symbol
    base_timestamp = 1640995200000  # 2022-01-01 00:00:00 UTC

    # AAPL: Strong uptrend with SMA crossover
    aapl_data = []
    for i in range(100):
        timestamp = base_timestamp + (i * 86400000)  # Daily bars
        # Create upward trending data
        base_price = 150 + (i * 0.5)  # Trending up
        aapl_data.append(OHLCVBar(
            timestamp=timestamp,
            open=base_price,
            high=base_price + 2,
            low=base_price - 1,
            close=base_price + 1,
            volume=1000000 + (i * 10000)
        ))

    # BTC: Volatile but trending down
    btc_data = []
    for i in range(100):
        timestamp = base_timestamp + (i * 86400000)
        base_price = 50000 - (i * 50)  # Trending down
        btc_data.append(OHLCVBar(
            timestamp=timestamp,
            open=base_price,
            high=base_price + 500,
            low=base_price - 300,
            close=base_price - 100,
            volume=20000000 + (i * 500000)
        ))

    # ETH: Sideways movement
    eth_data = []
    for i in range(100):
        timestamp = base_timestamp + (i * 86400000)
        base_price = 3000 + (i % 20) * 10  # Sideways with small oscillations
        eth_data.append(OHLCVBar(
            timestamp=timestamp,
            open=base_price,
            high=base_price + 50,
            low=base_price - 30,
            close=base_price + 10,
            volume=15000000 + (i * 200000)
        ))

    # TSLA: Strong uptrend, higher ADX
    tsla_data = []
    for i in range(100):
        timestamp = base_timestamp + (i * 86400000)
        base_price = 200 + (i * 2)  # Strong uptrend
        tsla_data.append(OHLCVBar(
            timestamp=timestamp,
            open=base_price,
            high=base_price + 10,
            low=base_price - 5,
            close=base_price + 8,
            volume=5000000 + (i * 50000)
        ))

    return {
        sample_symbols[0]: aapl_data,   # AAPL: Should pass SMA crossover
        sample_symbols[1]: btc_data,    # BTC: Should fail most filters
        sample_symbols[2]: eth_data,    # ETH: Should pass RSI filter (neutral)
        sample_symbols[3]: tsla_data,   # TSLA: Should pass ADX and SMA filters
    }


@pytest.fixture
def sample_ohlcv_bars():
    base_timestamp = 1640995200000
    return [
        OHLCVBar(
            timestamp=base_timestamp + i * 86400000,
            open=100 + i,
            high=110 + i,
            low=90 + i,
            close=105 + i,
            volume=1000
        ) for i in range(20)
    ]


class TestSMACrossoverFilterNode:
    """Tests for SMA Crossover Filter Node."""

    @pytest.fixture
    def sma_filter_node(self):
        return SMACrossoverFilterNode("sma_filter_id", {})

    @pytest.mark.asyncio
    async def test_execute_empty_inputs(self, sma_filter_node):
        """Test execution with empty inputs."""
        result = await sma_filter_node.execute({})
        assert result == {"filtered_ohlcv_bundle": {}}

    @pytest.mark.asyncio
    async def test_execute_empty_bundle(self, sma_filter_node):
        """Test execution with empty OHLCV bundle."""
        result = await sma_filter_node.execute({"ohlcv_bundle": {}})
        assert result == {"filtered_ohlcv_bundle": {}}

    @pytest.mark.asyncio
    async def test_execute_default_params(self, sma_filter_node, sample_ohlcv_bundle, sample_symbols):
        """Test SMA crossover with default parameters (20 vs 50)."""
        inputs = {"ohlcv_bundle": sample_ohlcv_bundle}
        result = await sma_filter_node.execute(inputs)

        # Should filter assets based on recent SMA crossover
        filtered_bundle = result["filtered_ohlcv_bundle"]

        # AAPL and TSLA should pass (uptrending), BTC and ETH may not
        assert isinstance(filtered_bundle, dict)
        assert all(isinstance(symbol, AssetSymbol) for symbol in filtered_bundle.keys())
        assert all(isinstance(data, list) for data in filtered_bundle.values())

    @pytest.mark.asyncio
    async def test_execute_custom_periods(self, sample_ohlcv_bundle, sample_symbols):
        """Test SMA crossover with custom periods."""
        node = SMACrossoverFilterNode("sma_filter_id", {"short_period": 10, "long_period": 30})
        inputs = {"ohlcv_bundle": sample_ohlcv_bundle}
        result = await node.execute(inputs)

        filtered_bundle = result["filtered_ohlcv_bundle"]
        assert isinstance(filtered_bundle, dict)

    @pytest.mark.asyncio
    async def test_execute_insufficient_data(self, sma_filter_node, sample_symbols):
        """Test with insufficient data for SMA calculation."""
        # Create bundle with very short OHLCV data
        short_bundle = {
            sample_symbols[0]: [OHLCVBar(
                timestamp=1640995200000,
                open=150.0, high=152.0, low=149.0, close=151.0, volume=1000000
            )]
        }

        inputs = {"ohlcv_bundle": short_bundle}
        result = await sma_filter_node.execute(inputs)

        # Should return empty result due to insufficient data
        assert result["filtered_ohlcv_bundle"] == {}

    def test_invalid_params(self):
        """Test validation of invalid parameters."""
        with pytest.raises(ValueError, match="Short period must be less than long period"):
            SMACrossoverFilterNode("test_id", {"short_period": 50, "long_period": 20})


class TestADXFilterNode:
    """Tests for ADX Filter Node."""

    @pytest.fixture
    def adx_filter_node(self):
        return ADXFilterNode("adx_filter_id", {})

    @pytest.mark.asyncio
    async def test_execute_default_params(self, adx_filter_node, sample_ohlcv_bundle, sample_symbols):
        """Test ADX filtering with default parameters."""
        inputs = {"ohlcv_bundle": sample_ohlcv_bundle}
        result = await adx_filter_node.execute(inputs)

        filtered_bundle = result["filtered_ohlcv_bundle"]
        assert isinstance(filtered_bundle, dict)

    @pytest.mark.asyncio
    async def test_execute_high_adx_threshold(self, sample_ohlcv_bundle):
        """Test ADX filtering with high threshold."""
        node = ADXFilterNode("adx_filter_id", {"min_adx": 40.0})
        inputs = {"ohlcv_bundle": sample_ohlcv_bundle}
        result = await node.execute(inputs)

        # With high threshold, fewer assets should pass
        filtered_bundle = result["filtered_ohlcv_bundle"]
        assert isinstance(filtered_bundle, dict)

    @pytest.mark.asyncio
    async def test_execute_insufficient_data(self, adx_filter_node, sample_symbols):
        """Test ADX with insufficient data."""
        short_bundle = {
            sample_symbols[0]: [OHLCVBar(
                timestamp=1640995200000,
                open=150.0, high=152.0, low=149.0, close=151.0, volume=1000000
            )]
        }

        inputs = {"ohlcv_bundle": short_bundle}
        result = await adx_filter_node.execute(inputs)

        # Should return empty due to insufficient data for ADX calculation
        assert result["filtered_ohlcv_bundle"] == {}

    @pytest.mark.asyncio
    async def test_handle_nan_adx(self, adx_filter_node, sample_symbols):
        bundle_with_nan = {
            sample_symbols[0]: [OHLCVBar(timestamp=1, open=float('nan'), high=110, low=90, close=105, volume=1000)]
        }
        result = await adx_filter_node.execute({"ohlcv_bundle": bundle_with_nan})
        assert result["filtered_ohlcv_bundle"] == {}


class TestRSIFilterNode:
    """Tests for RSI Filter Node."""

    @pytest.fixture
    def rsi_filter_node(self):
        return RSIFilterNode("rsi_filter_id", {})

    @pytest.mark.asyncio
    async def test_execute_default_params(self, rsi_filter_node, sample_ohlcv_bundle, sample_symbols):
        """Test RSI filtering with default parameters (30-70 range)."""
        inputs = {"ohlcv_bundle": sample_ohlcv_bundle}
        result = await rsi_filter_node.execute(inputs)

        filtered_bundle = result["filtered_ohlcv_bundle"]
        assert isinstance(filtered_bundle, dict)

        # All sample data should be in neutral RSI range (30-70)

    @pytest.mark.asyncio
    async def test_execute_strict_oversold(self, sample_ohlcv_bundle):
        """Test RSI filtering for oversold conditions."""
        node = RSIFilterNode("rsi_filter_id", {"min_rsi": 0.0, "max_rsi": 30.0})
        inputs = {"ohlcv_bundle": sample_ohlcv_bundle}
        result = await node.execute(inputs)

        filtered_bundle = result["filtered_ohlcv_bundle"]
        assert isinstance(filtered_bundle, dict)

    @pytest.mark.asyncio
    async def test_execute_strict_overbought(self, sample_ohlcv_bundle):
        """Test RSI filtering for overbought conditions."""
        node = RSIFilterNode("rsi_filter_id", {"min_rsi": 70.0, "max_rsi": 100.0})
        inputs = {"ohlcv_bundle": sample_ohlcv_bundle}
        result = await node.execute(inputs)

        filtered_bundle = result["filtered_ohlcv_bundle"]
        assert isinstance(filtered_bundle, dict)

    @pytest.mark.asyncio
    async def test_execute_impossible_range(self, sample_ohlcv_bundle):
        """Test RSI filtering with impossible range."""
        # Should raise error during node creation due to invalid range
        with pytest.raises(ValueError, match="Minimum RSI must be less than maximum RSI"):
            RSIFilterNode("rsi_filter_id", {"min_rsi": 80.0, "max_rsi": 70.0})

    @pytest.mark.asyncio
    async def test_execute_insufficient_data(self, rsi_filter_node, sample_symbols):
        """Test RSI with insufficient data."""
        short_bundle = {
            sample_symbols[0]: [
                OHLCVBar(
                    timestamp=1640995200000 + i * 86400000,
                    open=150.0 + i, high=152.0 + i, low=149.0 + i, close=151.0 + i, volume=1000000
                ) for i in range(5)  # Less than default RSI period (14)
            ]
        }

        inputs = {"ohlcv_bundle": short_bundle}
        result = await rsi_filter_node.execute(inputs)

        # Should return empty due to insufficient data
        assert result["filtered_ohlcv_bundle"] == {}


class TestIndicatorFilterIntegration:
    """Integration tests combining multiple filters."""

    @pytest.mark.asyncio
    async def test_combined_filtering_workflow(self, sample_ohlcv_bundle, sample_symbols):
        """Test a typical workflow combining multiple filters."""
        # First apply ADX filter
        adx_node = ADXFilterNode("adx_filter", {"min_adx": 20.0})
        adx_result = await adx_node.execute({"ohlcv_bundle": sample_ohlcv_bundle})

        # Then apply RSI filter to ADX-filtered results
        rsi_node = RSIFilterNode("rsi_filter", {"min_rsi": 20.0, "max_rsi": 80.0})
        final_result = await rsi_node.execute({"ohlcv_bundle": adx_result["filtered_ohlcv_bundle"]})

        filtered_bundle = final_result["filtered_ohlcv_bundle"]
        assert isinstance(filtered_bundle, dict)

    @pytest.mark.asyncio
    async def test_empty_intermediate_results(self, sample_symbols):
        """Test handling when intermediate filtering results in empty bundle."""
        # Create bundle that will fail ADX filter
        weak_trend_bundle = {
            sample_symbols[0]: [
                OHLCVBar(
                    timestamp=1640995200000 + i * 86400000,
                    open=150.0, high=150.5, low=149.5, close=150.0, volume=1000000
                ) for i in range(50)  # Very flat, low ADX
            ]
        }

        # Apply very strict ADX filter
        adx_node = ADXFilterNode("adx_filter", {"min_adx": 50.0})
        result = await adx_node.execute({"ohlcv_bundle": weak_trend_bundle})

        # Should result in empty filtered bundle
        assert result["filtered_ohlcv_bundle"] == {}


class TestNodeProperties:
    """Test node configuration and metadata."""

    def test_sma_node_properties(self):
        """Test SMA filter node properties."""
        node = SMACrossoverFilterNode("test_id", {})

        expected_inputs = {"ohlcv_bundle": Dict[AssetSymbol, List[OHLCVBar]]}
        expected_outputs = {"filtered_ohlcv_bundle": Dict[AssetSymbol, List[OHLCVBar]]}

        assert node.inputs == expected_inputs
        assert node.outputs == expected_outputs

        expected_defaults = {"short_period": 20, "long_period": 50, "timeframe": "1d"}
        assert node.default_params == expected_defaults

        assert len(node.params_meta) == 3
        param_names = [p["name"] for p in node.params_meta]
        assert set(param_names) == {"short_period", "long_period", "timeframe"}

    def test_adx_node_properties(self):
        """Test ADX filter node properties."""
        node = ADXFilterNode("test_id", {})

        expected_defaults = {"min_adx": 25.0, "timeperiod": 14, "timeframe": "1d"}
        assert node.default_params == expected_defaults

        assert len(node.params_meta) == 3
        param_names = [p["name"] for p in node.params_meta]
        assert set(param_names) == {"min_adx", "timeperiod", "timeframe"}

    def test_rsi_node_properties(self):
        """Test RSI filter node properties."""
        node = RSIFilterNode("test_id", {})

        expected_defaults = {"min_rsi": 30.0, "max_rsi": 70.0, "timeperiod": 14, "timeframe": "1d"}
        assert node.default_params == expected_defaults

        assert len(node.params_meta) == 4
        param_names = [p["name"] for p in node.params_meta]
        assert set(param_names) == {"min_rsi", "max_rsi", "timeperiod", "timeframe"}


@pytest.mark.asyncio
@pytest.mark.parametrize("timeperiod, expected_pass", [(10, True), (101, False)])  # Test different timeperiods including insufficient data case
async def test_custom_timeperiod(sample_ohlcv_bundle, timeperiod, expected_pass):
    node = ADXFilterNode("adx_filter_id", {"min_adx": 25.0, "timeperiod": timeperiod})
    result = await node.execute({"ohlcv_bundle": sample_ohlcv_bundle})
    filtered_count = len(result["filtered_ohlcv_bundle"])
    if expected_pass:
        assert filtered_count > 0
    else:
        assert filtered_count == 0

@pytest.mark.asyncio
async def test_large_dataset():
    node = ADXFilterNode("adx_filter_id", {})
    large_bundle = {AssetSymbol(f"SYM_{i}", AssetClass.STOCKS): [OHLCVBar(timestamp=j, open=100+j, high=110+j, low=90+j, close=105+j, volume=1000) for j in range(1000)] for i in range(10)}
    result = await node.execute({"ohlcv_bundle": large_bundle})
    assert isinstance(result["filtered_ohlcv_bundle"], dict)

@pytest.mark.asyncio
async def test_all_nan_data(sample_symbols):
    node = ADXFilterNode("adx_filter_id", {})
    nan_bundle = {sample_symbols[0]: [OHLCVBar(timestamp=1, open=float('nan'), high=float('nan'), low=float('nan'), close=float('nan'), volume=float('nan')) for _ in range(20)]}
    result = await node.execute({"ohlcv_bundle": nan_bundle})
    assert result["filtered_ohlcv_bundle"] == {}

@pytest.mark.asyncio
async def test_mixed_nan_valid_data(sample_symbols, sample_ohlcv_bars):
    node = ADXFilterNode("adx_filter_id", {})
    mixed_bars = sample_ohlcv_bars[:10] + [OHLCVBar(timestamp=11, open=float('nan'), high=110, low=90, close=105, volume=1000)] + sample_ohlcv_bars[11:]
    mixed_bundle = {sample_symbols[0]: mixed_bars}
    result = await node.execute({"ohlcv_bundle": mixed_bundle})
    assert sample_symbols[0] not in result["filtered_ohlcv_bundle"]

def test_invalid_parameters():
    with pytest.raises(ValueError, match="Minimum ADX cannot be negative"):
        ADXFilterNode("test_id", {"min_adx": -5.0})
    with pytest.raises(ValueError, match="Time period must be positive"):
        ADXFilterNode("test_id", {"timeperiod": 0})
    with pytest.raises(ValueError, match="Invalid timeframe"):
        ADXFilterNode("test_id", {"timeframe": "invalid_tf"})
