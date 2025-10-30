import pytest
import pandas as pd
import numpy as np
from typing import List
from nodes.core.market.filters.ema_filter_node import EMAFilter
from core.types_registry import OHLCVBar, AssetSymbol, IndicatorResult, IndicatorType, AssetClass
from unittest.mock import MagicMock, patch

@pytest.fixture
def ema_filter_node():
    node = EMAFilter(id=1, params={"period": 5, "prior_days": 1})
    node.indicators_service = MagicMock()
    return node

@pytest.fixture
def sample_ohlcv_bars() -> List[OHLCVBar]:
    """Create sample OHLCV bars with increasing closes over 10 days."""
    bars = []
    base_ts = 1672531200000  # 2023-01-01 00:00:00
    for i in range(10):
        ts = base_ts + i * 86400000
        close = 100 + i * 2  # Increasing closes
        bars.append({
            'timestamp': ts,
            'open': close - 1,
            'high': close + 1,
            'low': close - 2,
            'close': close,
            'volume': 1000 + i * 100
        })
    return bars

@pytest.mark.asyncio
async def test_ema_filter_happy_path(ema_filter_node, sample_ohlcv_bars):
    """Test filter passes when price > EMA and current EMA > previous EMA."""
    from unittest.mock import patch

    # Mock the calculate_ema function to return EMAs below price
    with patch('nodes.core.market.filters.ema_filter_node.calculate_ema') as mock_calculate_ema:
        mock_calculate_ema.side_effect = [
            {"ema": [110.0, 112.0, 114.0, 116.0, 118.0, 120.0, 122.0, 124.0, 126.0, 115.0]},  # Current EMA (115 < 118 price)
            {"ema": [110.0]}  # Previous EMA (lower than current)
        ]

        inputs = {
            "ohlcv_bundle": {AssetSymbol("TEST", AssetClass.STOCKS): sample_ohlcv_bars}
        }
        result = await ema_filter_node.execute(inputs)

        assert "filtered_ohlcv_bundle" in result
        assert AssetSymbol("TEST", AssetClass.STOCKS) in result["filtered_ohlcv_bundle"]


@pytest.mark.asyncio
async def test_ema_filter_does_not_pass(ema_filter_node, sample_ohlcv_bars):
    """Test filter does not pass when current EMA <= previous EMA."""
    from unittest.mock import patch

    # Mock the calculate_ema function to return decreasing EMAs (current < previous)
    with patch('nodes.core.market.filters.ema_filter_node.calculate_ema') as mock_calculate_ema:
        # Return decreasing EMAs for current and previous calculations
        mock_calculate_ema.side_effect = [
            {"ema": [110.0, 112.0, 114.0, 116.0, 118.0, 120.0, 122.0, 124.0, 126.0, 125.0]},  # Current EMAs (increasing but last is lower)
            {"ema": [130.0]}  # Previous EMA (higher than current)
        ]

        inputs = {
            "ohlcv_bundle": {AssetSymbol("TEST", AssetClass.STOCKS): sample_ohlcv_bars}
        }
        result = await ema_filter_node.execute(inputs)

        assert "filtered_ohlcv_bundle" in result
        assert AssetSymbol("TEST", AssetClass.STOCKS) not in result["filtered_ohlcv_bundle"]


@pytest.mark.asyncio
async def test_ema_filter_insufficient_data(ema_filter_node):
    """Test handling of insufficient data."""
    short_data = [
        {'timestamp': 1672531200000, 'open': 100, 'high': 101, 'low': 99, 'close': 100, 'volume': 1000},
        {'timestamp': 1672617600000, 'open': 100, 'high': 101, 'low': 99, 'close': 101, 'volume': 1100},
    ]

    inputs = {
        "ohlcv_bundle": {AssetSymbol("TEST", AssetClass.STOCKS): short_data}
    }
    result = await ema_filter_node.execute(inputs)

    assert "filtered_ohlcv_bundle" in result
    assert result["filtered_ohlcv_bundle"] == {}  # Should not pass due to insufficient data


@pytest.mark.asyncio
async def test_ema_filter_nan_values(ema_filter_node, sample_ohlcv_bars):
    """Test handling of NaN in EMA calculations."""
    # Mock the calculate_ema function to return NaN values
    with patch('nodes.core.market.filters.ema_filter_node.calculate_ema') as mock_calculate_ema:
        mock_calculate_ema.return_value = {"ema": [np.nan]}

        inputs = {
            "ohlcv_bundle": {AssetSymbol("TEST", AssetClass.STOCKS): sample_ohlcv_bars}
        }
        result = await ema_filter_node.execute(inputs)

        assert AssetSymbol("TEST", AssetClass.STOCKS) not in result["filtered_ohlcv_bundle"]  # Should not pass due to NaN


@pytest.mark.asyncio
async def test_ema_filter_multiple_symbols(ema_filter_node, sample_ohlcv_bars):
    """Test filtering with multiple symbols."""
    from unittest.mock import patch

    # Mock the calculate_ema function to return EMAs below price for both symbols
    with patch('nodes.core.market.filters.ema_filter_node.calculate_ema') as mock_calculate_ema:
        mock_calculate_ema.side_effect = [
            {"ema": [110.0, 112.0, 114.0, 116.0, 118.0, 120.0, 122.0, 124.0, 126.0, 115.0]},  # Current EMA for TEST1 (115 < 118 price)
            {"ema": [110.0]},  # Previous EMA for TEST1
            {"ema": [110.0, 112.0, 114.0, 116.0, 118.0, 120.0, 122.0, 124.0, 126.0, 115.0]},  # Current EMA for TEST2 (115 < 118 price)
            {"ema": [110.0]}   # Previous EMA for TEST2
        ]

        inputs = {
            "ohlcv_bundle": {
                AssetSymbol("TEST1", AssetClass.STOCKS): sample_ohlcv_bars,
                AssetSymbol("TEST2", AssetClass.STOCKS): sample_ohlcv_bars,
            }
        }
        result = await ema_filter_node.execute(inputs)

        assert "filtered_ohlcv_bundle" in result
        assert len(result["filtered_ohlcv_bundle"]) == 2  # Both should pass


@pytest.mark.asyncio
async def test_ema_filter_equal_emas(ema_filter_node, sample_ohlcv_bars):
    """Test filter does not pass when current EMA == previous EMA (no upward slope)."""
    from unittest.mock import patch

    # Mock the calculate_ema function to return equal EMAs (no slope)
    with patch('nodes.core.market.filters.ema_filter_node.calculate_ema') as mock_calculate_ema:
        mock_calculate_ema.side_effect = [
            {"ema": [110.0, 112.0, 114.0, 116.0, 118.0, 120.0, 122.0, 124.0, 126.0, 120.0]},  # Current EMA
            {"ema": [120.0]}  # Previous EMA (same as current)
        ]

        inputs = {
            "ohlcv_bundle": {AssetSymbol("TEST", AssetClass.STOCKS): sample_ohlcv_bars}
        }
        result = await ema_filter_node.execute(inputs)

        assert "filtered_ohlcv_bundle" in result
        assert AssetSymbol("TEST", AssetClass.STOCKS) not in result["filtered_ohlcv_bundle"]


@pytest.mark.asyncio
async def test_ema_filter_zero_prior_days(ema_filter_node, sample_ohlcv_bars):
    """Test handling of prior_days = 0."""
    ema_filter_node.prior_days = 0
    # Mock EMA calculations
    ema_filter_node.indicators_service.calculate_ema.side_effect = lambda df, p, price='Close': df[price].ewm(span=p).mean()

    inputs = {
        "ohlcv_bundle": {AssetSymbol("TEST", AssetClass.STOCKS): sample_ohlcv_bars}
    }
    result = await ema_filter_node.execute(inputs)

    assert AssetSymbol("TEST", AssetClass.STOCKS) in result["filtered_ohlcv_bundle"]  # Should pass with no slope check


@pytest.mark.asyncio
async def test_ema_filter_price_below_ema_fails(ema_filter_node):
    """Test that filter fails when price is below EMA."""
    from unittest.mock import patch

    # Create data where price is below EMA (decreasing prices)
    bars = []
    base_ts = 1672531200000
    for i in range(10):
        close_price = 120 - (i * 2)  # Decreasing: 120, 118, 116, ...
        bar = {
            'timestamp': base_ts + (i * 86400000),
            'open': close_price + 1,
            'high': close_price + 2,
            'low': close_price - 1,
            'close': close_price,
            'volume': 1000
        }
        bars.append(bar)

    # Mock the calculate_ema function
    with patch('nodes.core.market.filters.ema_filter_node.calculate_ema') as mock_calculate_ema:
        mock_calculate_ema.return_value = {"ema": [106.0]}  # EMA = 106, but price = 102

        inputs = {
            "ohlcv_bundle": {AssetSymbol("TEST", AssetClass.STOCKS): bars}
        }
        result = await ema_filter_node.execute(inputs)

        # Should fail because price (102) < EMA (106)
        assert AssetSymbol("TEST", AssetClass.STOCKS) not in result["filtered_ohlcv_bundle"]


@pytest.mark.asyncio
async def test_ema_filter_large_prior_days(ema_filter_node, sample_ohlcv_bars):
    """Test prior_days larger than available data."""
    ema_filter_node.prior_days = 20  # More than 10 bars

    inputs = {
        "ohlcv_bundle": {AssetSymbol("TEST", AssetClass.STOCKS): sample_ohlcv_bars}
    }
    result = await ema_filter_node.execute(inputs)

    assert "filtered_ohlcv_bundle" in result
    assert result["filtered_ohlcv_bundle"] == {}  # Should not pass due to insufficient previous data


@pytest.mark.asyncio
async def test_ema_filter_data_with_gaps(ema_filter_node):
    """Test handling of data with timestamp gaps."""
    # Create data with gaps that might affect date-based filtering
    bars = []
    base_ts = 1672531200000  # 2023-01-01
    for i in range(5):
        ts = base_ts + i * 86400000  # Daily bars
        close = 100 + i * 2
        bars.append({
            'timestamp': ts,
            'open': close - 1,
            'high': close + 1,
            'low': close - 2,
            'close': close,
            'volume': 1000
        })

    # Add a gap of several days, then continue
    gap_start = base_ts + 10 * 86400000  # 10 day gap
    for i in range(5):
        ts = gap_start + i * 86400000
        close = 120 + i * 2
        bars.append({
            'timestamp': ts,
            'open': close - 1,
            'high': close + 1,
            'low': close - 2,
            'close': close,
            'volume': 1000
        })

    ema_filter_node.prior_days = 1  # Should use data before the gap

    inputs = {
        "ohlcv_bundle": {AssetSymbol("TEST", AssetClass.STOCKS): bars}
    }
    result = await ema_filter_node.execute(inputs)

    # Should work despite the gap in data
    assert "filtered_ohlcv_bundle" in result


@pytest.mark.asyncio
async def test_ema_filter_unsorted_data(ema_filter_node, sample_ohlcv_bars):
    """Test handling of unsorted timestamp data."""
    # Reverse the order to simulate unsorted data
    unsorted_bars = list(reversed(sample_ohlcv_bars))

    inputs = {
        "ohlcv_bundle": {AssetSymbol("TEST", AssetClass.STOCKS): unsorted_bars}
    }
    result = await ema_filter_node.execute(inputs)

    # Should handle unsorted data gracefully
    assert "filtered_ohlcv_bundle" in result


@pytest.mark.asyncio
async def test_ema_filter_single_bar(ema_filter_node):
    """Test handling of single bar data."""
    single_bar = [{
        'timestamp': 1672531200000,
        'open': 100,
        'high': 101,
        'low': 99,
        'close': 100,
        'volume': 1000
    }]

    inputs = {
        "ohlcv_bundle": {AssetSymbol("TEST", AssetClass.STOCKS): single_bar}
    }
    result = await ema_filter_node.execute(inputs)

    assert "filtered_ohlcv_bundle" in result
    assert result["filtered_ohlcv_bundle"] == {}  # Should not pass due to insufficient data


@pytest.mark.asyncio
async def test_ema_filter_nan_in_data(ema_filter_node, sample_ohlcv_bars):
    """Test handling of NaN values in input data."""
    # Modify some data to include NaN
    test_bars = sample_ohlcv_bars.copy()
    test_bars[5]['close'] = np.nan

    inputs = {
        "ohlcv_bundle": {AssetSymbol("TEST", AssetClass.STOCKS): test_bars}
    }
    result = await ema_filter_node.execute(inputs)

    # Should handle NaN gracefully
    assert "filtered_ohlcv_bundle" in result


@pytest.mark.asyncio
async def test_ema_filter_empty_bundle(ema_filter_node):
    """Test handling of empty OHLCV bundle."""
    inputs = {"ohlcv_bundle": {}}
    result = await ema_filter_node.execute(inputs)

    assert "filtered_ohlcv_bundle" in result
    assert result["filtered_ohlcv_bundle"] == {}


@pytest.mark.asyncio
async def test_ema_filter_negative_params(ema_filter_node, sample_ohlcv_bars):
    """Test handling of negative parameters."""
    ema_filter_node.period = -5
    ema_filter_node.prior_days = -1

    inputs = {
        "ohlcv_bundle": {AssetSymbol("TEST", AssetClass.STOCKS): sample_ohlcv_bars}
    }
    result = await ema_filter_node.execute(inputs)

    # Should fail due to negative parameters
    assert "filtered_ohlcv_bundle" in result
    assert result["filtered_ohlcv_bundle"] == {}


@pytest.mark.asyncio
async def test_ema_filter_period_equals_data_length(ema_filter_node, sample_ohlcv_bars):
    """Test when period equals available data length."""
    ema_filter_node.period = len(sample_ohlcv_bars)
    ema_filter_node.prior_days = 1

    inputs = {
        "ohlcv_bundle": {AssetSymbol("TEST", AssetClass.STOCKS): sample_ohlcv_bars}
    }
    result = await ema_filter_node.execute(inputs)

    # Should work when period equals data length
    assert "filtered_ohlcv_bundle" in result
