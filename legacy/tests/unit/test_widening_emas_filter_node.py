import pytest

from core.types_registry import (
    AssetClass,
    AssetSymbol,
    IndicatorResult,
    IndicatorType,
    IndicatorValue,
    OHLCVBar,
)
from nodes.core.market.filters.widening_emas_filter_node import WideningEMAsFilter


@pytest.fixture
def widening_emas_bundle() -> dict[AssetSymbol, list[OHLCVBar]]:
    """Create bundle with widening EMAs (bullish divergence)."""
    # Create data where fast EMA moves away from slow EMA
    bars = []
    base_ts = 1672531200000  # 2023-01-01 00:00:00

    # Start with stable prices, then accelerate upwards
    for i in range(35):
        ts = base_ts + i * 86400000
        # Accelerating upward trend
        close = 100 + i * 0.5 + (i > 20) * (i - 20) * 2
        bars.append(
            {
                "timestamp": ts,
                "open": close - 1,
                "high": close + 2,
                "low": close - 2,
                "close": close,
                "volume": 1000,
            }
        )

    symbol = AssetSymbol("WIDENING", AssetClass.STOCKS)
    return {symbol: bars}


@pytest.fixture
def narrowing_emas_bundle() -> dict[AssetSymbol, list[OHLCVBar]]:
    """Create bundle with narrowing EMAs (convergence)."""
    # Create data where fast EMA converges with slow EMA
    bars = []
    base_ts = 1672531200000

    # Start with fast upward trend, then slow down
    for i in range(35):
        ts = base_ts + i * 86400000
        # Slowing upward trend
        close = 100 + i * 2 - (i > 20) * (i - 20) * 1.5
        bars.append(
            {
                "timestamp": ts,
                "open": close - 1,
                "high": close + 2,
                "low": close - 2,
                "close": close,
                "volume": 1000,
            }
        )

    symbol = AssetSymbol("NARROWING", AssetClass.STOCKS)
    return {symbol: bars}


@pytest.fixture
def flat_price_bundle() -> dict[AssetSymbol, list[OHLCVBar]]:
    """Create bundle with flat prices (no EMA movement)."""
    bars = []
    base_ts = 1672531200000

    for i in range(35):
        ts = base_ts + i * 86400000
        bars.append(
            {
                "timestamp": ts,
                "open": 100,
                "high": 100.5,
                "low": 99.5,
                "close": 100,
                "volume": 1000,
            }
        )

    symbol = AssetSymbol("FLAT", AssetClass.STOCKS)
    return {symbol: bars}


@pytest.fixture
def insufficient_data_bundle() -> dict[AssetSymbol, list[OHLCVBar]]:
    """Create bundle with insufficient data."""
    bars = []
    base_ts = 1672531200000

    # Only 10 bars, not enough for EMA(30)
    for i in range(10):
        ts = base_ts + i * 86400000
        bars.append(
            {
                "timestamp": ts,
                "open": 100 + i,
                "high": 105 + i,
                "low": 95 + i,
                "close": 102 + i,
                "volume": 1000,
            }
        )

    symbol = AssetSymbol("SHORT", AssetClass.STOCKS)
    return {symbol: bars}


@pytest.mark.asyncio
async def test_widening_emas_filter_happy_path_widening(widening_emas_bundle):
    """Test that assets with widening EMAs pass when widening=True."""
    node = WideningEMAsFilter(
        id=1, params={"fast_ema_period": 10, "slow_ema_period": 30, "widening": True}
    )
    inputs = {"ohlcv_bundle": widening_emas_bundle}
    result = await node.execute(inputs)

    assert "filtered_ohlcv_bundle" in result
    filtered = result["filtered_ohlcv_bundle"]
    assert len(filtered) == 1
    symbol = AssetSymbol("WIDENING", AssetClass.STOCKS)
    assert symbol in filtered


@pytest.mark.asyncio
async def test_widening_emas_filter_happy_path_narrowing(narrowing_emas_bundle):
    """Test that assets with narrowing EMAs pass when widening=False."""
    node = WideningEMAsFilter(
        id=1, params={"fast_ema_period": 10, "slow_ema_period": 30, "widening": False}
    )
    inputs = {"ohlcv_bundle": narrowing_emas_bundle}
    result = await node.execute(inputs)

    assert "filtered_ohlcv_bundle" in result
    filtered = result["filtered_ohlcv_bundle"]
    assert len(filtered) == 1
    symbol = AssetSymbol("NARROWING", AssetClass.STOCKS)
    assert symbol in filtered


@pytest.mark.asyncio
async def test_widening_emas_filter_widening_does_not_pass_narrowing(narrowing_emas_bundle):
    """Test that narrowing EMAs don't pass when widening=True."""
    node = WideningEMAsFilter(
        id=1, params={"fast_ema_period": 10, "slow_ema_period": 30, "widening": True}
    )
    inputs = {"ohlcv_bundle": narrowing_emas_bundle}
    result = await node.execute(inputs)

    assert "filtered_ohlcv_bundle" in result
    filtered = result["filtered_ohlcv_bundle"]
    assert len(filtered) == 0


@pytest.mark.asyncio
async def test_widening_emas_filter_narrowing_does_not_pass_widening(widening_emas_bundle):
    """Test that widening EMAs don't pass when widening=False."""
    node = WideningEMAsFilter(
        id=1, params={"fast_ema_period": 10, "slow_ema_period": 30, "widening": False}
    )
    inputs = {"ohlcv_bundle": widening_emas_bundle}
    result = await node.execute(inputs)

    assert "filtered_ohlcv_bundle" in result
    filtered = result["filtered_ohlcv_bundle"]
    assert len(filtered) == 0


@pytest.mark.asyncio
async def test_widening_emas_filter_empty_bundle():
    """Test behavior with empty input bundle."""
    node = WideningEMAsFilter(
        id=1, params={"fast_ema_period": 10, "slow_ema_period": 30, "widening": True}
    )
    inputs = {"ohlcv_bundle": {}}
    result = await node.execute(inputs)

    assert result["filtered_ohlcv_bundle"] == {}


@pytest.mark.asyncio
async def test_widening_emas_filter_insufficient_data(insufficient_data_bundle):
    """Test behavior when data is insufficient for EMA calculation."""
    node = WideningEMAsFilter(
        id=1, params={"fast_ema_period": 10, "slow_ema_period": 30, "widening": True}
    )
    inputs = {"ohlcv_bundle": insufficient_data_bundle}
    result = await node.execute(inputs)

    # Should not pass due to insufficient data
    assert len(result["filtered_ohlcv_bundle"]) == 0


@pytest.mark.asyncio
async def test_widening_emas_filter_no_data_symbol():
    """Test behavior with symbol having no OHLCV data."""
    symbol = AssetSymbol("EMPTY", AssetClass.STOCKS)
    bundle = {symbol: []}

    node = WideningEMAsFilter(
        id=1, params={"fast_ema_period": 10, "slow_ema_period": 30, "widening": True}
    )
    inputs = {"ohlcv_bundle": bundle}
    result = await node.execute(inputs)

    assert len(result["filtered_ohlcv_bundle"]) == 0


@pytest.mark.asyncio
async def test_widening_emas_filter_flat_prices(flat_price_bundle):
    """Test behavior with flat prices (no EMA movement)."""
    node = WideningEMAsFilter(
        id=1, params={"fast_ema_period": 10, "slow_ema_period": 30, "widening": True}
    )
    inputs = {"ohlcv_bundle": flat_price_bundle}
    result = await node.execute(inputs)

    # With flat prices, EMAs won't widen or narrow significantly
    # Should not pass widening filter
    assert len(result["filtered_ohlcv_bundle"]) == 0


@pytest.mark.asyncio
async def test_widening_emas_filter_string_boolean_true(widening_emas_bundle):
    """Test handling of string 'true' parameter."""
    node = WideningEMAsFilter(
        id=1, params={"fast_ema_period": 10, "slow_ema_period": 30, "widening": "true"}
    )
    inputs = {"ohlcv_bundle": widening_emas_bundle}
    result = await node.execute(inputs)

    assert len(result["filtered_ohlcv_bundle"]) == 1


@pytest.mark.asyncio
async def test_widening_emas_filter_string_boolean_false(narrowing_emas_bundle):
    """Test handling of string 'false' parameter."""
    node = WideningEMAsFilter(
        id=1, params={"fast_ema_period": 10, "slow_ema_period": 30, "widening": "false"}
    )
    inputs = {"ohlcv_bundle": narrowing_emas_bundle}
    result = await node.execute(inputs)

    assert len(result["filtered_ohlcv_bundle"]) == 1


@pytest.mark.asyncio
async def test_widening_emas_filter_different_periods():
    """Test with different EMA periods."""
    bars = []
    base_ts = 1672531200000

    # Create upward trending data
    for i in range(50):
        ts = base_ts + i * 86400000
        close = 100 + i * 1.5
        bars.append(
            {
                "timestamp": ts,
                "open": close - 1,
                "high": close + 2,
                "low": close - 2,
                "close": close,
                "volume": 1000,
            }
        )

    symbol = AssetSymbol("TREND", AssetClass.STOCKS)
    bundle = {symbol: bars}

    node = WideningEMAsFilter(
        id=1, params={"fast_ema_period": 5, "slow_ema_period": 20, "widening": True}
    )
    inputs = {"ohlcv_bundle": bundle}
    result = await node.execute(inputs)

    assert "filtered_ohlcv_bundle" in result
    assert len(result["filtered_ohlcv_bundle"]) == 1


@pytest.mark.asyncio
async def test_widening_emas_filter_mixed_bundle(widening_emas_bundle, narrowing_emas_bundle):
    """Test filtering with mixed bundle of widening and narrowing assets."""
    mixed_bundle = {**widening_emas_bundle, **narrowing_emas_bundle}

    node = WideningEMAsFilter(
        id=1, params={"fast_ema_period": 10, "slow_ema_period": 30, "widening": True}
    )
    inputs = {"ohlcv_bundle": mixed_bundle}
    result = await node.execute(inputs)

    assert "filtered_ohlcv_bundle" in result
    filtered = result["filtered_ohlcv_bundle"]
    # Should only contain the widening symbol
    assert len(filtered) == 1
    widening_symbol = AssetSymbol("WIDENING", AssetClass.STOCKS)
    narrowing_symbol = AssetSymbol("NARROWING", AssetClass.STOCKS)
    assert widening_symbol in filtered
    assert narrowing_symbol not in filtered


@pytest.mark.asyncio
async def test_widening_emas_filter_progress_reporting(widening_emas_bundle, narrowing_emas_bundle):
    """Test that progress is reported during execution."""
    mixed_bundle = {**widening_emas_bundle, **narrowing_emas_bundle}

    progress_calls = []
    node = WideningEMAsFilter(
        id=1, params={"fast_ema_period": 10, "slow_ema_period": 30, "widening": True}
    )
    node.set_progress_callback(
        lambda event: progress_calls.append((event.get("progress", 0.0), event.get("text", "")))
    )

    inputs = {"ohlcv_bundle": mixed_bundle}
    await node.execute(inputs)

    # Should have progress calls
    assert len(progress_calls) > 0
    # Final progress should be 100%
    assert any(call[0] == 100.0 for call in progress_calls)


def test_widening_emas_filter_parameter_validation():
    """Test parameter validation in constructor."""
    # Valid parameters
    node = WideningEMAsFilter(
        id=1, params={"fast_ema_period": 10, "slow_ema_period": 30, "widening": True}
    )
    assert node.params["fast_ema_period"] == 10
    assert node.params["slow_ema_period"] == 30
    assert node.params["widening"] is True

    # Invalid: fast >= slow
    with pytest.raises(ValueError, match="Fast EMA period must be less than slow EMA period"):
        WideningEMAsFilter(
            id=1, params={"fast_ema_period": 30, "slow_ema_period": 10, "widening": True}
        )

    # Invalid: fast < 2
    with pytest.raises(ValueError, match="Fast EMA period must be at least 2"):
        WideningEMAsFilter(
            id=1, params={"fast_ema_period": 1, "slow_ema_period": 30, "widening": True}
        )

    # Invalid: slow < 2
    with pytest.raises(ValueError, match="Slow EMA period must be at least 2"):
        WideningEMAsFilter(
            id=1, params={"fast_ema_period": 10, "slow_ema_period": 1, "widening": True}
        )


def test_calculate_indicator_no_data():
    """Test _calculate_indicator with empty data."""
    node = WideningEMAsFilter(
        id=1, params={"fast_ema_period": 10, "slow_ema_period": 30, "widening": True}
    )
    result = node._calculate_indicator([])  # type: ignore

    assert result.indicator_type == IndicatorType.EMA
    assert result.error == "No data"
    assert result.values.lines["ema_difference"] == 0.0
    assert result.values.lines["is_widening"] is False


def test_calculate_indicator_insufficient_data():
    """Test _calculate_indicator with insufficient data."""
    node = WideningEMAsFilter(
        id=1, params={"fast_ema_period": 10, "slow_ema_period": 30, "widening": True}
    )
    short_data = [
        {
            "timestamp": i * 86400000,
            "open": 100,
            "high": 105,
            "low": 95,
            "close": 102,
            "volume": 1000,
        }
        for i in range(10)
    ]
    result = node._calculate_indicator(short_data)  # type: ignore

    assert result.indicator_type == IndicatorType.EMA
    assert result.error is not None and "Insufficient data" in result.error
    assert result.values.lines["ema_difference"] == 0.0
    assert result.values.lines["is_widening"] is False


def test_calculate_indicator_valid_data():
    """Test _calculate_indicator with valid data."""
    node = WideningEMAsFilter(
        id=1, params={"fast_ema_period": 10, "slow_ema_period": 30, "widening": True}
    )
    valid_data = [
        {
            "timestamp": i * 86400000,
            "open": 100 + i * 1.5,
            "high": 105 + i * 1.5,
            "low": 95 + i * 1.5,
            "close": 102 + i * 1.5,
            "volume": 1000,
        }
        for i in range(35)
    ]
    result = node._calculate_indicator(valid_data)  # type: ignore

    assert result.indicator_type == IndicatorType.EMA
    assert result.error is None
    assert "ema_difference" in result.values.lines
    assert "is_widening" in result.values.lines
    assert "fast_ema" in result.values.lines
    assert "slow_ema" in result.values.lines
    assert "prev_difference" in result.values.lines


def test_should_pass_filter_with_error():
    """Test _should_pass_filter with error in result."""
    node = WideningEMAsFilter(
        id=1, params={"fast_ema_period": 10, "slow_ema_period": 30, "widening": True}
    )
    error_result = IndicatorResult(
        indicator_type=IndicatorType.EMA,
        values=IndicatorValue(lines={"is_widening": True}),
        error="Test error",
    )

    assert not node._should_pass_filter(error_result)  # type: ignore


def test_should_pass_filter_missing_value():
    """Test _should_pass_filter with missing is_widening."""
    node = WideningEMAsFilter(
        id=1, params={"fast_ema_period": 10, "slow_ema_period": 30, "widening": True}
    )
    missing_result = IndicatorResult(
        indicator_type=IndicatorType.EMA, values=IndicatorValue(lines={"other": True})
    )

    assert not node._should_pass_filter(missing_result)  # type: ignore


def test_should_pass_filter_widening_true_and_is_widening_true():
    """Test _should_pass_filter when widening=True and is_widening=True."""
    node = WideningEMAsFilter(
        id=1, params={"fast_ema_period": 10, "slow_ema_period": 30, "widening": True}
    )
    pass_result = IndicatorResult(
        indicator_type=IndicatorType.EMA,
        values=IndicatorValue(lines={"is_widening": True}),
    )

    assert node._should_pass_filter(pass_result)  # type: ignore


def test_should_pass_filter_widening_true_and_is_widening_false():
    """Test _should_pass_filter when widening=True and is_widening=False."""
    node = WideningEMAsFilter(
        id=1, params={"fast_ema_period": 10, "slow_ema_period": 30, "widening": True}
    )
    fail_result = IndicatorResult(
        indicator_type=IndicatorType.EMA,
        values=IndicatorValue(lines={"is_widening": False}),
    )

    assert not node._should_pass_filter(fail_result)  # type: ignore


def test_should_pass_filter_widening_false_and_is_widening_false():
    """Test _should_pass_filter when widening=False and is_widening=False."""
    node = WideningEMAsFilter(
        id=1, params={"fast_ema_period": 10, "slow_ema_period": 30, "widening": False}
    )
    pass_result = IndicatorResult(
        indicator_type=IndicatorType.EMA,
        values=IndicatorValue(lines={"is_widening": False}),
    )

    assert node._should_pass_filter(pass_result)  # type: ignore


def test_should_pass_filter_widening_false_and_is_widening_true():
    """Test _should_pass_filter when widening=False and is_widening=True."""
    node = WideningEMAsFilter(
        id=1, params={"fast_ema_period": 10, "slow_ema_period": 30, "widening": False}
    )
    fail_result = IndicatorResult(
        indicator_type=IndicatorType.EMA,
        values=IndicatorValue(lines={"is_widening": True}),
    )

    assert not node._should_pass_filter(fail_result)  # type: ignore


def test_should_pass_filter_string_true():
    """Test _should_pass_filter with string 'true' parameter."""
    node = WideningEMAsFilter(
        id=1, params={"fast_ema_period": 10, "slow_ema_period": 30, "widening": "true"}
    )
    pass_result = IndicatorResult(
        indicator_type=IndicatorType.EMA,
        values=IndicatorValue(lines={"is_widening": True}),
    )

    assert node._should_pass_filter(pass_result)  # type: ignore


def test_should_pass_filter_string_false():
    """Test _should_pass_filter with string 'false' parameter."""
    node = WideningEMAsFilter(
        id=1, params={"fast_ema_period": 10, "slow_ema_period": 30, "widening": "false"}
    )
    pass_result = IndicatorResult(
        indicator_type=IndicatorType.EMA,
        values=IndicatorValue(lines={"is_widening": False}),
    )

    assert node._should_pass_filter(pass_result)  # type: ignore


@pytest.mark.asyncio
async def test_widening_emas_filter_zero_difference():
    """Test behavior when EMA difference is zero (no change)."""
    bars = []
    base_ts = 1672531200000

    # Create data where EMAs remain constant
    for i in range(35):
        ts = base_ts + i * 86400000
        bars.append(
            {
                "timestamp": ts,
                "open": 100,
                "high": 100.5,
                "low": 99.5,
                "close": 100,
                "volume": 1000,
            }
        )

    symbol = AssetSymbol("CONSTANT", AssetClass.STOCKS)
    bundle = {symbol: bars}

    node = WideningEMAsFilter(
        id=1, params={"fast_ema_period": 10, "slow_ema_period": 30, "widening": True}
    )
    inputs = {"ohlcv_bundle": bundle}
    result = await node.execute(inputs)

    # With constant prices, difference won't widen or narrow
    assert len(result["filtered_ohlcv_bundle"]) == 0


def test_widening_emas_filter_equal_periods():
    """Test with equal fast and slow periods (should fail validation)."""
    # Should raise error during initialization
    with pytest.raises(ValueError, match="Fast EMA period must be less than slow EMA period"):
        WideningEMAsFilter(
            id=1, params={"fast_ema_period": 20, "slow_ema_period": 20, "widening": True}
        )


@pytest.mark.asyncio
async def test_widening_emas_filter_single_bar():
    """Test with single bar data."""
    single_bar = [
        {
            "timestamp": 1672531200000,
            "open": 100,
            "high": 101,
            "low": 99,
            "close": 100,
            "volume": 1000,
        }
    ]

    symbol = AssetSymbol("SINGLE", AssetClass.STOCKS)
    bundle = {symbol: single_bar}

    node = WideningEMAsFilter(
        id=1, params={"fast_ema_period": 10, "slow_ema_period": 30, "widening": True}
    )
    inputs = {"ohlcv_bundle": bundle}
    result = await node.execute(inputs)

    assert symbol not in result["filtered_ohlcv_bundle"]


@pytest.mark.asyncio
async def test_widening_emas_filter_downward_trend():
    """Test with downward trending data."""
    bars = []
    base_ts = 1672531200000

    # Create downward trend
    for i in range(35):
        ts = base_ts + i * 86400000
        close = 100 - i * 0.5
        bars.append(
            {
                "timestamp": ts,
                "open": close - 1,
                "high": close + 2,
                "low": close - 2,
                "close": close,
                "volume": 1000,
            }
        )

    symbol = AssetSymbol("DOWN", AssetClass.STOCKS)
    bundle = {symbol: bars}

    node = WideningEMAsFilter(
        id=1, params={"fast_ema_period": 10, "slow_ema_period": 30, "widening": True}
    )
    inputs = {"ohlcv_bundle": bundle}
    result = await node.execute(inputs)

    # With steady downward trend, EMAs might actually converge
    # The exact behavior depends on EMA calculation
    assert "filtered_ohlcv_bundle" in result


@pytest.mark.asyncio
async def test_widening_emas_filter_volatile_data():
    """Test with highly volatile data."""
    bars = []
    base_ts = 1672531200000

    # Create volatile data with big swings
    for i in range(35):
        ts = base_ts + i * 86400000
        # Large swings in price
        close = 100 + (i % 5) * 10 - 20
        bars.append(
            {
                "timestamp": ts,
                "open": close - 2,
                "high": close + 5,
                "low": close - 5,
                "close": close,
                "volume": 1000,
            }
        )

    symbol = AssetSymbol("VOLATILE", AssetClass.STOCKS)
    bundle = {symbol: bars}

    node = WideningEMAsFilter(
        id=1, params={"fast_ema_period": 10, "slow_ema_period": 30, "widening": True}
    )
    inputs = {"ohlcv_bundle": bundle}
    result = await node.execute(inputs)

    # Should handle volatile data without crashing
    assert "filtered_ohlcv_bundle" in result


def test_calculate_indicator_none_values_from_calculator():
    """Test handling when calculator returns None values."""
    node = WideningEMAsFilter(
        id=1, params={"fast_ema_period": 10, "slow_ema_period": 30, "widening": True}
    )

    # Create data that's borderline - might return None from calculator
    borderline_data = [
        {
            "timestamp": i * 86400000,
            "open": 100,
            "high": 105,
            "low": 95,
            "close": 102,
            "volume": 1000,
        }
        for i in range(15)  # Just enough for EMA(10) but not EMA(30)
    ]

    result = node._calculate_indicator(borderline_data)  # type: ignore

    # Should handle gracefully
    assert result.indicator_type == IndicatorType.EMA
    # May have error or may have None values
    assert result.error is not None or result.values.lines.get("ema_difference") is not None


@pytest.mark.asyncio
async def test_widening_emas_filter_extreme_values():
    """Test with extreme price values."""
    bars = []
    base_ts = 1672531200000

    # Create data with very large values
    for i in range(35):
        ts = base_ts + i * 86400000
        close = 1000000 + i * 1000
        bars.append(
            {
                "timestamp": ts,
                "open": close - 100,
                "high": close + 200,
                "low": close - 200,
                "close": close,
                "volume": 1000000,
            }
        )

    symbol = AssetSymbol("EXTREME", AssetClass.STOCKS)
    bundle = {symbol: bars}

    node = WideningEMAsFilter(
        id=1, params={"fast_ema_period": 10, "slow_ema_period": 30, "widening": True}
    )
    inputs = {"ohlcv_bundle": bundle}
    result = await node.execute(inputs)

    # Should handle extreme values without crashing
    assert "filtered_ohlcv_bundle" in result
