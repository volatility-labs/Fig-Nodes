import pytest
from typing import Dict, List
from nodes.core.market.filters.atrx_filter_node import AtrXFilterNode
from core.types_registry import AssetSymbol, OHLCVBar, IndicatorType
import pandas as pd
from core.types_registry import IndicatorResult, IndicatorType, IndicatorValue
from unittest.mock import patch
from core.types_registry import AssetClass

@pytest.fixture
def sample_bundle() -> Dict[AssetSymbol, List[OHLCVBar]]:
    symbol = AssetSymbol("TEST", AssetClass.CRYPTO)
    bars = [{"timestamp": 0, "open": 100, "high": 105, "low": 95, "close": 102, "volume": 10000}] * 60
    return {symbol: bars}

@pytest.mark.asyncio
async def test_atrx_filter_node_outside(sample_bundle):
    params = {"filter_condition": "outside", "upper_threshold": 5.0, "lower_threshold": -3.0}
    node = AtrXFilterNode(id=1, params=params)
    result = await node.execute({"ohlcv_bundle": sample_bundle})
    assert "filtered_ohlcv_bundle" in result
    # With constant data (close=102, high=105, low=95), daily_avg=100, EMA trend=100, ATR=10
    # ATRX = (102-100)/10 = 0.2, which is inside -3 to 5, so filtered out for "outside"
    assert result["filtered_ohlcv_bundle"] == {}

# Add more tests for inside condition, thresholds, empty input, etc.

@pytest.mark.asyncio
@pytest.mark.parametrize("smoothing", ["RMA", "EMA", "SMA"])
async def test_atrx_filter_node_smoothing(sample_bundle, smoothing):
    params = {"smoothing": smoothing, "filter_condition": "outside", "upper_threshold": 5.0, "lower_threshold": -3.0}
    node = AtrXFilterNode(id=1, params=params)
    result = await node.execute({"ohlcv_bundle": sample_bundle})
    assert "filtered_ohlcv_bundle" in result
    # Note: smoothing parameter is now ignored in corrected ATRX calculation (uses SMA for ATR)
    # Same as above, expect empty since ATRX ~0.2 is inside thresholds
    assert result["filtered_ohlcv_bundle"] == {}

@pytest.fixture
def multi_symbol_bundle() -> Dict[AssetSymbol, List[OHLCVBar]]:
    bars = [{"timestamp": i, "open": 100, "high": 105, "low": 95, "close": 102, "volume": 10000} for i in range(60)]
    return {
        AssetSymbol("AAPL", AssetClass.CRYPTO): bars,
        AssetSymbol("GOOG", AssetClass.CRYPTO): bars,
        AssetSymbol("TSLA", AssetClass.CRYPTO): bars,
    }

@pytest.mark.asyncio
async def test_atrx_filter_node_outside_multi_symbols(multi_symbol_bundle):
    params = {"filter_condition": "outside", "upper_threshold": 5.0, "lower_threshold": -3.0}
    node = AtrXFilterNode(id=1, params=params)
    with patch.object(node, '_calculate_indicator') as mock_calc:
        mock_calc.side_effect = [
            IndicatorResult(
                indicator_type=IndicatorType.ATRX,
                timestamp=0,
                values=IndicatorValue(single=6.2),
                params={}
            ),  # AAPL: outside upper
            IndicatorResult(
                indicator_type=IndicatorType.ATRX,
                timestamp=0,
                values=IndicatorValue(single=1.5),
                params={}
            ),   # GOOG: inside
            IndicatorResult(
                indicator_type=IndicatorType.ATRX,
                timestamp=0,
                values=IndicatorValue(single=-4.1),
                params={}
            ),  # TSLA: outside lower
        ]
        result = await node.execute({"ohlcv_bundle": multi_symbol_bundle})
    assert "filtered_ohlcv_bundle" in result
    filtered = result["filtered_ohlcv_bundle"]
    assert set(filtered.keys()) == {AssetSymbol("AAPL", AssetClass.CRYPTO), AssetSymbol("TSLA", AssetClass.CRYPTO)}
    assert len(filtered[AssetSymbol("AAPL", AssetClass.CRYPTO)]) == 60
    assert mock_calc.call_count == 3

@pytest.mark.asyncio
async def test_atrx_filter_node_inside_multi_symbols(multi_symbol_bundle):
    params = {"filter_condition": "inside", "upper_threshold": 5.0, "lower_threshold": -3.0}
    node = AtrXFilterNode(id=1, params=params)
    with patch.object(node, '_calculate_indicator') as mock_calc:
        mock_calc.side_effect = [
            IndicatorResult(
                indicator_type=IndicatorType.ATRX,
                timestamp=0,
                values=IndicatorValue(single=6.2),
                params={}
            ),  # AAPL: outside
            IndicatorResult(
                indicator_type=IndicatorType.ATRX,
                timestamp=0,
                values=IndicatorValue(single=1.5),
                params={}
            ),   # GOOG: inside
            IndicatorResult(
                indicator_type=IndicatorType.ATRX,
                timestamp=0,
                values=IndicatorValue(single=-4.1),
                params={}
            ),  # TSLA: outside
        ]
        result = await node.execute({"ohlcv_bundle": multi_symbol_bundle})
    assert "filtered_ohlcv_bundle" in result
    filtered = result["filtered_ohlcv_bundle"]
    assert set(filtered.keys()) == {AssetSymbol("GOOG", AssetClass.CRYPTO)}
    assert len(filtered[AssetSymbol("GOOG", AssetClass.CRYPTO)]) == 60
    assert mock_calc.call_count == 3

@pytest.mark.asyncio
async def test_atrx_filter_node_edge_cases_outside(multi_symbol_bundle):
    params = {"filter_condition": "outside", "upper_threshold": 5.0, "lower_threshold": -3.0}
    node = AtrXFilterNode(id=1, params=params)
    with patch.object(node, '_calculate_indicator') as mock_calc:
        mock_calc.side_effect = [
            IndicatorResult(
                indicator_type=IndicatorType.ATRX,
                timestamp=0,
                values=IndicatorValue(single=5.0),
                params={}
            ),   # AAPL: exactly upper -> now outside (inclusive), keep
            IndicatorResult(
                indicator_type=IndicatorType.ATRX,
                timestamp=0,
                values=IndicatorValue(single=-3.0),
                params={}
            ),  # GOOG: exactly lower -> now outside, keep
            IndicatorResult(
                indicator_type=IndicatorType.ATRX,
                timestamp=0,
                values=IndicatorValue(single=5.1),
                params={}
            ),   # TSLA: above -> outside, keep
        ]
        result = await node.execute({"ohlcv_bundle": multi_symbol_bundle})
    filtered = result["filtered_ohlcv_bundle"]
    assert set(filtered.keys()) == {AssetSymbol("AAPL", AssetClass.CRYPTO), AssetSymbol("GOOG", AssetClass.CRYPTO), AssetSymbol("TSLA", AssetClass.CRYPTO)}

@pytest.mark.asyncio
async def test_atrx_filter_node_edge_cases_inside(multi_symbol_bundle):
    params = {"filter_condition": "inside", "upper_threshold": 5.0, "lower_threshold": -3.0}
    node = AtrXFilterNode(id=1, params=params)
    with patch.object(node, '_calculate_indicator') as mock_calc:
        mock_calc.side_effect = [
            IndicatorResult(
                indicator_type=IndicatorType.ATRX,
                timestamp=0,
                values=IndicatorValue(single=5.0),
                params={}
            ),   # AAPL: exactly upper -> now inside (inclusive), keep
            IndicatorResult(
                indicator_type=IndicatorType.ATRX,
                timestamp=0,
                values=IndicatorValue(single=-3.0),
                params={}
            ),  # GOOG: exactly lower -> now inside, keep
            IndicatorResult(
                indicator_type=IndicatorType.ATRX,
                timestamp=0,
                values=IndicatorValue(single=0.0),
                params={}
            ),   # TSLA: strictly inside, keep
        ]
        result = await node.execute({"ohlcv_bundle": multi_symbol_bundle})
    filtered = result["filtered_ohlcv_bundle"]
    assert set(filtered.keys()) == {AssetSymbol("AAPL", AssetClass.CRYPTO), AssetSymbol("GOOG", AssetClass.CRYPTO), AssetSymbol("TSLA", AssetClass.CRYPTO)}

@pytest.mark.asyncio
async def test_atrx_filter_node_empty_bundle():
    params = {"filter_condition": "outside", "upper_threshold": 5.0, "lower_threshold": -3.0}
    node = AtrXFilterNode(id=1, params=params)
    result = await node.execute({"ohlcv_bundle": {}})
    assert "filtered_ohlcv_bundle" in result
    assert result["filtered_ohlcv_bundle"] == {}

@pytest.mark.asyncio
async def test_atrx_filter_node_symbol_with_empty_ohlcv(sample_bundle):
    bundle = sample_bundle.copy()
    bundle[AssetSymbol("EMPTY", AssetClass.CRYPTO)] = []
    params = {"filter_condition": "outside", "upper_threshold": 5.0, "lower_threshold": -3.0}
    node = AtrXFilterNode(id=1, params=params)
    result = await node.execute({"ohlcv_bundle": bundle})
    filtered = result["filtered_ohlcv_bundle"]
    # Empty OHLCV data should be handled gracefully and not included in results
    # TEST symbol with ATRX=0.2 is inside [-3.0, 5.0], so it fails "outside" filter
    assert filtered == {}

@pytest.mark.asyncio
async def test_atrx_filter_node_calculation_error(multi_symbol_bundle):
    params = {"filter_condition": "outside", "upper_threshold": 5.0, "lower_threshold": -3.0}
    node = AtrXFilterNode(id=1, params=params)
    with patch.object(node, '_calculate_indicator') as mock_calc:
        mock_calc.side_effect = [
            IndicatorResult(
                indicator_type=IndicatorType.ATRX,
                timestamp=0,
                values=IndicatorValue(single=6.2),
                params={}
            ),  # AAPL: keep
            ValueError("Calculation error"),                          # GOOG: skip
            IndicatorResult(
                indicator_type=IndicatorType.ATRX,
                timestamp=0,
                values=IndicatorValue(single=-4.1),
                params={}
            ), # TSLA: keep
        ]
        result = await node.execute({"ohlcv_bundle": multi_symbol_bundle})
    filtered = result["filtered_ohlcv_bundle"]
    assert set(filtered.keys()) == {AssetSymbol("AAPL", AssetClass.CRYPTO), AssetSymbol("TSLA", AssetClass.CRYPTO)}

@pytest.mark.asyncio
@pytest.mark.parametrize("condition, upper, lower, expected_kept", [
    ("outside", 10.0, -10.0, ["AAPL", "TSLA"]),  # AAPL (11 >=10), TSLA (-11 <=-10), GOOG (0 inside) filtered out
    ("inside", 10.0, -10.0, ["GOOG"]),           # Only GOOG ( -10 <=0 <=10)
    # Removed: ("outside", 0.0, 0.0, ["AAPL", "TSLA"]),     # Degenerate with inclusive
    # Replacement:
    ("outside", 0.1, -0.1, ["AAPL", "TSLA"]),    # AAPL (11 >=0.1), TSLA (-11 <=-0.1), GOOG (0 inside, not extreme)
    ("outside", 1.0, -1.0, ["AAPL", "TSLA"]),    # AAPL (11>=1), TSLA (-11<=-1), GOOG (0 inside)
    ("inside", 1.0, -1.0, ["GOOG"]),             # GOOG (-1<=0<=1)
    ("outside", 12.0, -12.0, []),                # None: 11<12, -11 > -12, 0 inside
    ("outside", 11.0, -11.0, ["AAPL", "TSLA"]),  # AAPL exact >=11, TSLA exact <=-11
    ("inside", 11.0, -11.0, ["AAPL", "GOOG", "TSLA"]),  # Now includes exact with inclusive (adjusted order)
])
async def test_atrx_filter_node_varying_params(multi_symbol_bundle, condition, upper, lower, expected_kept):
    params = {"filter_condition": condition, "upper_threshold": upper, "lower_threshold": lower}
    node = AtrXFilterNode(id=1, params=params)
    with patch.object(node, '_calculate_indicator') as mock_calc:
        mock_calc.side_effect = [
            IndicatorResult(
                indicator_type=IndicatorType.ATRX,
                timestamp=0,
                values=IndicatorValue(single=11.0),
                params={}
            ),  # AAPL
            IndicatorResult(
                indicator_type=IndicatorType.ATRX,
                timestamp=0,
                values=IndicatorValue(single=0.0),
                params={}
            ),   # GOOG
            IndicatorResult(
                indicator_type=IndicatorType.ATRX,
                timestamp=0,
                values=IndicatorValue(single=-11.0),
                params={}
            ), # TSLA
        ]
        result = await node.execute({"ohlcv_bundle": multi_symbol_bundle})
    filtered = result["filtered_ohlcv_bundle"]
    assert set(k.ticker for k in filtered.keys()) == set(expected_kept)  # Use .ticker for string comparison

# New test for real calculation with varying data
@pytest.fixture
def varying_bundle():
    symbol = AssetSymbol("TEST", AssetClass.CRYPTO)
    # Data with increasing prices to generate positive ATRX
    bars = [{"timestamp": i*1000, "open": 100 + i, "high": 105 + i, "low": 95 + i, "close": 102 + i, "volume": 10000} for i in range(60)]
    return {symbol: bars}

@pytest.mark.asyncio
async def test_atrx_filter_node_real_calc_outside(varying_bundle):
    # With varying data: close increases from 102 to 161, high=close+3, low=close-5
    # daily_avg = (close+3 + close-5)/2 = close-1
    # EMA of daily_avg will be lower than current close (trending up)
    # ATR = SMA of (high-low) = SMA of 8 = 8
    # ATRX = (current_close - EMA_daily_avg) / 8
    # This should be positive and potentially large, so may pass "outside" filter
    params = {"filter_condition": "outside", "upper_threshold": 1.0, "lower_threshold": -1.0}
    node = AtrXFilterNode(id=1, params=params)
    result = await node.execute({"ohlcv_bundle": varying_bundle})
    assert "filtered_ohlcv_bundle" in result
    # With trending up data, ATRX should be positive and potentially > 1.0
    # So it should pass the "outside" filter (keep the symbol)
    assert len(result["filtered_ohlcv_bundle"]) == 1
