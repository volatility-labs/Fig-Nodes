import pytest

from core.types_registry import (
    AssetClass,
    AssetSymbol,
    IndicatorResult,
    IndicatorType,
    IndicatorValue,
    OHLCVBar,
)
from nodes.core.market.filters.vbp_level_filter_node import VBPLevelFilter


@pytest.fixture
def sample_ohlcv_bundle() -> dict[AssetSymbol, list[OHLCVBar]]:
    """Create a sample bundle with consistent price patterns."""
    bars = [
        {
            "timestamp": i * 86400000,
            "open": 100.0 + i * 0.5,
            "high": 105.0 + i * 0.5,
            "low": 95.0 + i * 0.5,
            "close": 102.0 + i * 0.5,
            "volume": 1000.0,
        }
        for i in range(100)
    ]
    symbol = AssetSymbol("TEST_SYMBOL", AssetClass.STOCKS)
    return {symbol: bars}


@pytest.fixture
def bundle_with_volume_levels() -> dict[AssetSymbol, list[OHLCVBar]]:
    """Create bundle with concentrated volume at specific price levels."""
    bars = []
    # Create data with high volume at specific price ranges
    for i in range(50):
        if 10 <= i < 20 or 30 <= i < 40:
            # High volume bars in middle ranges
            bars.append(
                {
                    "timestamp": i * 86400000,
                    "open": 100.0,
                    "high": 108.0,
                    "low": 100.0,
                    "close": 106.0,
                    "volume": 5000.0,
                }
            )
        else:
            # Low volume bars
            bars.append(
                {
                    "timestamp": i * 86400000,
                    "open": 100.0 + i * 0.5,
                    "high": 105.0 + i * 0.5,
                    "low": 95.0 + i * 0.5,
                    "close": 102.0 + i * 0.5,
                    "volume": 100.0,
                }
            )
    symbol = AssetSymbol("VOL_LEVELS", AssetClass.STOCKS)
    return {symbol: bars}


@pytest.fixture
def low_distance_bundle() -> dict[AssetSymbol, list[OHLCVBar]]:
    """Create bundle where current price is close to support."""
    bars = []
    for i in range(50):
        bars.append(
            {
                "timestamp": i * 86400000,
                "open": 100.0,
                "high": 105.0,
                "low": 95.0,
                "close": 102.0 + i * 0.1,  # Slowly trending up
                "volume": 1000.0,
            }
        )
    # Last bar is at 106.7, create high volume at 105 (support level)
    bars.append(
        {
            "timestamp": 50 * 86400000,
            "open": 105.0,
            "high": 107.0,
            "low": 104.0,
            "close": 106.7,  # Close to resistance
            "volume": 5000.0,
        }
    )
    symbol = AssetSymbol("CLOSE_SUPPORT", AssetClass.STOCKS)
    return {symbol: bars}


@pytest.mark.asyncio
async def test_vbp_filter_node_basic_operation(sample_ohlcv_bundle):
    """Test basic VBP filter node operation."""
    node = VBPLevelFilter(
        id=1,
        params={
            "bins": 20,
            "lookback_years": 2,
            "num_levels": 5,
            "max_distance_to_support": 10.0,
            "min_distance_to_resistance": 5.0,
        },
    )

    result = await node._execute_impl({"ohlcv_bundle": sample_ohlcv_bundle})

    assert "filtered_ohlcv_bundle" in result
    assert isinstance(result["filtered_ohlcv_bundle"], dict)


@pytest.mark.asyncio
async def test_vbp_filter_node_with_dollar_weighted(bundle_with_volume_levels):
    """Test VBP filter with dollar-weighted volume."""
    node = VBPLevelFilter(
        id=1,
        params={
            "bins": 20,
            "lookback_years": 2,
            "num_levels": 5,
            "max_distance_to_support": 10.0,
            "min_distance_to_resistance": 5.0,
            "use_dollar_weighted": True,
        },
    )

    result = await node._execute_impl({"ohlcv_bundle": bundle_with_volume_levels})

    assert "filtered_ohlcv_bundle" in result


@pytest.mark.asyncio
async def test_vbp_filter_node_with_close_only(bundle_with_volume_levels):
    """Test VBP filter with close-only binning."""
    node = VBPLevelFilter(
        id=1,
        params={
            "bins": 20,
            "lookback_years": 2,
            "num_levels": 5,
            "max_distance_to_support": 10.0,
            "min_distance_to_resistance": 5.0,
            "use_close_only": True,
        },
    )

    result = await node._execute_impl({"ohlcv_bundle": bundle_with_volume_levels})

    assert "filtered_ohlcv_bundle" in result


@pytest.mark.asyncio
async def test_vbp_filter_node_all_combinations(bundle_with_volume_levels):
    """Test VBP filter with all parameter combinations."""
    combinations = [
        {"use_dollar_weighted": False, "use_close_only": False},
        {"use_dollar_weighted": False, "use_close_only": True},
        {"use_dollar_weighted": True, "use_close_only": False},
        {"use_dollar_weighted": True, "use_close_only": True},
    ]

    for combo in combinations:
        node = VBPLevelFilter(
            id=1,
            params={
                "bins": 20,
                "lookback_years": 2,
                "num_levels": 5,
                "max_distance_to_support": 10.0,
                "min_distance_to_resistance": 5.0,
                **combo,
            },
        )

        result = await node._execute_impl({"ohlcv_bundle": bundle_with_volume_levels})
        assert "filtered_ohlcv_bundle" in result


def test_vbp_filter_node_calculate_indicator(bundle_with_volume_levels):
    """Test VBP indicator calculation with new parameters."""
    node = VBPLevelFilter(
        id=1,
        params={
            "bins": 20,
            "lookback_years": 2,
            "num_levels": 5,
            "use_dollar_weighted": True,
            "use_close_only": False,
        },
    )

    symbol = list(bundle_with_volume_levels.keys())[0]
    bars = bundle_with_volume_levels[symbol]

    result = node._calculate_indicator(bars)

    assert isinstance(result, IndicatorResult)
    assert result.indicator_type == IndicatorType.VBP
    assert result.values is not None
    assert "lines" in result.values.__dict__


def test_vbp_filter_node_indicator_with_defaults(bundle_with_volume_levels):
    """Test VBP indicator with default parameters."""
    node = VBPLevelFilter(
        id=1,
        params={
            "bins": 20,
            "lookback_years": 2,
            "num_levels": 5,
        },
    )

    symbol = list(bundle_with_volume_levels.keys())[0]
    bars = bundle_with_volume_levels[symbol]

    result = node._calculate_indicator(bars)

    assert isinstance(result, IndicatorResult)
    assert result.indicator_type == IndicatorType.VBP


def test_vbp_filter_node_indicator_with_close_only(bundle_with_volume_levels):
    """Test VBP indicator specifically with close-only parameter."""
    node = VBPLevelFilter(
        id=1,
        params={
            "bins": 20,
            "lookback_years": 2,
            "num_levels": 5,
            "use_close_only": True,
        },
    )

    symbol = list(bundle_with_volume_levels.keys())[0]
    bars = bundle_with_volume_levels[symbol]

    result = node._calculate_indicator(bars)

    assert isinstance(result, IndicatorResult)
    assert result.indicator_type == IndicatorType.VBP


def test_vbp_filter_node_indicator_with_dollar_weighted(bundle_with_volume_levels):
    """Test VBP indicator specifically with dollar-weighted parameter."""
    node = VBPLevelFilter(
        id=1,
        params={
            "bins": 20,
            "lookback_years": 2,
            "num_levels": 5,
            "use_dollar_weighted": True,
        },
    )

    symbol = list(bundle_with_volume_levels.keys())[0]
    bars = bundle_with_volume_levels[symbol]

    result = node._calculate_indicator(bars)

    assert isinstance(result, IndicatorResult)
    assert result.indicator_type == IndicatorType.VBP


@pytest.mark.asyncio
async def test_vbp_filter_node_empty_bundle():
    """Test VBP filter with empty bundle."""
    node = VBPLevelFilter(
        id=1,
        params={
            "bins": 20,
            "lookback_years": 2,
            "num_levels": 5,
            "max_distance_to_support": 10.0,
            "min_distance_to_resistance": 5.0,
        },
    )

    result = await node._execute_impl({"ohlcv_bundle": {}})

    assert "filtered_ohlcv_bundle" in result
    assert result["filtered_ohlcv_bundle"] == {}


@pytest.mark.asyncio
async def test_vbp_filter_node_with_two_lookback_periods(bundle_with_volume_levels):
    """Test VBP filter with two lookback periods."""
    node = VBPLevelFilter(
        id=1,
        params={
            "bins": 20,
            "lookback_years": 2,
            "lookback_years_2": 1,
            "num_levels": 5,
            "max_distance_to_support": 10.0,
            "min_distance_to_resistance": 5.0,
        },
    )

    result = await node._execute_impl({"ohlcv_bundle": bundle_with_volume_levels})

    assert "filtered_ohlcv_bundle" in result


def test_vbp_filter_node_validate_params():
    """Test parameter validation."""
    # Valid params
    node1 = VBPLevelFilter(
        id=1,
        params={
            "bins": 20,
            "lookback_years": 2,
            "num_levels": 5,
        },
    )
    assert node1 is not None

    # Invalid bins (too small)
    with pytest.raises(ValueError, match="Number of bins must be at least 10"):
        VBPLevelFilter(
            id=1,
            params={
                "bins": 5,
                "lookback_years": 2,
                "num_levels": 5,
            },
        )

    # Invalid lookback (too small)
    with pytest.raises(ValueError, match="Lookback period must be at least 1 year"):
        VBPLevelFilter(
            id=1,
            params={
                "bins": 20,
                "lookback_years": 0.5,
                "num_levels": 5,
            },
        )

    # Invalid num_levels (too small)
    with pytest.raises(ValueError, match="Number of levels must be at least 1"):
        VBPLevelFilter(
            id=1,
            params={
                "bins": 20,
                "lookback_years": 2,
                "num_levels": 0,
            },
        )


def test_vbp_filter_node_should_pass_filter():
    """Test filter pass/fail logic."""
    node = VBPLevelFilter(
        id=1,
        params={
            "bins": 20,
            "lookback_years": 2,
            "num_levels": 5,
            "max_distance_to_support": 5.0,
            "min_distance_to_resistance": 5.0,
        },
    )

    # Test with error
    error_result = IndicatorResult(
        indicator_type=IndicatorType.VBP,
        timestamp=1000,
        values=IndicatorValue(lines={}),
        params={},
        error="Test error",
    )
    assert not node._should_pass_filter(error_result)

    # Test with valid result but wrong distances
    # Create a result that won't pass
    invalid_result = IndicatorResult(
        indicator_type=IndicatorType.VBP,
        timestamp=1000,
        values=IndicatorValue(
            lines={
                "current_price": 100.0,
                "closest_support": 90.0,  # 10% away (exceeds max of 5%)
                "closest_resistance": 110.0,  # 10% away (exceeds min of 5%)
                "distance_to_support": 10.0,
                "distance_to_resistance": 10.0,
                "num_levels": 5,
                "has_resistance_above": True,
            }
        ),
        params={},
    )
    assert not node._should_pass_filter(invalid_result)

    # Test with valid result that should pass
    valid_result = IndicatorResult(
        indicator_type=IndicatorType.VBP,
        timestamp=1000,
        values=IndicatorValue(
            lines={
                "current_price": 100.0,
                "closest_support": 96.0,  # 4% away (within max of 5%)
                "closest_resistance": 107.0,  # 7% away (exceeds min of 5%)
                "distance_to_support": 4.0,
                "distance_to_resistance": 7.0,
                "num_levels": 5,
                "has_resistance_above": True,
            }
        ),
        params={},
    )
    assert node._should_pass_filter(valid_result)


@pytest.mark.asyncio
async def test_vbp_filter_node_edge_case_minimal_data():
    """Test VBP filter with minimal data."""
    minimal_bars = [
        {
            "timestamp": i * 86400000,
            "open": 100.0,
            "high": 105.0,
            "low": 95.0,
            "close": 102.0,
            "volume": 1000.0,
        }
        for i in range(10)
    ]
    symbol = AssetSymbol("MINIMAL", AssetClass.STOCKS)
    bundle = {symbol: minimal_bars}

    node = VBPLevelFilter(
        id=1,
        params={
            "bins": 20,
            "lookback_years": 2,
            "num_levels": 5,
            "max_distance_to_support": 10.0,
            "min_distance_to_resistance": 5.0,
        },
    )

    result = await node._execute_impl({"ohlcv_bundle": bundle})

    assert "filtered_ohlcv_bundle" in result
