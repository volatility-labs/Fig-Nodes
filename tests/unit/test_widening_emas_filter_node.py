import pytest
from unittest.mock import patch, MagicMock
from typing import Dict, List
from nodes.core.market.filters.widening_emas_filter_node import WideningEMAsFilter
from core.types_registry import AssetSymbol, OHLCVBar, IndicatorType, IndicatorResult, IndicatorValue, AssetClass


@pytest.fixture
def widening_emas_bundle() -> Dict[AssetSymbol, List[OHLCVBar]]:
    """Create bundle with EMAs that are widening (diverging)."""
    # Create data where the price trend accelerates, causing EMA difference to widen
    bars = []
    for i in range(50):
        # Start with steady trend, then accelerate
        if i < 30:
            price = 100 + i * 0.1
        else:
            price = 103 + (i - 30) * 0.5  # Accelerate trend

        bars.append({
            "timestamp": i * 86400000,
            "open": price - 1,
            "high": price + 2,
            "low": price - 3,
            "close": price,
            "volume": 1000
        })
    symbol = AssetSymbol("WIDENING_EMAS", AssetClass.STOCKS)
    return {symbol: bars}


@pytest.fixture
def narrowing_emas_bundle() -> Dict[AssetSymbol, List[OHLCVBar]]:
    """Create bundle with EMAs that are narrowing (converging)."""
    # Create data where EMAs converge by having an oscillating pattern that dampens
    bars = []
    for i in range(50):
        # Create dampening oscillation that causes EMA convergence
        oscillation = 5 * (0.9 ** (i // 5)) * ((-1) ** i)  # Dampening oscillation
        price = 100 + oscillation

        bars.append({
            "timestamp": i * 86400000,
            "open": price - 1,
            "high": price + 2,
            "low": price - 3,
            "close": price,
            "volume": 1000
        })
    symbol = AssetSymbol("NARROWING_EMAS", AssetClass.STOCKS)
    return {symbol: bars}


@pytest.mark.asyncio
async def test_widening_emas_filter_widening_true(widening_emas_bundle):
    """Test that assets with widening EMAs pass when widening=True."""
    node = WideningEMAsFilter(id=1, params={"fast_ema_period": 10, "slow_ema_period": 30, "widening": True})
    inputs = {"ohlcv_bundle": widening_emas_bundle}
    result = await node.execute(inputs)

    assert "filtered_ohlcv_bundle" in result
    filtered = result["filtered_ohlcv_bundle"]
    assert len(filtered) == 1
    symbol = AssetSymbol("WIDENING_EMAS", AssetClass.STOCKS)
    assert symbol in filtered


@pytest.mark.asyncio
async def test_widening_emas_filter_widening_false(narrowing_emas_bundle):
    """Test that assets with narrowing EMAs pass when widening=False."""
    node = WideningEMAsFilter(id=1, params={"fast_ema_period": 10, "slow_ema_period": 30, "widening": False})
    inputs = {"ohlcv_bundle": narrowing_emas_bundle}
    result = await node.execute(inputs)

    assert "filtered_ohlcv_bundle" in result
    filtered = result["filtered_ohlcv_bundle"]
    assert len(filtered) == 1
    symbol = AssetSymbol("NARROWING_EMAS", AssetClass.STOCKS)
    assert symbol in filtered


@pytest.mark.asyncio
async def test_widening_emas_filter_mixed_bundle(widening_emas_bundle, narrowing_emas_bundle):
    """Test filtering with mixed bundle of widening and narrowing EMAs."""
    mixed_bundle = {**widening_emas_bundle, **narrowing_emas_bundle}

    # Test widening=True (should only pass widening EMAs)
    node = WideningEMAsFilter(id=1, params={"fast_ema_period": 10, "slow_ema_period": 30, "widening": True})
    inputs = {"ohlcv_bundle": mixed_bundle}
    result = await node.execute(inputs)

    assert "filtered_ohlcv_bundle" in result
    filtered = result["filtered_ohlcv_bundle"]
    assert len(filtered) == 1
    widening_symbol = AssetSymbol("WIDENING_EMAS", AssetClass.STOCKS)
    narrowing_symbol = AssetSymbol("NARROWING_EMAS", AssetClass.STOCKS)
    assert widening_symbol in filtered
    assert narrowing_symbol not in filtered


@pytest.mark.asyncio
async def test_widening_emas_filter_empty_bundle():
    """Test behavior with empty input bundle."""
    node = WideningEMAsFilter(id=1, params={"fast_ema_period": 10, "slow_ema_period": 30, "widening": True})
    inputs = {"ohlcv_bundle": {}}
    result = await node.execute(inputs)

    assert result["filtered_ohlcv_bundle"] == {}


@pytest.mark.asyncio
async def test_widening_emas_filter_insufficient_data():
    """Test behavior when data is insufficient for EMA calculation."""
    short_bars = [
        {"timestamp": i * 86400000, "open": 100, "high": 105, "low": 95, "close": 102, "volume": 1000}
        for i in range(10)  # Less than needed for EMA(30) + comparison
    ]
    symbol = AssetSymbol("SHORT_DATA", AssetClass.STOCKS)
    bundle = {symbol: short_bars}

    node = WideningEMAsFilter(id=1, params={"fast_ema_period": 10, "slow_ema_period": 30, "widening": True})
    inputs = {"ohlcv_bundle": bundle}
    result = await node.execute(inputs)

    # Should not pass due to insufficient data
    assert len(result["filtered_ohlcv_bundle"]) == 0


@pytest.mark.asyncio
async def test_widening_emas_filter_no_data_symbol():
    """Test behavior with symbol having no OHLCV data."""
    symbol = AssetSymbol("EMPTY", AssetClass.STOCKS)
    bundle = {symbol: []}

    node = WideningEMAsFilter(id=1, params={"fast_ema_period": 10, "slow_ema_period": 30, "widening": True})
    inputs = {"ohlcv_bundle": bundle}
    result = await node.execute(inputs)

    assert len(result["filtered_ohlcv_bundle"]) == 0


@pytest.mark.asyncio
async def test_widening_emas_filter_different_periods():
    """Test with different EMA periods."""
    # Use widening data pattern
    bars = []
    for i in range(50):
        if i < 30:
            price = 100 + i * 0.1
        else:
            price = 103 + (i - 30) * 0.5
        bars.append({
            "timestamp": i * 86400000,
            "open": price - 1,
            "high": price + 2,
            "low": price - 3,
            "close": price,
            "volume": 1000
        })

    symbol = AssetSymbol("TEST", AssetClass.STOCKS)
    bundle = {symbol: bars}

    # Test with EMA(5) and EMA(20)
    node = WideningEMAsFilter(id=1, params={"fast_ema_period": 5, "slow_ema_period": 20, "widening": True})
    inputs = {"ohlcv_bundle": bundle}
    result = await node.execute(inputs)

    assert "filtered_ohlcv_bundle" in result
    # Should pass with the widening data
    assert len(result["filtered_ohlcv_bundle"]) == 1


def test_widening_emas_filter_parameter_validation():
    """Test parameter validation in constructor."""
    # Valid parameters
    node = WideningEMAsFilter(id=1, params={"fast_ema_period": 10, "slow_ema_period": 30, "widening": True})
    assert node.params["fast_ema_period"] == 10
    assert node.params["slow_ema_period"] == 30
    assert node.params["widening"] == True

    # Invalid: fast >= slow
    with pytest.raises(ValueError, match="Fast EMA period must be less than slow EMA period"):
        WideningEMAsFilter(id=1, params={"fast_ema_period": 30, "slow_ema_period": 10, "widening": True})

    # Invalid: periods too small
    with pytest.raises(ValueError, match="EMA periods must be at least 2"):
        WideningEMAsFilter(id=1, params={"fast_ema_period": 1, "slow_ema_period": 30, "widening": True})


@pytest.mark.asyncio
async def test_widening_emas_filter_progress_reporting():
    """Test that progress is reported during execution."""
    bars = [
        {"timestamp": i * 86400000, "open": 100 + i, "high": 105 + i, "low": 95 + i, "close": 102 + i, "volume": 1000}
        for i in range(50)
    ]
    symbol1 = AssetSymbol("SYMBOL1", AssetClass.STOCKS)
    symbol2 = AssetSymbol("SYMBOL2", AssetClass.STOCKS)
    bundle = {symbol1: bars, symbol2: bars}

    progress_calls = []
    node = WideningEMAsFilter(id=1, params={"fast_ema_period": 10, "slow_ema_period": 30, "widening": True})
    node.set_progress_callback(lambda node_id, progress, text: progress_calls.append((progress, text)))

    inputs = {"ohlcv_bundle": bundle}
    result = await node.execute(inputs)

    # Should have progress calls
    assert len(progress_calls) > 0
    # Final progress should be 100%
    assert any(call[0] == 100.0 for call in progress_calls)


def test_calculate_indicator_no_data():
    """Test _calculate_indicator with empty data."""
    node = WideningEMAsFilter(id=1, params={"fast_ema_period": 10, "slow_ema_period": 30, "widening": True})
    result = node._calculate_indicator([])

    assert result.indicator_type == IndicatorType.EMA
    assert result.error == "No data"
    assert result.values.lines["ema_difference"] == 0.0
    assert result.values.lines["is_widening"] == False


def test_calculate_indicator_insufficient_data():
    """Test _calculate_indicator with insufficient data."""
    node = WideningEMAsFilter(id=1, params={"fast_ema_period": 10, "slow_ema_period": 30, "widening": True})
    short_data = [
        {"timestamp": i * 86400000, "open": 100, "high": 105, "low": 95, "close": 102, "volume": 1000}
        for i in range(15)
    ]
    result = node._calculate_indicator(short_data)

    assert result.indicator_type == IndicatorType.EMA
    assert "Insufficient data" in result.error
    assert result.values.lines["ema_difference"] == 0.0
    assert result.values.lines["is_widening"] == False


def test_calculate_indicator_valid_data():
    """Test _calculate_indicator with valid data."""
    node = WideningEMAsFilter(id=1, params={"fast_ema_period": 10, "slow_ema_period": 30, "widening": True})
    valid_data = [
        {"timestamp": i * 86400000, "open": 100 + i*0.5, "high": 105 + i*0.5, "low": 95 + i*0.5, "close": 102 + i*0.5, "volume": 1000}
        for i in range(50)
    ]
    result = node._calculate_indicator(valid_data)

    assert result.indicator_type == IndicatorType.EMA
    assert result.error is None
    assert "ema_difference" in result.values.lines
    assert "is_widening" in result.values.lines
    assert "fast_ema" in result.values.lines
    assert "slow_ema" in result.values.lines
    assert "prev_difference" in result.values.lines


def test_should_pass_filter_with_error():
    """Test _should_pass_filter with error in result."""
    node = WideningEMAsFilter(id=1, params={"fast_ema_period": 10, "slow_ema_period": 30, "widening": True})
    error_result = IndicatorResult(
        indicator_type=IndicatorType.EMA,
        values=IndicatorValue(lines={"ema_difference": 1.0, "is_widening": True}),
        error="Test error"
    )

    assert not node._should_pass_filter(error_result)


def test_should_pass_filter_missing_value():
    """Test _should_pass_filter with missing is_widening."""
    node = WideningEMAsFilter(id=1, params={"fast_ema_period": 10, "slow_ema_period": 30, "widening": True})
    missing_result = IndicatorResult(
        indicator_type=IndicatorType.EMA,
        values=IndicatorValue(lines={"ema_difference": 1.0})
    )

    assert not node._should_pass_filter(missing_result)


def test_should_pass_filter_widening_match():
    """Test _should_pass_filter when widening matches parameter."""
    node = WideningEMAsFilter(id=1, params={"fast_ema_period": 10, "slow_ema_period": 30, "widening": True})
    match_result = IndicatorResult(
        indicator_type=IndicatorType.EMA,
        values=IndicatorValue(lines={"ema_difference": 1.0, "is_widening": True})
    )

    assert node._should_pass_filter(match_result)


def test_should_pass_filter_widening_no_match():
    """Test _should_pass_filter when widening doesn't match parameter."""
    node = WideningEMAsFilter(id=1, params={"fast_ema_period": 10, "slow_ema_period": 30, "widening": True})
    no_match_result = IndicatorResult(
        indicator_type=IndicatorType.EMA,
        values=IndicatorValue(lines={"ema_difference": 1.0, "is_widening": False})
    )

    assert not node._should_pass_filter(no_match_result)
