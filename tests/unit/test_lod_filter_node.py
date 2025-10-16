import pytest
from unittest.mock import patch, MagicMock
from typing import Dict, List
import pandas as pd
import numpy as np
from ta.volatility import AverageTrueRange
from nodes.core.market.filters.lod_filter_node import LodFilter
from core.types_registry import AssetSymbol, OHLCVBar, IndicatorType, IndicatorResult, IndicatorValue, AssetClass


@pytest.fixture
def sample_ohlcv_bundle() -> Dict[AssetSymbol, List[OHLCVBar]]:
    """Create a sample bundle with predictable ATR and LoD distance."""
    # Create data with known volatility pattern
    # High volatility symbol (should have high ATR)
    high_vol_bars = [
        {"timestamp": i * 86400000, "open": 100 + i*0.5, "high": 105 + i*0.5, "low": 95 + i*0.5, "close": 102 + i*0.5, "volume": 1000}
        for i in range(20)
    ]
    # Low volatility symbol (should have low ATR)
    low_vol_bars = [
        {"timestamp": i * 86400000, "open": 100 + i*0.01, "high": 100.5 + i*0.01, "low": 99.5 + i*0.01, "close": 100 + i*0.01, "volume": 1000}
        for i in range(20)
    ]

    symbol_high = AssetSymbol("HIGH_VOL", AssetClass.STOCKS)
    symbol_low = AssetSymbol("LOW_VOL", AssetClass.STOCKS)
    return {symbol_high: high_vol_bars, symbol_low: low_vol_bars}


@pytest.fixture
def high_lod_bundle() -> Dict[AssetSymbol, List[OHLCVBar]]:
    """Create bundle with high LoD distance (close far from low)."""
    # Symbol with close much higher than low of day
    bars = [
        {"timestamp": i * 86400000, "open": 100, "high": 120, "low": 90, "close": 115, "volume": 1000}
        for i in range(20)
    ]
    # Ensure last bar has high LoD distance
    bars[-1] = {"timestamp": 19 * 86400000, "open": 100, "high": 120, "low": 90, "close": 115, "volume": 1000}
    symbol = AssetSymbol("HIGH_LOD", AssetClass.STOCKS)
    return {symbol: bars}


@pytest.fixture
def low_lod_bundle() -> Dict[AssetSymbol, List[OHLCVBar]]:
    """Create bundle with low LoD distance (close close to low of day)."""
    # Symbol with close very close to low of day
    bars = [
        {"timestamp": i * 86400000, "open": 100, "high": 105, "low": 99, "close": 99.5, "volume": 1000}
        for i in range(20)
    ]
    symbol = AssetSymbol("LOW_LOD", AssetClass.STOCKS)
    return {symbol: bars}


@pytest.mark.asyncio
async def test_lod_filter_node_happy_path_high_lod(high_lod_bundle):
    """Test that assets with high LoD distance pass the filter."""
    node = LodFilter(id=1, params={"min_lod_distance": 10.0, "atr_window": 14})
    inputs = {"ohlcv_bundle": high_lod_bundle}
    result = await node.execute(inputs)

    assert "filtered_ohlcv_bundle" in result
    filtered = result["filtered_ohlcv_bundle"]
    assert len(filtered) == 1
    symbol = AssetSymbol("HIGH_LOD", AssetClass.STOCKS)
    assert symbol in filtered


@pytest.mark.asyncio
async def test_lod_filter_node_happy_path_low_lod(low_lod_bundle):
    """Test that assets with low LoD distance fail the filter."""
    node = LodFilter(id=1, params={"min_lod_distance": 10.0, "atr_window": 14})
    inputs = {"ohlcv_bundle": low_lod_bundle}
    result = await node.execute(inputs)

    assert "filtered_ohlcv_bundle" in result
    filtered = result["filtered_ohlcv_bundle"]
    assert len(filtered) == 0


@pytest.mark.asyncio
async def test_lod_filter_node_mixed_bundle(high_lod_bundle, low_lod_bundle):
    """Test filtering with mixed bundle of passing and failing assets."""
    # Combine bundles
    mixed_bundle = {**high_lod_bundle, **low_lod_bundle}

    node = LodFilter(id=1, params={"min_lod_distance": 10.0, "atr_window": 14})
    inputs = {"ohlcv_bundle": mixed_bundle}
    result = await node.execute(inputs)

    assert "filtered_ohlcv_bundle" in result
    filtered = result["filtered_ohlcv_bundle"]
    # Should only contain the high LoD symbol
    assert len(filtered) == 1
    high_symbol = AssetSymbol("HIGH_LOD", AssetClass.STOCKS)
    low_symbol = AssetSymbol("LOW_LOD", AssetClass.STOCKS)
    assert high_symbol in filtered
    assert low_symbol not in filtered


@pytest.mark.asyncio
async def test_lod_filter_node_empty_bundle():
    """Test behavior with empty input bundle."""
    node = LodFilter(id=1, params={"min_lod_distance": 3.16, "atr_window": 14})
    inputs = {"ohlcv_bundle": {}}
    result = await node.execute(inputs)

    assert result["filtered_ohlcv_bundle"] == {}


@pytest.mark.asyncio
async def test_lod_filter_node_insufficient_data():
    """Test behavior when data is insufficient for ATR calculation."""
    # Create bundle with too few bars
    short_bars = [
        {"timestamp": i * 86400000, "open": 100, "high": 105, "low": 95, "close": 102, "volume": 1000}
        for i in range(10)  # Less than default atr_window of 14
    ]
    symbol = AssetSymbol("SHORT_DATA", AssetClass.STOCKS)
    bundle = {symbol: short_bars}

    node = LodFilter(id=1, params={"min_lod_distance": 3.16, "atr_window": 14})
    inputs = {"ohlcv_bundle": bundle}
    result = await node.execute(inputs)

    # Should not pass due to insufficient data
    assert len(result["filtered_ohlcv_bundle"]) == 0


@pytest.mark.asyncio
async def test_lod_filter_node_no_data_symbol():
    """Test behavior with symbol having no OHLCV data."""
    symbol = AssetSymbol("EMPTY", AssetClass.STOCKS)
    bundle = {symbol: []}

    node = LodFilter(id=1, params={"min_lod_distance": 3.16, "atr_window": 14})
    inputs = {"ohlcv_bundle": bundle}
    result = await node.execute(inputs)

    assert len(result["filtered_ohlcv_bundle"]) == 0


@pytest.mark.asyncio
async def test_lod_filter_node_zero_atr():
    """Test behavior when ATR calculation results in zero or invalid ATR."""
    # Create flat data that should result in zero ATR
    flat_bars = [
        {"timestamp": i * 86400000, "open": 100, "high": 100, "low": 100, "close": 100, "volume": 1000}
        for i in range(20)
    ]
    symbol = AssetSymbol("FLAT", AssetClass.STOCKS)
    bundle = {symbol: flat_bars}

    node = LodFilter(id=1, params={"min_lod_distance": 3.16, "atr_window": 14})
    inputs = {"ohlcv_bundle": bundle}
    result = await node.execute(inputs)

    # Should not pass due to invalid ATR
    assert len(result["filtered_ohlcv_bundle"]) == 0


@pytest.mark.asyncio
async def test_lod_filter_node_nan_close_values():
    """Test handling of NaN values in close prices."""
    # Create data with NaN in close prices which should cause issues
    nan_close_bars = [
        {"timestamp": i * 86400000, "open": 100, "high": 105, "low": 95, "close": float('nan'), "volume": 1000}
        for i in range(20)
    ]
    symbol = AssetSymbol("NAN_CLOSE", AssetClass.STOCKS)
    bundle = {symbol: nan_close_bars}

    node = LodFilter(id=1, params={"min_lod_distance": 3.16, "atr_window": 14})
    inputs = {"ohlcv_bundle": bundle}
    result = await node.execute(inputs)

    # Should not pass due to NaN close values affecting calculations
    assert len(result["filtered_ohlcv_bundle"]) == 0


@pytest.mark.asyncio
async def test_lod_filter_node_different_atr_windows():
    """Test different ATR window sizes."""
    bars = [
        {"timestamp": i * 86400000, "open": 100 + i*0.5, "high": 105 + i*0.5, "low": 95 + i*0.5, "close": 102 + i*0.5, "volume": 1000}
        for i in range(20)
    ]
    symbol = AssetSymbol("TEST", AssetClass.STOCKS)
    bundle = {symbol: bars}

    # Test with smaller window
    node = LodFilter(id=1, params={"min_lod_distance": 1.0, "atr_window": 5})
    inputs = {"ohlcv_bundle": bundle}
    result = await node.execute(inputs)

    assert "filtered_ohlcv_bundle" in result
    # Should pass with lower threshold
    assert len(result["filtered_ohlcv_bundle"]) == 1


@pytest.mark.asyncio
async def test_lod_filter_node_zero_threshold():
    """Test with zero minimum LoD distance (all should pass)."""
    bars = [
        {"timestamp": i * 86400000, "open": 100, "high": 105, "low": 95, "close": 102, "volume": 1000}
        for i in range(20)
    ]
    symbol = AssetSymbol("TEST", AssetClass.STOCKS)
    bundle = {symbol: bars}

    node = LodFilter(id=1, params={"min_lod_distance": 0.0, "atr_window": 14})
    inputs = {"ohlcv_bundle": bundle}
    result = await node.execute(inputs)

    assert len(result["filtered_ohlcv_bundle"]) == 1


@pytest.mark.asyncio
async def test_lod_filter_node_negative_lod_distance():
    """Test handling of negative LoD distance (should be clamped to 0)."""
    # Create data where close is below low (edge case)
    bars = [
        {"timestamp": i * 86400000, "open": 100, "high": 105, "low": 95, "close": 90, "volume": 1000}
        for i in range(20)
    ]
    symbol = AssetSymbol("NEGATIVE", AssetClass.STOCKS)
    bundle = {symbol: bars}

    node = LodFilter(id=1, params={"min_lod_distance": 0.0, "atr_window": 14})
    inputs = {"ohlcv_bundle": bundle}
    result = await node.execute(inputs)

    # Should still pass since LoD distance is clamped to 0 and 0 >= 0
    assert len(result["filtered_ohlcv_bundle"]) == 1


def test_lod_filter_node_parameter_validation():
    """Test parameter validation in constructor."""
    # Valid parameters
    node = LodFilter(id=1, params={"min_lod_distance": 5.0, "atr_window": 14})
    assert node.params["min_lod_distance"] == 5.0
    assert node.params["atr_window"] == 14

    # Invalid min_lod_distance
    with pytest.raises(ValueError, match="Minimum LoD distance cannot be negative"):
        LodFilter(id=1, params={"min_lod_distance": -1.0, "atr_window": 14})

    # Invalid atr_window
    with pytest.raises(ValueError, match="ATR window must be positive"):
        LodFilter(id=1, params={"min_lod_distance": 3.16, "atr_window": 0})


@pytest.mark.asyncio
async def test_lod_filter_node_progress_reporting():
    """Test that progress is reported during execution."""
    bars = [
        {"timestamp": i * 86400000, "open": 100 + i, "high": 105 + i, "low": 95 + i, "close": 102 + i, "volume": 1000}
        for i in range(20)
    ]
    symbol1 = AssetSymbol("SYMBOL1", AssetClass.STOCKS)
    symbol2 = AssetSymbol("SYMBOL2", AssetClass.STOCKS)
    bundle = {symbol1: bars, symbol2: bars}

    progress_calls = []
    node = LodFilter(id=1, params={"min_lod_distance": 3.16, "atr_window": 14})
    node.set_progress_callback(lambda node_id, progress, text: progress_calls.append((progress, text)))

    inputs = {"ohlcv_bundle": bundle}
    result = await node.execute(inputs)

    # Should have progress calls
    assert len(progress_calls) > 0
    # Final progress should be 100%
    assert any(call[0] == 100.0 for call in progress_calls)


def test_calculate_indicator_no_data():
    """Test _calculate_indicator with empty data."""
    node = LodFilter(id=1, params={"min_lod_distance": 3.16, "atr_window": 14})
    result = node._calculate_indicator([])

    assert result.indicator_type == IndicatorType.LOD
    assert result.error == "No data"
    assert result.values.lines["lod_distance_pct"] == 0.0


def test_calculate_indicator_insufficient_data():
    """Test _calculate_indicator with insufficient data."""
    node = LodFilter(id=1, params={"min_lod_distance": 3.16, "atr_window": 14})
    short_data = [
        {"timestamp": i * 86400000, "open": 100, "high": 105, "low": 95, "close": 102, "volume": 1000}
        for i in range(10)
    ]
    result = node._calculate_indicator(short_data)

    assert result.indicator_type == IndicatorType.LOD
    assert "Insufficient data" in result.error
    assert result.values.lines["lod_distance_pct"] == 0.0


def test_calculate_indicator_valid_data():
    """Test _calculate_indicator with valid data."""
    node = LodFilter(id=1, params={"min_lod_distance": 3.16, "atr_window": 14})
    valid_data = [
        {"timestamp": i * 86400000, "open": 100 + i*0.5, "high": 105 + i*0.5, "low": 95 + i*0.5, "close": 102 + i*0.5, "volume": 1000}
        for i in range(20)
    ]
    # Modify last bar to have distance from low
    valid_data[-1] = {"timestamp": 19 * 86400000, "open": 110, "high": 115, "low": 108, "close": 112, "volume": 1000}
    result = node._calculate_indicator(valid_data)

    assert result.indicator_type == IndicatorType.LOD
    assert result.error is None
    assert result.values.lines["lod_distance_pct"] > 0
    assert "current_price" in result.values.lines
    assert "low_of_day" in result.values.lines
    assert "atr" in result.values.lines


def test_should_pass_filter_with_error():
    """Test _should_pass_filter with error in result."""
    node = LodFilter(id=1, params={"min_lod_distance": 3.16, "atr_window": 14})
    error_result = IndicatorResult(
        indicator_type=IndicatorType.LOD,
        values=IndicatorValue(lines={"lod_distance_pct": 10.0}),
        error="Test error"
    )

    assert not node._should_pass_filter(error_result)


def test_should_pass_filter_missing_value():
    """Test _should_pass_filter with missing lod_distance_pct."""
    node = LodFilter(id=1, params={"min_lod_distance": 3.16, "atr_window": 14})
    missing_result = IndicatorResult(
        indicator_type=IndicatorType.LOD,
        values=IndicatorValue(lines={"other": 5.0})
    )

    assert not node._should_pass_filter(missing_result)


def test_should_pass_filter_nan_value():
    """Test _should_pass_filter with NaN lod_distance_pct."""
    node = LodFilter(id=1, params={"min_lod_distance": 3.16, "atr_window": 14})
    nan_result = IndicatorResult(
        indicator_type=IndicatorType.LOD,
        values=IndicatorValue(lines={"lod_distance_pct": float('nan')})
    )

    assert not node._should_pass_filter(nan_result)


def test_should_pass_filter_above_threshold():
    """Test _should_pass_filter with value above threshold."""
    node = LodFilter(id=1, params={"min_lod_distance": 5.0, "atr_window": 14})
    pass_result = IndicatorResult(
        indicator_type=IndicatorType.LOD,
        values=IndicatorValue(lines={"lod_distance_pct": 10.0})
    )

    assert node._should_pass_filter(pass_result)


def test_should_pass_filter_below_threshold():
    """Test _should_pass_filter with value below threshold."""
    node = LodFilter(id=1, params={"min_lod_distance": 15.0, "atr_window": 14})
    fail_result = IndicatorResult(
        indicator_type=IndicatorType.LOD,
        values=IndicatorValue(lines={"lod_distance_pct": 10.0})
    )

    assert not node._should_pass_filter(fail_result)
