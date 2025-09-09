import pytest
from typing import Dict, Any, List
from unittest.mock import AsyncMock, patch
from nodes.base.base_node import BaseNode
from nodes.base.streaming_node import StreamingNode
from nodes.base.universe_node import UniverseNode
from core.types_registry import AssetSymbol, AssetClass

class ConcreteBaseNode(BaseNode):
    inputs: Dict[str, type] = {"input": str}
    outputs: Dict[str, type] = {"output": str}

    async def execute(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        return {"output": inputs["input"]}

class ConcreteStreamingNode(StreamingNode):
    async def start(self, inputs: Dict[str, Any]) -> Any:
        yield {"output": "stream"}

    def stop(self):
        pass

class ConcreteUniverseNode(UniverseNode):
    async def _fetch_symbols(self) -> List[AssetSymbol]:
        return [AssetSymbol("TEST", AssetClass.CRYPTO, "USDT")]

@pytest.fixture
def base_node():
    return ConcreteBaseNode("test_id", {"param": "value"})

# Tests for BaseNode

def test_base_node_init(base_node):
    assert base_node.id == "test_id"
    assert base_node.params == {"param": "value"}

def test_collect_multi_input_empty(base_node):
    base_node.inputs["key"] = List[Any]
    inputs = {}
    assert base_node.collect_multi_input("key", inputs) == []

def test_collect_multi_input_single(base_node):
    base_node.inputs["key"] = List[Any]
    inputs = {"key": "value"}
    assert base_node.collect_multi_input("key", inputs) == ["value"]

def test_collect_multi_input_multi(base_node):
    base_node.inputs["key"] = List[Any]
    inputs = {"key_0": "a", "key_1": "b", "key_2": "c"}
    assert base_node.collect_multi_input("key", inputs) == ["a", "b", "c"]

def test_collect_multi_input_lists(base_node):
    base_node.inputs["key"] = List[Any]
    inputs = {"key_0": ["a", "b"], "key_1": "c"}
    assert base_node.collect_multi_input("key", inputs) == ["a", "b", "c"]

def test_collect_multi_input_dedup(base_node):
    base_node.inputs["key"] = List[Any]
    inputs = {"key_0": "a", "key_1": "a", "key_2": "b"}
    assert base_node.collect_multi_input("key", inputs) == ["a", "b"]

def test_collect_multi_input_none_skipped(base_node):
    base_node.inputs["key"] = List[Any]
    inputs = {"key_0": "a", "key_1": None, "key_2": "b"}
    assert base_node.collect_multi_input("key", inputs) == ["a", "b"]

def test_validate_inputs_valid(base_node):
    inputs = {"input": "test"}
    assert base_node.validate_inputs(inputs) is True

def test_validate_inputs_missing(base_node):
    inputs = {}
    assert base_node.validate_inputs(inputs) is False

def test_validate_inputs_invalid_type(base_node):
    inputs = {"input": 123}
    with pytest.raises(TypeError):
        base_node.validate_inputs(inputs)

def test_validate_inputs_list_type(base_node):
    base_node.inputs = {"list_input": List[str]}
    inputs = {"list_input_0": ["a", "b"], "list_input_1": "c"}
    assert base_node.validate_inputs(inputs) is True

def test_validate_inputs_invalid_list_element(base_node):
    base_node.inputs = {"list_input": List[int]}
    inputs = {"list_input_0": [1, "two"]}
    with pytest.raises(TypeError):
        base_node.validate_inputs(inputs)

def test_validate_inputs_asset_class(base_node):
    base_node.inputs = {"asset": AssetSymbol}
    base_node.required_asset_class = AssetClass.CRYPTO
    valid_asset = AssetSymbol("BTC", AssetClass.CRYPTO, "USDT")
    invalid_asset = AssetSymbol("AAPL", AssetClass.STOCKS)
    assert base_node.validate_inputs({"asset": valid_asset}) is True
    with pytest.raises(ValueError):
        base_node.validate_inputs({"asset": invalid_asset})

def test_validate_inputs_multi_asset_class(base_node):
    base_node.inputs = {"assets": List[AssetSymbol]}
    base_node.required_asset_class = AssetClass.CRYPTO
    valid_assets = [AssetSymbol("BTC", AssetClass.CRYPTO, "USDT")]
    invalid_assets = [AssetSymbol("AAPL", AssetClass.STOCKS)]
    assert base_node.validate_inputs({"assets_0": valid_assets}) is True
    with pytest.raises(ValueError):
        base_node.validate_inputs({"assets_0": invalid_assets})

def test_validate_inputs_single_list(base_node):
    base_node.inputs = {"list_input": List[str]}
    inputs = {"list_input": ["a", "b"]}
    assert base_node.validate_inputs(inputs) is True

@pytest.mark.asyncio
async def test_base_node_execute(base_node):
    inputs = {"input": "test"}
    result = await base_node.execute(inputs)
    assert result == {"output": "test"}

@pytest.mark.asyncio
async def test_abstract_execute():
    abstract = BaseNode("id")
    with pytest.raises(NotImplementedError):
        await abstract.execute({})

# Tests for StreamingNode

@pytest.fixture
def streaming_node():
    return ConcreteStreamingNode("stream_id")

@pytest.mark.asyncio
async def test_streaming_node_execute(streaming_node):
    with pytest.raises(NotImplementedError):
        await streaming_node.execute({})

@pytest.mark.asyncio
async def test_streaming_node_start(streaming_node):
    async for output in streaming_node.start({}):
        assert output == {"output": "stream"}
        break

def test_streaming_node_stop(streaming_node):
    streaming_node.stop()  # Just check it doesn't raise

# Tests for UniverseNode

@pytest.fixture
def universe_node():
    return ConcreteUniverseNode("uni_id")

@pytest.mark.asyncio
@patch.object(ConcreteUniverseNode, "_fetch_symbols", new_callable=AsyncMock)
async def test_universe_node_execute_no_filter(mock_fetch, universe_node):
    mock_fetch.return_value = [AssetSymbol("TEST", AssetClass.CRYPTO, "USDT")]
    result = await universe_node.execute({})
    assert result == {"symbols": [AssetSymbol("TEST", AssetClass.CRYPTO, "USDT")]}

@pytest.mark.asyncio
@patch.object(ConcreteUniverseNode, "_fetch_symbols", new_callable=AsyncMock)
async def test_universe_node_execute_with_filter(mock_fetch, universe_node):
    mock_fetch.return_value = [AssetSymbol("TEST", AssetClass.CRYPTO, "USDT"), AssetSymbol("OTHER", AssetClass.CRYPTO, "USDT")]
    inputs = {"filter_symbols_0": [AssetSymbol("TEST", AssetClass.CRYPTO, "USDT")]}
    result = await universe_node.execute(inputs)
    assert result == {"symbols": [AssetSymbol("TEST", AssetClass.CRYPTO, "USDT")]}

@pytest.mark.asyncio
@patch.object(ConcreteUniverseNode, "_fetch_symbols", new_callable=AsyncMock)
async def test_universe_node_execute_empty_filter(mock_fetch, universe_node):
    mock_fetch.return_value = []
    inputs = {"filter_symbols": []}
    result = await universe_node.execute(inputs)
    assert result == {"symbols": []}

def test_universe_node_abstract_fetch(universe_node):
    with pytest.raises(TypeError, match="abstract"):
        class TestUniverse(UniverseNode):
            pass
        TestUniverse("id")
