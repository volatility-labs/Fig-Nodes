
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
import pandas as pd
from typing import Dict, Any, List
from nodes.core.market.filters.base.base_filter_node import BaseFilterNode
from nodes.core.market.indicators.base.base_indicator_node import BaseIndicatorNode
from nodes.core.market.filters.base.base_indicator_filter_node import BaseIndicatorFilterNode
from core.types_registry import AssetSymbol, AssetClass, OHLCVBar, IndicatorResult, IndicatorType, IndicatorValue
from services.indicators_service import IndicatorsService

# Fixtures
@pytest.fixture
def sample_ohlcv_bundle():
    symbol = AssetSymbol("TEST", AssetClass.STOCKS)
    bars = [
        OHLCVBar(timestamp=1, open=100, high=110, low=90, close=105, volume=1000),
        OHLCVBar(timestamp=2, open=105, high=115, low=95, close=110, volume=1200),
    ]
    return {symbol: bars}

@pytest.fixture
def empty_ohlcv_bundle():
    return {}

@pytest.fixture
def insufficient_ohlcv_bundle():
    symbol = AssetSymbol("TEST", AssetClass.STOCKS)
    bars = [OHLCVBar(timestamp=1, open=100, high=110, low=90, close=105, volume=1000)]  # Only 1 bar
    return {symbol: bars}

# Tests for BaseFilterNode
class TestBaseFilterNode:
    class ConcreteFilterNode(BaseFilterNode):
        def _filter_condition(self, symbol: AssetSymbol, ohlcv_data: List[OHLCVBar]) -> bool:
            return len(ohlcv_data) > 1  # Simple condition: pass if more than 1 bar

    @pytest.fixture
    def filter_node(self):
        return self.ConcreteFilterNode("filter_id", {})

    @pytest.mark.asyncio
    async def test_execute_happy_path(self, filter_node, sample_ohlcv_bundle):
        inputs = {"ohlcv_bundle": sample_ohlcv_bundle}
        result = await filter_node.execute(inputs)
        assert "filtered_ohlcv_bundle" in result
        assert len(result["filtered_ohlcv_bundle"]) == 1  # Should pass

    @pytest.mark.asyncio
    async def test_execute_empty_bundle(self, filter_node, empty_ohlcv_bundle):
        inputs = {"ohlcv_bundle": empty_ohlcv_bundle}
        result = await filter_node.execute(inputs)
        assert result["filtered_ohlcv_bundle"] == {}

    @pytest.mark.asyncio
    async def test_execute_insufficient_data(self, filter_node, insufficient_ohlcv_bundle):
        inputs = {"ohlcv_bundle": insufficient_ohlcv_bundle}
        result = await filter_node.execute(inputs)
        assert result["filtered_ohlcv_bundle"] == {}  # Should not pass

    @pytest.mark.asyncio
    async def test_execute_filter_condition_error(self, filter_node, sample_ohlcv_bundle):
        def failing_condition(*args):
            raise ValueError("Filter error")
        filter_node._filter_condition = failing_condition
        inputs = {"ohlcv_bundle": sample_ohlcv_bundle}
        result = await filter_node.execute(inputs)
        assert result["filtered_ohlcv_bundle"] == {}  # Should skip on error

# Tests for BaseIndicatorNode
class TestBaseIndicatorNode:
    class ConcreteIndicatorNode(BaseIndicatorNode):
        def _map_to_indicator_value(self, ind_type: IndicatorType, raw: Dict[str, Any]) -> IndicatorValue:
            return {"single": raw.get(ind_type.name, 0.0)}

    @pytest.fixture
    def indicator_node(self):
        return self.ConcreteIndicatorNode("ind_id", {"indicators": [IndicatorType.ADX], "timeframe": "1d"})

    @pytest.mark.asyncio
    async def test_execute_happy_path(self, indicator_node):
        bars = [
            {"timestamp": i, "open": 100, "high": 110, "low": 90, "close": 105, "volume": 1000} for i in range(20)
        ]
        inputs = {"ohlcv": bars}
        with patch.object(IndicatorsService, "compute_indicators", return_value={"ADX": 25.0}):
            result = await indicator_node.execute(inputs)
            assert "results" in result
            assert len(result["results"]) == 1
            assert result["results"][0]["values"]["single"] == 25.0

    @pytest.mark.asyncio
    async def test_execute_empty_bars(self, indicator_node):
        inputs = {"ohlcv": []}
        result = await indicator_node.execute(inputs)
        assert result["results"] == []

    @pytest.mark.asyncio
    async def test_execute_insufficient_data(self, indicator_node):
        bars = [{"timestamp": 1, "open": 100, "high": 110, "low": 90, "close": 105, "volume": 1000}]  # <14 bars
        inputs = {"ohlcv": bars}
        with patch.object(IndicatorsService, "compute_indicators", return_value={}):
            result = await indicator_node.execute(inputs)
            assert result["results"] == []

    @pytest.mark.asyncio
    async def test_execute_computation_error(self, indicator_node):
        bars = [{"timestamp": i, "open": 100, "high": 110, "low": 90, "close": 105, "volume": 1000} for i in range(20)]
        inputs = {"ohlcv": bars}
        with patch.object(IndicatorsService, "compute_indicators", side_effect=ValueError("Computation error")):
            result = await indicator_node.execute(inputs)
            assert result["results"] == []

# Tests for BaseIndicatorFilterNode
class TestBaseIndicatorFilterNode:
    class ConcreteIndicatorFilterNode(BaseIndicatorFilterNode):
        def _calculate_indicator(self, ohlcv_data: List[OHLCVBar]) -> IndicatorResult:
            if not ohlcv_data:
                return {
                    "indicator_type": IndicatorType.ADX,
                    "timestamp": 0,
                    "values": {"single": 0.0},
                    "error": "No data"
                }
            df = pd.DataFrame(ohlcv_data)
            adx = 30.0 if len(df) > 1 else 0.0
            return {
                "indicator_type": IndicatorType.ADX,
                "timestamp": int(df['timestamp'].iloc[-1]),
                "values": {"single": adx}
            }

        def _should_pass_filter(self, indicator_result: IndicatorResult) -> bool:
            if "error" in indicator_result:
                return False
            return indicator_result["values"]["single"] > 25.0

    @pytest.fixture
    def ind_filter_node(self):
        return self.ConcreteIndicatorFilterNode("ind_filter_id", {})

    @pytest.mark.asyncio
    async def test_execute_happy_path(self, ind_filter_node, sample_ohlcv_bundle):
        inputs = {"ohlcv_bundle": sample_ohlcv_bundle}
        result = await ind_filter_node.execute(inputs)
        assert "filtered_ohlcv_bundle" in result
        assert len(result["filtered_ohlcv_bundle"]) == 1  # Should pass

    @pytest.mark.asyncio
    async def test_execute_empty_bundle(self, ind_filter_node, empty_ohlcv_bundle):
        inputs = {"ohlcv_bundle": empty_ohlcv_bundle}
        result = await ind_filter_node.execute(inputs)
        assert result["filtered_ohlcv_bundle"] == {}

    @pytest.mark.asyncio
    async def test_execute_insufficient_data(self, ind_filter_node, insufficient_ohlcv_bundle):
        inputs = {"ohlcv_bundle": insufficient_ohlcv_bundle}
        result = await ind_filter_node.execute(inputs)
        assert result["filtered_ohlcv_bundle"] == {}  # Should not pass

    @pytest.mark.asyncio
    async def test_execute_computation_error(self, ind_filter_node, sample_ohlcv_bundle):
        def failing_calculate(*args):
            raise ValueError("Calc error")
        ind_filter_node._calculate_indicator = failing_calculate
        inputs = {"ohlcv_bundle": sample_ohlcv_bundle}
        result = await ind_filter_node.execute(inputs)
        assert result["filtered_ohlcv_bundle"] == {}  # Skip on error
