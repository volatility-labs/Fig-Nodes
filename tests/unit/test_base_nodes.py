import pytest
from typing import Dict, Any, List, Type, AsyncGenerator, Union, Optional
from unittest.mock import Mock
from nodes.base.base_node import Base
from nodes.base.streaming_node import Streaming
from core.types_registry import NodeExecutionError, NodeValidationError

class ConcreteBaseNode(Base):
    inputs: Dict[str, Type[Any]] = {"input": str}
    outputs: Dict[str, Type[Any]] = {"output": str}

    async def _execute_impl(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        return {"output": inputs["input"]}

class ConcreteBaseNodeWithOptional(Base):
    inputs: Dict[str, Type[Any]] = {"required": str, "optional": Optional[str]}
    outputs: Dict[str, Type[Any]] = {"output": str}

    async def _execute_impl(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        return {"output": inputs.get("required", "default")}

class ConcreteBaseNodeWithList(Base):
    inputs: Dict[str, Type[Any]] = {"items": List[str]}
    outputs: Dict[str, Type[Any]] = {"output": str}

    async def _execute_impl(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        return {"output": str(len(inputs.get("items", [])))}

class ConcreteBaseNodeWithUnion(Base):
    inputs: Dict[str, Type[Any]] = {"value": Union[str, int]}
    outputs: Dict[str, Type[Any]] = {"output": str}

    async def _execute_impl(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        return {"output": str(inputs["value"])}

class ConcreteStreamingNode(Streaming):
    inputs: Dict[str, Type[Any]] = {}  # No required inputs
    
    async def _start_impl(self, inputs: Dict[str, Any]) -> AsyncGenerator[Dict[str, Any], None]:
        yield {"output": "stream"}

    async def _execute_impl(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        # Not used for Streaming, present to satisfy abstract base class
        return {}

    def stop(self):
        pass

    def interrupt(self):
        pass

@pytest.fixture
def base_node():
    return ConcreteBaseNode(id=1, params={"param": "value"})

@pytest.fixture
def base_node_with_optional():
    return ConcreteBaseNodeWithOptional(id=2, params={})

@pytest.fixture
def base_node_with_list():
    return ConcreteBaseNodeWithList(id=3, params={})

@pytest.fixture
def base_node_with_union():
    return ConcreteBaseNodeWithUnion(id=4, params={})

# Tests for BaseNode initialization

def test_base_node_init(base_node):
    assert base_node.id == 1
    assert base_node.params == {"param": "value"}
    assert base_node.inputs == {"input": str}
    assert base_node.outputs == {"output": str}
    assert base_node._progress_callback is None
    assert base_node._is_stopped is False

def test_base_node_init_with_default_params():
    class TestNode(Base):
        default_params = {"default": "value"}
        
        async def _execute_impl(self, inputs):
            return {}
    
    node = TestNode(id=1, params={"custom": "custom_value"})
    assert node.params == {"default": "value", "custom": "custom_value"}

# Tests for static utility methods

def test_normalize_to_list():
    # Test None
    assert Base._normalize_to_list(None) == []
    
    # Test list
    assert Base._normalize_to_list([1, 2, 3]) == [1, 2, 3]
    
    # Test single value
    assert Base._normalize_to_list("single") == ["single"]
    assert Base._normalize_to_list(42) == [42]

def test_dedupe_preserve_order():
    # Test empty list
    assert Base._dedupe_preserve_order([]) == []
    
    # Test with duplicates
    assert Base._dedupe_preserve_order([1, 2, 1, 3, 2]) == [1, 2, 3]
    
    # Test with non-hashable items
    result = Base._dedupe_preserve_order([{"a": 1}, {"b": 2}, {"a": 1}])
    assert len(result) == 3  # Non-hashable items are not deduplicated
    
    # Test with mixed types
    assert Base._dedupe_preserve_order([1, "a", 1, "b"]) == [1, "a", "b"]

def test_is_declared_list():
    # Test None
    assert Base._is_declared_list(None) is False
    
    # Test list types
    assert Base._is_declared_list(List[str]) is True
    # Note: get_origin(list) returns None, not list itself
    assert Base._is_declared_list(list) is False
    
    # Test non-list types
    assert Base._is_declared_list(str) is False
    assert Base._is_declared_list(int) is False

def test_type_allows_none():
    # Create a test node instance
    test_node = ConcreteBaseNode(id=999, params={})
    
    # Test Union types
    assert test_node._type_allows_none(Union[str, None]) is True
    assert test_node._type_allows_none(Union[str, int]) is False
    
    # Test Optional (which is Union[T, None])
    assert test_node._type_allows_none(Optional[str]) is True
    
    # Test simple types
    assert test_node._type_allows_none(str) is False
    assert test_node._type_allows_none(int) is False

# Tests for collect_multi_input

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

def test_collect_multi_input_non_list_type(base_node):
    # When not declared as List[...], should just normalize to list
    base_node.inputs["key"] = str
    inputs = {"key": "value"}
    assert base_node.collect_multi_input("key", inputs) == ["value"]

# Tests for validate_inputs

def test_validate_inputs_valid(base_node):
    inputs = {"input": "test"}
    # Should not raise any exception
    base_node.validate_inputs(inputs)

def test_validate_inputs_missing_required(base_node):
    inputs = {}
    with pytest.raises(NodeValidationError):
        base_node.validate_inputs(inputs)

def test_validate_inputs_invalid_type(base_node):
    inputs = {"input": 123}
    with pytest.raises(NodeValidationError):
        base_node.validate_inputs(inputs)

def test_validate_inputs_optional_field_missing(base_node_with_optional):
    inputs = {"required": "test"}
    # Should not raise - optional field can be missing
    base_node_with_optional.validate_inputs(inputs)

def test_validate_inputs_optional_field_none(base_node_with_optional):
    inputs = {"required": "test", "optional": None}
    # Should not raise - optional field can be None
    base_node_with_optional.validate_inputs(inputs)

def test_validate_inputs_list_type(base_node_with_list):
    inputs = {"items": ["a", "b", "c"]}
    base_node_with_list.validate_inputs(inputs)

def test_validate_inputs_list_with_multi_input(base_node_with_list):
    inputs = {"items_0": ["a", "b"], "items_1": "c"}
    base_node_with_list.validate_inputs(inputs)

def test_validate_inputs_invalid_list_element(base_node_with_list):
    inputs = {"items": [1, "two"]}  # Mixed types in List[str]
    with pytest.raises(NodeValidationError):
        base_node_with_list.validate_inputs(inputs)

def test_validate_inputs_union_type(base_node_with_union):
    # Test with string
    inputs = {"value": "test"}
    base_node_with_union.validate_inputs(inputs)
    
    # Test with int
    inputs = {"value": 42}
    base_node_with_union.validate_inputs(inputs)

def test_validate_inputs_union_type_invalid(base_node_with_union):
    inputs = {"value": [1, 2, 3]}  # Not str or int
    with pytest.raises(NodeValidationError):
        base_node_with_union.validate_inputs(inputs)

# Tests for _validate_outputs

def test_validate_outputs_valid(base_node):
    outputs = {"output": "test"}
    # Should not raise any exception
    base_node._validate_outputs(outputs)

def test_validate_outputs_invalid_type(base_node):
    outputs = {"output": 123}  # Should be str
    with pytest.raises(TypeError):
        base_node._validate_outputs(outputs)

def test_validate_outputs_empty_outputs(base_node):
    outputs = {}
    # Should not raise - lenient validation
    base_node._validate_outputs(outputs)

def test_validate_outputs_no_declared_outputs():
    class TestNode(Base):
        inputs = {}
        outputs = {}
        
        async def _execute_impl(self, inputs):
            return {}
    
    node = TestNode(id=1, params={})
    outputs = {"anything": "goes"}
    # Should not raise - no outputs declared
    node._validate_outputs(outputs)

# Tests for progress callbacks

def test_set_progress_callback(base_node):
    callback = Mock()
    base_node.set_progress_callback(callback)
    assert base_node._progress_callback is callback

def test_report_progress_with_callback(base_node):
    callback = Mock()
    base_node.set_progress_callback(callback)
    
    base_node.report_progress(0.5, "test message")
    callback.assert_called_once_with(1, 0.5, "test message")

def test_report_progress_without_callback(base_node):
    # Should not raise any exception
    base_node.report_progress(0.5, "test message")

def test_report_progress_default_text(base_node):
    callback = Mock()
    base_node.set_progress_callback(callback)
    
    base_node.report_progress(0.5)
    callback.assert_called_once_with(1, 0.5, "")

# Tests for force_stop

def test_force_stop_idempotent(base_node):
    # First call
    base_node.force_stop()
    assert base_node._is_stopped is True
    
    # Second call should be idempotent
    base_node.force_stop()
    assert base_node._is_stopped is True

def test_force_stop_initial_state(base_node):
    assert base_node._is_stopped is False
    base_node.force_stop()
    assert base_node._is_stopped is True

# Tests for execute method

@pytest.mark.asyncio
async def test_base_node_execute_success(base_node):
    inputs = {"input": "test"}
    result = await base_node.execute(inputs)
    assert result == {"output": "test"}

@pytest.mark.asyncio
async def test_base_node_execute_validation_error(base_node):
    inputs = {}  # Missing required input
    with pytest.raises(NodeValidationError):
        await base_node.execute(inputs)

@pytest.mark.asyncio
async def test_base_node_execute_implementation_error():
    class FailingNode(Base):
        inputs = {"input": str}
        outputs = {"output": str}
        
        async def _execute_impl(self, inputs):
            raise ValueError("Implementation error")
    
    node = FailingNode(id=1, params={})
    inputs = {"input": "test"}
    
    with pytest.raises(NodeExecutionError) as exc_info:
        await node.execute(inputs)
    
    assert isinstance(exc_info.value.original_exc, ValueError)

@pytest.mark.asyncio
async def test_base_node_execute_output_validation_error():
    class BadOutputNode(Base):
        inputs = {"input": str}
        outputs = {"output": str}
        
        async def _execute_impl(self, inputs):
            return {"output": 123}  # Wrong type
    
    node = BadOutputNode(id=1, params={})
    inputs = {"input": "test"}
    
    with pytest.raises(NodeExecutionError) as exc_info:
        await node.execute(inputs)
    
    assert isinstance(exc_info.value.original_exc, TypeError)

@pytest.mark.asyncio
async def test_abstract_execute():
    # Create a minimal concrete subclass to test the abstract behavior
    class MinimalNode(Base):
        inputs = {}
        outputs = {}
        
        async def _execute_impl(self, inputs):
            raise NotImplementedError("Test implementation error")
    
    abstract = MinimalNode(id=1, params={})
    with pytest.raises(NodeExecutionError) as exc_info:
        await abstract.execute({})
    
    assert isinstance(exc_info.value.original_exc, NotImplementedError)

# Tests for StreamingNode

@pytest.fixture
def streaming_node():
    return ConcreteStreamingNode(id=1, params={})

@pytest.mark.asyncio
async def test_streaming_node_execute(streaming_node):
    with pytest.raises(NotImplementedError):
        await streaming_node.execute({})

@pytest.mark.asyncio
async def test_streaming_node_start(streaming_node):
    # StreamingNode requires inputs to be valid, but our test node has no inputs declared
    # So we need to provide empty inputs which should be valid
    async for output in streaming_node.start({}):
        assert output == {"output": "stream"}
        break

def test_streaming_node_stop(streaming_node):
    streaming_node.stop()  # Just check it doesn't raise

def test_streaming_node_interrupt(streaming_node):
    streaming_node.interrupt()  # Just check it doesn't raise