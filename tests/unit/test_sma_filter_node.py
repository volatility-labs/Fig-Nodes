import pytest
import pandas as pd
import numpy as np
from typing import List
from nodes.core.market.filters.sma_filter_node import SMAFilterNode
from core.types_registry import OHLCVBar, AssetSymbol, IndicatorResult, IndicatorType, IndicatorValue
from unittest.mock import MagicMock

@pytest.fixture
def sma_filter_node():
    node = SMAFilterNode(id=1, params={"period": 5, "prior_days": 1})
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
async def test_sma_filter_happy_path(sma_filter_node, sample_ohlcv_bars):
    """Test filter passes when current SMA &gt; previous SMA."""
    # Mock SMA calculations
    sma_filter_node.indicators_service.calculate_sma.side_effect = lambda df, p, price='Close': df[price].tail(p).mean()

    inputs = {
        "ohlcv_bundle": {AssetSymbol("TEST", "STOCKS"): sample_ohlcv_bars}
    }
    result = await sma_filter_node.execute(inputs)

    assert "filtered_ohlcv_bundle" in result
    assert AssetSymbol("TEST", "STOCKS") in result["filtered_ohlcv_bundle"]  # Should pass since closes are increasing

@pytest.mark.asyncio
async def test_sma_filter_does_not_pass(sma_filter_node, sample_ohlcv_bars):
    """Test filter does not pass when current SMA &lt;= previous SMA."""
    # Reverse the closes to decreasing
    for i, bar in enumerate(sample_ohlcv_bars):
        bar['close'] = 100 - i * 2

    # Mock SMA calculations
    sma_filter_node.indicators_service.calculate_sma.side_effect = lambda df, p, price='Close': df[price].tail(p).mean()

    inputs = {
        "ohlcv_bundle": {AssetSymbol("TEST", "STOCKS"): sample_ohlcv_bars}
    }
    result = await sma_filter_node.execute(inputs)

    assert "filtered_ohlcv_bundle" in result
    assert AssetSymbol("TEST", "STOCKS") not in result["filtered_ohlcv_bundle"]  # Should not pass

@pytest.mark.asyncio
async def test_sma_filter_insufficient_data(sma_filter_node):
    """Test handling of insufficient data."""
    bars = []  # Empty data
    inputs = {
        "ohlcv_bundle": {AssetSymbol("TEST", "STOCKS"): bars}
    }
    result = await sma_filter_node.execute(inputs)

    assert result["filtered_ohlcv_bundle"] == {}

@pytest.mark.asyncio
async def test_sma_filter_nan_values(sma_filter_node, sample_ohlcv_bars):
    """Test handling of NaN in SMA calculations."""
    sma_filter_node.indicators_service.calculate_sma.return_value = np.nan

    inputs = {
        "ohlcv_bundle": {AssetSymbol("TEST", "STOCKS"): sample_ohlcv_bars}
    }
    result = await sma_filter_node.execute(inputs)

    assert AssetSymbol("TEST", "STOCKS") not in result["filtered_ohlcv_bundle"]  # Should not pass due to NaN

@pytest.mark.asyncio
async def test_sma_filter_multiple_symbols(sma_filter_node, sample_ohlcv_bars):
    """Test filtering with multiple symbols."""
    decreasing_bars = [bar.copy() for bar in sample_ohlcv_bars]
    for bar in decreasing_bars:
        bar['close'] = bar['close'] - 20  # Make decreasing

    # Mock different SMA for each
    def mock_sma(df, p):
        if len(df) > 5 and df['Close'].iloc[-1] > 100:  # Passing condition
            return df['Close'].tail(p).mean()
        else:
            return np.nan  # Force fail

    sma_filter_node.indicators_service.calculate_sma.side_effect = mock_sma

    inputs = {
        "ohlcv_bundle": {
            AssetSymbol("PASS", "STOCKS"): sample_ohlcv_bars,
            AssetSymbol("FAIL", "STOCKS"): decreasing_bars
        }
    }
    result = await sma_filter_node.execute(inputs)

    assert AssetSymbol("PASS", "STOCKS") in result["filtered_ohlcv_bundle"]
    assert AssetSymbol("FAIL", "STOCKS") not in result["filtered_ohlcv_bundle"]

@pytest.mark.asyncio
async def test_sma_filter_equal_smas(sma_filter_node, sample_ohlcv_bars):
    """Test filter does not pass when current SMA == previous SMA."""
    # Make constant closes
    for bar in sample_ohlcv_bars:
        bar['close'] = 100.0

    # Mock SMA to return same value
    sma_filter_node.indicators_service.calculate_sma.return_value = 100.0

    inputs = {
        "ohlcv_bundle": {AssetSymbol("TEST", "STOCKS"): sample_ohlcv_bars}
    }
    result = await sma_filter_node.execute(inputs)

    assert AssetSymbol("TEST", "STOCKS") not in result["filtered_ohlcv_bundle"]

@pytest.mark.asyncio
async def test_sma_filter_zero_prior_days(sma_filter_node, sample_ohlcv_bars):
    """Test handling of prior_days = 0."""
    sma_filter_node.prior_days = 0
    # Mock SMA
    sma_filter_node.indicators_service.calculate_sma.side_effect = lambda df, p, price='Close': df[price].tail(p).mean()

    inputs = {
        "ohlcv_bundle": {AssetSymbol("TEST", "STOCKS"): sample_ohlcv_bars}
    }
    result = await sma_filter_node.execute(inputs)

    assert AssetSymbol("TEST", "STOCKS") in result["filtered_ohlcv_bundle"]  # Likely passes for increasing data

@pytest.mark.asyncio
async def test_sma_filter_large_prior_days(sma_filter_node, sample_ohlcv_bars):
    """Test prior_days larger than available data."""
    sma_filter_node.prior_days = 20  # More than 10 bars
    # Mock SMA to return valid values
    def mock_sma(df, p, price='Close'):
        return 100.0
    sma_filter_node.indicators_service.calculate_sma.side_effect = mock_sma

    inputs = {
        "ohlcv_bundle": {AssetSymbol("TEST", "STOCKS"): sample_ohlcv_bars}
    }
    result = await sma_filter_node.execute(inputs)

    assert AssetSymbol("TEST", "STOCKS") not in result["filtered_ohlcv_bundle"]

@pytest.mark.asyncio
async def test_sma_filter_data_with_gaps(sma_filter_node):
    """Test data with timestamp gaps."""
    base_ts = 1672531200000
    bars = [
        {'timestamp': base_ts, 'close': 100},
        {'timestamp': base_ts + 2 * 86400000, 'close': 102},  # Gap of 1 day
        {'timestamp': base_ts + 3 * 86400000, 'close': 104},
        {'timestamp': base_ts + 4 * 86400000, 'close': 106},
        {'timestamp': base_ts + 5 * 86400000, 'close': 108},
    ]
    for bar in bars:
        bar.update({'open': bar['close'] - 1, 'high': bar['close'] + 1, 'low': bar['close'] - 2, 'volume': 1000})

    sma_filter_node.period = 2
    sma_filter_node.prior_days = 1
    sma_filter_node.indicators_service.calculate_sma.side_effect = lambda df, p, price='Close': df[price].tail(p).mean() if len(df) >= p else np.nan

    inputs = {
        "ohlcv_bundle": {AssetSymbol("TEST", "STOCKS"): bars}
    }
    result = await sma_filter_node.execute(inputs)

    assert AssetSymbol("TEST", "STOCKS") in result["filtered_ohlcv_bundle"]  # Should pass as overall increasing

@pytest.mark.asyncio
async def test_sma_filter_unsorted_data(sma_filter_node, sample_ohlcv_bars):
    """Test unsorted input data."""
    unsorted_bars = sample_ohlcv_bars[::-1]  # Reversed

    # Mock to verify sorting happens
    sma_filter_node.indicators_service.calculate_sma.side_effect = lambda df, p: df['Close'].tail(p).mean()

    inputs = {
        "ohlcv_bundle": {AssetSymbol("TEST", "STOCKS"): unsorted_bars}
    }
    result = await sma_filter_node.execute(inputs)

    # Since code sorts by index, it should still work (now decreasing due to reverse)
    assert AssetSymbol("TEST", "STOCKS") not in result["filtered_ohlcv_bundle"]  # Decreasing, shouldn't pass

@pytest.mark.asyncio
async def test_sma_filter_single_bar(sma_filter_node):
    """Test with single bar data."""
    single_bar = [{'timestamp': 1672531200000, 'open': 100, 'high': 101, 'low': 99, 'close': 100, 'volume': 1000}]

    inputs = {
        "ohlcv_bundle": {AssetSymbol("TEST", "STOCKS"): single_bar}
    }
    result = await sma_filter_node.execute(inputs)

    assert AssetSymbol("TEST", "STOCKS") not in result["filtered_ohlcv_bundle"]

@pytest.mark.asyncio
async def test_sma_filter_nan_in_data(sma_filter_node, sample_ohlcv_bars):
    """Test data with NaN closes."""
    sample_ohlcv_bars[5]['close'] = np.nan  # Introduce NaN

    # Mock SMA to return NaN when NaN present
    def mock_sma(df, p):
        if df['Close'].isna().any():
            return np.nan
        return df['Close'].tail(p).mean()

    sma_filter_node.indicators_service.calculate_sma.side_effect = mock_sma

    inputs = {
        "ohlcv_bundle": {AssetSymbol("TEST", "STOCKS"): sample_ohlcv_bars}
    }
    result = await sma_filter_node.execute(inputs)

    assert AssetSymbol("TEST", "STOCKS") not in result["filtered_ohlcv_bundle"]

@pytest.mark.asyncio
async def test_sma_filter_empty_bundle(sma_filter_node):
    """Test empty input bundle."""
    inputs = {"ohlcv_bundle": {}}
    result = await sma_filter_node.execute(inputs)

    assert result["filtered_ohlcv_bundle"] == {}

@pytest.mark.asyncio
async def test_sma_filter_negative_params(sma_filter_node, sample_ohlcv_bars):
    """Test negative period/prior_days - should handle gracefully."""
    sma_filter_node.period = -5
    sma_filter_node.prior_days = -1

    inputs = {
        "ohlcv_bundle": {AssetSymbol("TEST", "STOCKS"): sample_ohlcv_bars}
    }
    result = await sma_filter_node.execute(inputs)

    # Should not crash, but likely produce error results
    assert "filtered_ohlcv_bundle" in result
    assert AssetSymbol("TEST", "STOCKS") not in result["filtered_ohlcv_bundle"]

@pytest.mark.asyncio
async def test_sma_filter_period_equals_data_length(sma_filter_node, sample_ohlcv_bars):
    """Test period equal to data length."""
    sma_filter_node.period = len(sample_ohlcv_bars)
    sma_filter_node.prior_days = 1

    # Mock SMA
    sma_filter_node.indicators_service.calculate_sma.side_effect = lambda df, p, price='Close': df[price].mean() if len(df) >= p else np.nan

    inputs = {
        "ohlcv_bundle": {AssetSymbol("TEST", "STOCKS"): sample_ohlcv_bars}
    }
    result = await sma_filter_node.execute(inputs)

    # Previous would have len-1 < period, so NaN, shouldn't pass
    assert AssetSymbol("TEST", "STOCKS") not in result["filtered_ohlcv_bundle"]
