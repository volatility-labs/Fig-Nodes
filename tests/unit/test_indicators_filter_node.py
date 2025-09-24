import pytest
from typing import Dict, Any, List
from nodes.core.market.indicators_filter_node import IndicatorsFilterNode
from core.types_registry import AssetSymbol, AssetClass


@pytest.fixture
def indicators_filter_node():
    return IndicatorsFilterNode("indicators_filter_id", {})


@pytest.fixture
def sample_symbols():
    return [
        AssetSymbol("AAPL", AssetClass.STOCKS),
        AssetSymbol("BTC", AssetClass.CRYPTO),
        AssetSymbol("ETH", AssetClass.CRYPTO),
        AssetSymbol("TSLA", AssetClass.STOCKS),
    ]


@pytest.fixture
def sample_indicators_data(sample_symbols):
    """Sample indicators data for testing."""
    return {
        sample_symbols[0]: {  # AAPL - passes all filters
            "adx": 25.0,
            "eis_bullish": True,
            "eis_bearish": False,
            "hurst": 0.6,
            "acceleration": 0.05,
            "volume_ratio": 1.2,
        },
        sample_symbols[1]: {  # BTC - low ADX, fails some filters
            "adx": 15.0,
            "eis_bullish": False,
            "eis_bearish": True,
            "hurst": 0.7,
            "acceleration": 0.03,
            "volume_ratio": 1.1,
        },
        sample_symbols[2]: {  # ETH - fails some filters
            "adx": 20.0,
            "eis_bullish": False,
            "eis_bearish": False,
            "hurst": 0.3,  # Below 0.5 threshold
            "acceleration": -0.02,  # Below 0.0 threshold
            "volume_ratio": 1.0,
        },
        sample_symbols[3]: {  # TSLA - passes all filters
            "adx": 30.0,
            "eis_bullish": True,
            "eis_bearish": False,
            "hurst": 0.65,
            "acceleration": 0.08,
            "volume_ratio": 1.5,
        },
    }


class TestIndicatorsFilterNode:
    """Comprehensive tests for IndicatorsFilterNode."""

    @pytest.mark.asyncio
    async def test_execute_empty_inputs(self, indicators_filter_node):
        """Test execution with empty inputs returns empty result."""
        result = await indicators_filter_node.execute({})
        assert result == {"filtered_symbols": []}

    @pytest.mark.asyncio
    async def test_execute_no_indicators(self, indicators_filter_node):
        """Test execution with no indicators input."""
        result = await indicators_filter_node.execute({"indicators": {}})
        assert result == {"filtered_symbols": []}

    @pytest.mark.asyncio
    async def test_execute_default_filters(self, indicators_filter_node, sample_indicators_data, sample_symbols):
        """Test execution with default filter parameters."""
        inputs = {"indicators": sample_indicators_data}
        result = await indicators_filter_node.execute(inputs)

        # ETH fails due to negative acceleration, so only 3 symbols pass
        expected_symbols = [sample_symbols[0], sample_symbols[1], sample_symbols[3]]  # AAPL, BTC, TSLA
        assert len(result["filtered_symbols"]) == 3
        assert set(result["filtered_symbols"]) == set(expected_symbols)

    @pytest.mark.asyncio
    async def test_execute_adx_filter(self, indicators_filter_node, sample_indicators_data, sample_symbols):
        """Test ADX filtering."""
        # Set minimum ADX to 20
        indicators_filter_node.params["min_adx"] = 20.0

        inputs = {"indicators": sample_indicators_data}
        result = await indicators_filter_node.execute(inputs)

        # BTC fails (adx=15), ETH fails (acceleration=-0.02), so only AAPL and TSLA pass
        expected_symbols = [sample_symbols[0], sample_symbols[3]]  # AAPL, TSLA
        assert len(result["filtered_symbols"]) == 2
        assert set(result["filtered_symbols"]) == set(expected_symbols)

    @pytest.mark.asyncio
    async def test_execute_eis_bullish_required(self, indicators_filter_node, sample_indicators_data, sample_symbols):
        """Test EIS bullish requirement filtering."""
        indicators_filter_node.params["require_eis_bullish"] = True

        inputs = {"indicators": sample_indicators_data}
        result = await indicators_filter_node.execute(inputs)

        # Should only keep AAPL and TSLA (both eis_bullish=True)
        expected_symbols = [sample_symbols[0], sample_symbols[3]]
        assert len(result["filtered_symbols"]) == 2
        assert set(result["filtered_symbols"]) == set(expected_symbols)

    @pytest.mark.asyncio
    async def test_execute_eis_bearish_required(self, indicators_filter_node, sample_indicators_data, sample_symbols):
        """Test EIS bearish requirement filtering."""
        indicators_filter_node.params["require_eis_bearish"] = True

        inputs = {"indicators": sample_indicators_data}
        result = await indicators_filter_node.execute(inputs)

        # Should only keep BTC (eis_bearish=True)
        expected_symbols = [sample_symbols[1]]
        assert len(result["filtered_symbols"]) == 1
        assert result["filtered_symbols"] == expected_symbols

    @pytest.mark.asyncio
    async def test_execute_hurst_filter(self, indicators_filter_node, sample_indicators_data, sample_symbols):
        """Test Hurst exponent filtering."""
        indicators_filter_node.params["min_hurst"] = 0.5

        inputs = {"indicators": sample_indicators_data}
        result = await indicators_filter_node.execute(inputs)

        # Should filter out ETH (hurst=0.4) but keep others
        expected_symbols = [sample_symbols[0], sample_symbols[1], sample_symbols[3]]
        assert len(result["filtered_symbols"]) == 3
        assert set(result["filtered_symbols"]) == set(expected_symbols)

    @pytest.mark.asyncio
    async def test_execute_acceleration_filter(self, indicators_filter_node, sample_indicators_data, sample_symbols):
        """Test acceleration filtering."""
        indicators_filter_node.params["min_acceleration"] = 0.0

        inputs = {"indicators": sample_indicators_data}
        result = await indicators_filter_node.execute(inputs)

        # Should filter out ETH (acceleration=-0.01) but keep others
        expected_symbols = [sample_symbols[0], sample_symbols[1], sample_symbols[3]]
        assert len(result["filtered_symbols"]) == 3
        assert set(result["filtered_symbols"]) == set(expected_symbols)

    @pytest.mark.asyncio
    async def test_execute_volume_ratio_filter(self, indicators_filter_node, sample_indicators_data, sample_symbols):
        """Test volume ratio filtering."""
        indicators_filter_node.params["min_volume_ratio"] = 1.1

        inputs = {"indicators": sample_indicators_data}
        result = await indicators_filter_node.execute(inputs)

        # Should filter out ETH (volume_ratio=0.8) and BTC (1.1 is >= 1.1, so borderline)
        # Wait, BTC has 1.1 which should pass if >= 1.1
        expected_symbols = [sample_symbols[0], sample_symbols[1], sample_symbols[3]]
        assert len(result["filtered_symbols"]) == 3
        assert set(result["filtered_symbols"]) == set(expected_symbols)

    @pytest.mark.asyncio
    async def test_execute_combined_filters(self, indicators_filter_node, sample_indicators_data, sample_symbols):
        """Test combined filtering with multiple criteria."""
        indicators_filter_node.params.update({
            "min_adx": 20.0,
            "require_eis_bullish": True,
            "min_hurst": 0.5,
            "min_acceleration": 0.0,
            "min_volume_ratio": 1.0,
        })

        inputs = {"indicators": sample_indicators_data}
        result = await indicators_filter_node.execute(inputs)

        # Should only keep AAPL and TSLA (both meet all criteria)
        expected_symbols = [sample_symbols[0], sample_symbols[3]]
        assert len(result["filtered_symbols"]) == 2
        assert set(result["filtered_symbols"]) == set(expected_symbols)

    @pytest.mark.asyncio
    async def test_execute_strict_filters_no_matches(self, indicators_filter_node, sample_indicators_data):
        """Test with very strict filters that match no symbols."""
        indicators_filter_node.params.update({
            "min_adx": 50.0,  # Higher than any sample
            "require_eis_bullish": True,
            "require_eis_bearish": True,  # Impossible to be both
            "min_hurst": 1.0,  # Higher than any sample
            "min_acceleration": 1.0,  # Higher than any sample
            "min_volume_ratio": 10.0,  # Higher than any sample
        })

        inputs = {"indicators": sample_indicators_data}
        result = await indicators_filter_node.execute(inputs)

        assert result["filtered_symbols"] == []

    @pytest.mark.asyncio
    async def test_execute_empty_indicator_dict(self, indicators_filter_node, sample_symbols):
        """Test handling of symbols with empty indicator dictionaries."""
        indicators_data = {
            sample_symbols[0]: {},  # Empty indicators
            sample_symbols[1]: None,  # None indicators
            sample_symbols[2]: {  # Valid indicators
                "adx": 25.0,
                "eis_bullish": True,
                "hurst": 0.6,
                "acceleration": 0.05,
                "volume_ratio": 1.2,
            },
        }

        inputs = {"indicators": indicators_data}
        result = await indicators_filter_node.execute(inputs)

        # Should skip empty/None indicators and only include valid ones that pass filters
        expected_symbols = [sample_symbols[2]]
        assert result["filtered_symbols"] == expected_symbols

    @pytest.mark.asyncio
    async def test_execute_missing_indicator_keys(self, indicators_filter_node, sample_symbols):
        """Test handling of indicators with missing keys (should use defaults)."""
        indicators_data = {
            sample_symbols[0]: {
                "adx": 25.0,
                # Missing eis_bullish (should default to False)
                "hurst": 0.6,
                "acceleration": 0.05,
                "volume_ratio": 1.2,
                # Missing eis_bearish (should default to False)
            },
        }

        inputs = {"indicators": indicators_data}
        result = await indicators_filter_node.execute(inputs)

        # Should pass because missing EIS flags default to False and don't require them
        assert len(result["filtered_symbols"]) == 1
        assert result["filtered_symbols"][0] == sample_symbols[0]

    @pytest.mark.asyncio
    async def test_execute_missing_indicator_keys_with_requirements(self, indicators_filter_node, sample_symbols):
        """Test handling of missing EIS flags when they are required."""
        indicators_data = {
            sample_symbols[0]: {
                "adx": 25.0,
                # Missing eis_bullish when it's required
                "hurst": 0.6,
                "acceleration": 0.05,
                "volume_ratio": 1.2,
            },
        }

        indicators_filter_node.params["require_eis_bullish"] = True
        inputs = {"indicators": indicators_data}
        result = await indicators_filter_node.execute(inputs)

        # Should fail because eis_bullish defaults to False but is required
        assert result["filtered_symbols"] == []

    @pytest.mark.asyncio
    async def test_execute_numeric_defaults(self, indicators_filter_node, sample_symbols):
        """Test that numeric indicators default to appropriate values."""
        indicators_data = {
            sample_symbols[0]: {
                "eis_bullish": True,
                # Missing numeric indicators - should default to 0
            },
        }

        inputs = {"indicators": indicators_data}
        result = await indicators_filter_node.execute(inputs)

        # Should pass because missing numerics default to 0, which meets minimum thresholds
        assert len(result["filtered_symbols"]) == 1

    @pytest.mark.asyncio
    async def test_execute_zero_values(self, indicators_filter_node, sample_symbols):
        """Test filtering with zero values."""
        indicators_data = {
            sample_symbols[0]: {
                "adx": 0.0,
                "eis_bullish": False,
                "eis_bearish": False,
                "hurst": 0.0,
                "acceleration": 0.0,
                "volume_ratio": 0.0,
            },
        }

        # Set minimums above zero
        indicators_filter_node.params.update({
            "min_adx": 10.0,
            "min_hurst": 0.5,
            "min_acceleration": 0.01,
            "min_volume_ratio": 1.0,
        })

        inputs = {"indicators": indicators_data}
        result = await indicators_filter_node.execute(inputs)

        # Should fail all filters
        assert result["filtered_symbols"] == []

    @pytest.mark.asyncio
    async def test_execute_parameter_override(self, indicators_filter_node, sample_indicators_data, sample_symbols):
        """Test that parameter values are correctly retrieved from node params."""
        # Override params during execution
        indicators_filter_node.params["min_adx"] = 25.0

        inputs = {"indicators": sample_indicators_data}
        result = await indicators_filter_node.execute(inputs)

        # Should only keep TSLA (adx=30) and AAPL (adx=25, which meets >= 25)
        expected_symbols = [sample_symbols[0], sample_symbols[3]]
        assert len(result["filtered_symbols"]) == 2
        assert set(result["filtered_symbols"]) == set(expected_symbols)

    @pytest.mark.asyncio
    async def test_execute_large_dataset(self, indicators_filter_node):
        """Test performance and correctness with larger dataset."""
        # Create 100 symbols with varying indicators
        symbols = [AssetSymbol(f"SYMBOL_{i}", AssetClass.STOCKS) for i in range(100)]
        indicators_data = {}

        for i, symbol in enumerate(symbols):
            # Create a pattern where every 10th symbol passes strict filters
            passes_strict = (i % 10) == 0
            indicators_data[symbol] = {
                "adx": 30.0 if passes_strict else 15.0,
                "eis_bullish": passes_strict,
                "eis_bearish": False,
                "hurst": 0.7 if passes_strict else 0.3,
                "acceleration": 0.1 if passes_strict else -0.05,
                "volume_ratio": 1.5 if passes_strict else 0.5,
            }

        # Set strict filters
        indicators_filter_node.params.update({
            "min_adx": 25.0,
            "require_eis_bullish": True,
            "min_hurst": 0.5,
            "min_acceleration": 0.0,
            "min_volume_ratio": 1.0,
        })

        inputs = {"indicators": indicators_data}
        result = await indicators_filter_node.execute(inputs)

        # Should have 10 symbols (every 10th one)
        assert len(result["filtered_symbols"]) == 10
        expected_symbols = [symbols[i] for i in range(0, 100, 10)]
        assert set(result["filtered_symbols"]) == set(expected_symbols)

    @pytest.mark.asyncio
    async def test_execute_edge_case_values(self, indicators_filter_node, sample_symbols):
        """Test edge cases with extreme values."""
        indicators_data = {
            sample_symbols[0]: {
                "adx": float('inf'),  # Infinity
                "eis_bullish": True,
                "eis_bearish": False,
                "hurst": float('-inf'),  # Negative infinity
                "acceleration": float('nan'),  # NaN
                "volume_ratio": 1.0,
            },
        }

        inputs = {"indicators": indicators_data}
        result = await indicators_filter_node.execute(inputs)

        # Should handle edge values gracefully
        # Note: NaN comparisons always return False, so acceleration check will fail
        assert len(result["filtered_symbols"]) == 0

    def test_node_properties(self, indicators_filter_node):
        """Test node configuration properties."""
        from core.types_registry import get_type

        assert indicators_filter_node.inputs == {"indicators": Dict[AssetSymbol, Dict[str, Any]]}
        assert indicators_filter_node.outputs == {"filtered_symbols": List[AssetSymbol]}

        expected_defaults = {
            "min_adx": 0.0,
            "require_eis_bullish": False,
            "require_eis_bearish": False,
            "min_hurst": 0.0,
            "min_acceleration": 0.0,
            "min_volume_ratio": 1.0,
        }
        assert indicators_filter_node.default_params == expected_defaults

        # Verify params_meta structure
        assert len(indicators_filter_node.params_meta) == 6
        param_names = [p["name"] for p in indicators_filter_node.params_meta]
        expected_names = ["min_adx", "require_eis_bullish", "require_eis_bearish",
                         "min_hurst", "min_acceleration", "min_volume_ratio"]
        assert set(param_names) == set(expected_names)

    def test_validate_inputs(self, indicators_filter_node):
        """Test input validation."""
        # Valid inputs
        assert indicators_filter_node.validate_inputs({"indicators": {}}) is True

        # Invalid inputs - indicators is required
        assert indicators_filter_node.validate_inputs({}) is False

        # Invalid inputs (indicators should be dict if provided) - raises TypeError
        with pytest.raises(TypeError):
            indicators_filter_node.validate_inputs({"indicators": "not_a_dict"})
        with pytest.raises(TypeError):
            indicators_filter_node.validate_inputs({"indicators": []})
