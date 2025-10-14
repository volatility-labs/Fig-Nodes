import pytest
from typing import Dict, Any, List, Type, AsyncGenerator
from unittest.mock import patch, AsyncMock
from nodes.base.base_node import BaseNode
from nodes.base.streaming_node import StreamingNode
from core.types_registry import AssetSymbol, AssetClass, NodeExecutionError

class ConcreteBaseNode(BaseNode):
    inputs: Dict[str, Type] = {"input": str}
    outputs: Dict[str, Type] = {"output": str}

    async def _execute_impl(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        return {"output": inputs["input"]}

class ConcreteStreamingNode(StreamingNode):
    async def _start_impl(self, inputs: Dict[str, Any]) -> AsyncGenerator[Dict[str, Any], None]:
        yield {"output": "stream"}

    def stop(self):
        pass

    def interrupt(self):
        pass

@pytest.fixture
def base_node():
    return ConcreteBaseNode(id=1, params={"param": "value"})

# Tests for BaseNode

def test_base_node_init(base_node):
    assert base_node.id == 1
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
    valid_asset = AssetSymbol("BTC", AssetClass.CRYPTO, quote_currency="USDT")
    invalid_asset = AssetSymbol("AAPL", AssetClass.STOCKS)
    assert base_node.validate_inputs({"asset": valid_asset}) is True
    with pytest.raises(ValueError):
        base_node.validate_inputs({"asset": invalid_asset})

def test_validate_inputs_multi_asset_class(base_node):
    base_node.inputs = {"assets": List[AssetSymbol]}
    base_node.required_asset_class = AssetClass.CRYPTO
    valid_assets = [AssetSymbol("BTC", AssetClass.CRYPTO, quote_currency="USDT")]
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
    abstract = BaseNode(id=1)
    with pytest.raises(NodeExecutionError):
        await abstract.execute({})

# Tests for StreamingNode

@pytest.fixture
def streaming_node():
    return ConcreteStreamingNode(id=1)

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
