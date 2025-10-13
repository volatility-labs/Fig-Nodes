import pytest
from typing import Dict, List
from nodes.core.market.filters.atrx_filter_node import AtrXFilterNode
from core.types_registry import AssetSymbol, OHLCVBar, IndicatorType
import pandas as pd
from core.types_registry import IndicatorResult, IndicatorType, IndicatorValue
from unittest.mock import patch

@pytest.fixture
def sample_bundle() -> Dict[AssetSymbol, List[OHLCVBar]]:
    symbol = AssetSymbol("TEST", "STOCKS")
    bars = [{"timestamp": 0, "open": 100, "high": 105, "low": 95, "close": 102, "volume": 10000}] * 60
    return {symbol: bars}

@pytest.mark.asyncio
async def test_atrx_filter_node_outside(sample_bundle):
    params = {"filter_condition": "outside", "upper_threshold": 5.0, "lower_threshold": -3.0}
    node = AtrXFilterNode("test_id", params)
    result = await node.execute({"ohlcv_bundle": sample_bundle})
    assert "filtered_ohlcv_bundle" in result

# Add more tests for inside condition, thresholds, empty input, etc.

@pytest.mark.asyncio
@pytest.mark.parametrize("smoothing", ["RMA", "EMA", "SMA"])
async def test_atrx_filter_node_smoothing(sample_bundle, smoothing):
    params = {"smoothing": smoothing, "filter_condition": "outside", "upper_threshold": 5.0, "lower_threshold": -3.0}
    node = AtrXFilterNode("test_id", params)
    result = await node.execute({"ohlcv_bundle": sample_bundle})
    assert "filtered_ohlcv_bundle" in result

@pytest.fixture
def multi_symbol_bundle() -> Dict[AssetSymbol, List[OHLCVBar]]:
    bars = [{"timestamp": i, "open": 100, "high": 105, "low": 95, "close": 102, "volume": 10000} for i in range(60)]
    return {
        AssetSymbol("AAPL", "STOCKS"): bars,
        AssetSymbol("GOOG", "STOCKS"): bars,
        AssetSymbol("TSLA", "STOCKS"): bars,
    }

@pytest.mark.asyncio
async def test_atrx_filter_node_outside_multi_symbols(multi_symbol_bundle):
    params = {"filter_condition": "outside", "upper_threshold": 5.0, "lower_threshold": -3.0}
    node = AtrXFilterNode("test_id", params)
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
    assert set(filtered.keys()) == {AssetSymbol("AAPL", "STOCKS"), AssetSymbol("TSLA", "STOCKS")}
    assert len(filtered[AssetSymbol("AAPL", "STOCKS")]) == 60
    assert mock_calc.call_count == 3

@pytest.mark.asyncio
async def test_atrx_filter_node_inside_multi_symbols(multi_symbol_bundle):
    params = {"filter_condition": "inside", "upper_threshold": 5.0, "lower_threshold": -3.0}
    node = AtrXFilterNode("test_id", params)
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
    assert set(filtered.keys()) == {AssetSymbol("GOOG", "STOCKS")}
    assert len(filtered[AssetSymbol("GOOG", "STOCKS")]) == 60
    assert mock_calc.call_count == 3

@pytest.mark.asyncio
async def test_atrx_filter_node_edge_cases_outside(multi_symbol_bundle):
    params = {"filter_condition": "outside", "upper_threshold": 5.0, "lower_threshold": -3.0}
    node = AtrXFilterNode("test_id", params)
    with patch.object(node, '_calculate_indicator') as mock_calc:
        mock_calc.side_effect = [
            IndicatorResult(
                indicator_type=IndicatorType.ATRX,
                timestamp=0,
                values=IndicatorValue(single=5.0),
                params={}
            ),   # AAPL: exactly upper -> inside, filter out
            IndicatorResult(
                indicator_type=IndicatorType.ATRX,
                timestamp=0,
                values=IndicatorValue(single=-3.0),
                params={}
            ),  # GOOG: exactly lower -> inside, filter out
            IndicatorResult(
                indicator_type=IndicatorType.ATRX,
                timestamp=0,
                values=IndicatorValue(single=5.1),
                params={}
            ),   # TSLA: just above -> outside, keep
        ]
        result = await node.execute({"ohlcv_bundle": multi_symbol_bundle})
    filtered = result["filtered_ohlcv_bundle"]
    assert set(filtered.keys()) == {AssetSymbol("TSLA", "STOCKS")}

@pytest.mark.asyncio
async def test_atrx_filter_node_edge_cases_inside(multi_symbol_bundle):
    params = {"filter_condition": "inside", "upper_threshold": 5.0, "lower_threshold": -3.0}
    node = AtrXFilterNode("test_id", params)
    with patch.object(node, '_calculate_indicator') as mock_calc:
        mock_calc.side_effect = [
            IndicatorResult(
                indicator_type=IndicatorType.ATRX,
                timestamp=0,
                values=IndicatorValue(single=5.0),
                params={}
            ),   # AAPL: exactly upper -> not < upper, filter out
            IndicatorResult(
                indicator_type=IndicatorType.ATRX,
                timestamp=0,
                values=IndicatorValue(single=-3.0),
                params={}
            ),  # GOOG: exactly lower -> not > lower, filter out
            IndicatorResult(
                indicator_type=IndicatorType.ATRX,
                timestamp=0,
                values=IndicatorValue(single=0.0),
                params={}
            ),   # TSLA: strictly inside, keep
        ]
        result = await node.execute({"ohlcv_bundle": multi_symbol_bundle})
    filtered = result["filtered_ohlcv_bundle"]
    assert set(filtered.keys()) == {AssetSymbol("TSLA", "STOCKS")}

@pytest.mark.asyncio
async def test_atrx_filter_node_empty_bundle():
    params = {"filter_condition": "outside", "upper_threshold": 5.0, "lower_threshold": -3.0}
    node = AtrXFilterNode("test_id", params)
    result = await node.execute({"ohlcv_bundle": {}})
    assert "filtered_ohlcv_bundle" in result
    assert result["filtered_ohlcv_bundle"] == {}

@pytest.mark.asyncio
async def test_atrx_filter_node_symbol_with_empty_ohlcv(sample_bundle):
    bundle = sample_bundle.copy()
    bundle[AssetSymbol("EMPTY", "STOCKS")] = []
    params = {"filter_condition": "outside", "upper_threshold": 5.0, "lower_threshold": -3.0}
    node = AtrXFilterNode("test_id", params)
    with patch.object(node, '_calculate_indicator') as mock_calc:
        mock_calc.side_effect = [
            IndicatorResult(
                indicator_type=IndicatorType.ATRX,
                timestamp=0,
                values=IndicatorValue(single=6.2),
                params={}
            ),
            ValueError("Empty OHLCV data")
        ]
        result = await node.execute({"ohlcv_bundle": bundle})
    filtered = result["filtered_ohlcv_bundle"]
    assert set(filtered.keys()) == {AssetSymbol("TEST", "STOCKS")}
    assert mock_calc.call_count == 1  # Skips empty

@pytest.mark.asyncio
async def test_atrx_filter_node_calculation_error(multi_symbol_bundle):
    params = {"filter_condition": "outside", "upper_threshold": 5.0, "lower_threshold": -3.0}
    node = AtrXFilterNode("test_id", params)
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
    assert set(filtered.keys()) == {AssetSymbol("AAPL", "STOCKS"), AssetSymbol("TSLA", "STOCKS")}

@pytest.mark.asyncio
@pytest.mark.parametrize("condition, upper, lower, expected_kept", [
    ("outside", 10.0, -10.0, ["AAPL", "TSLA"]),  # AAPL (11 >10), TSLA (-11 <-10), GOOG (0 inside) filtered out
    ("inside", 10.0, -10.0, ["GOOG"]),           # Only GOOG ( -10 <0 <10)
    ("outside", 0.0, 0.0, ["AAPL", "TSLA"]),  # AAPL (11 >0), TSLA (-11 <0), GOOG (0 neither >0 nor <0) filtered out
    ("outside", 1.0, -1.0, ["AAPL", "TSLA"]),    # AAPL (11>1), TSLA (-11<-1), GOOG (0 inside)
    ("inside", 1.0, -1.0, ["GOOG"]),             # GOOG (-1<0<1)
    ("outside", 12.0, -12.0, []),                # None: 11<12, 0> -12, -11 > -12? Wait, adjust mocked if needed.
])
async def test_atrx_filter_node_varying_params(multi_symbol_bundle, condition, upper, lower, expected_kept):
    params = {"filter_condition": condition, "upper_threshold": upper, "lower_threshold": lower}
    node = AtrXFilterNode("test_id", params)
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
