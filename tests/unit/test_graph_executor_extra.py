import asyncio
from typing import Any, AsyncGenerator, Dict, List, Optional

import pytest

from core.graph_executor import GraphExecutor
from nodes.base.base_node import BaseNode
from nodes.base.streaming_node import StreamingNode

class PassNode(BaseNode):
    def __init__(self, id: int, params: Dict[str, Any] = None):
        super().__init__(id=id, params=params)
    inputs = {"input": str}
    outputs = {"output": str}

    async def _execute_impl(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        return {"output": f"{inputs.get('input', '')}"}


class RaiseNode(BaseNode):
    def __init__(self, id: int, params: Dict[str, Any] = None):
        super().__init__(id=id, params=params)
    inputs = {}
    outputs = {"x": int}

    async def _execute_impl(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        raise RuntimeError("compute error")


class StreamSrc(StreamingNode):
    def __init__(self, id: int, params: Dict[str, Any] = None):
        super().__init__(id=id, params=params)
        # Initialize a gate used to control emission of the second tick
        self._gate = asyncio.Event()
    inputs = {}
    outputs = {"tick": str}
    is_streaming = True

    async def _start_impl(self, inputs: Dict[str, Any]) -> AsyncGenerator[Dict[str, Any], None]:
        # emit two ticks gated
        yield {"tick": "t1"}
        await self._gate.wait()
        yield {"tick": "t2"}

    def stop(self):
        self._gate.set()


class LLMLikeNode(BaseNode):
    def __init__(self, id: int, params: Dict[str, Any] = None):
        super().__init__(id=id, params=params)
    inputs = {"messages": list}
    outputs = {"assistant_message": dict}

    async def _execute_impl(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        msgs = inputs.get("messages") or []
        # Simulate dropping invalid messages and returning empty when none
        valid = [m for m in msgs if isinstance(m, dict) and m.get("role") in {"user", "assistant", "system", "tool"}]
        if not valid:
            return {"assistant_message": {}}
        return {"assistant_message": {"role": "assistant", "content": "ok"}}


@pytest.mark.asyncio
async def test_streaming_exception_propagates_from_task():
    class BadStream(StreamingNode):
        def __init__(self, id: int, params: Dict[str, Any] = None):
            super().__init__(id=id, params=params)
        inputs = {}
        outputs = {"x": int}
        is_streaming = True

        async def _start_impl(self, inputs: Dict[str, Any]) -> AsyncGenerator[Dict[str, Any], None]:
            raise RuntimeError("bad stream")
            yield  # Unreachable, but ensures async generator type

        def stop(self):
            pass

    data = {
        "nodes": [
            {"id": 1, "type": "BadStream"},
            {"id": 2, "type": "PassNode", "properties": {}, "inputs": [{"name": "input"}], "outputs": [{"name": "output"}]},
        ],
        "links": [[0, 1, 0, 2, 0]],
    }
    registry = {"BadStream": BadStream, "PassNode": PassNode}
    executor = GraphExecutor(data, registry)
    assert executor.is_streaming
    stream = executor.stream()
    await anext(stream)  # initial static
    # The executor wraps streaming exceptions in NodeExecutionError and yields an error result
    tick = await anext(stream)
    assert tick[1]["error"] == "Node 1: Streaming failed"


@pytest.mark.asyncio
async def test_stop_cancels_stream_tasks_cleanly():
    data = {
        "nodes": [
            {"id": 1, "type": "StreamSrc"},
            {"id": 2, "type": "PassNode", "properties": {}, "inputs": [{"name": "input"}], "outputs": [{"name": "output"}]},
        ],
        "links": [[0, 1, 0, 2, 0]],
    }
    registry = {"StreamSrc": StreamSrc, "PassNode": PassNode}
    executor = GraphExecutor(data, registry)
    stream = executor.stream()
    initial = await anext(stream)
    assert initial == {}
    tick1 = await anext(stream)
    assert tick1[1] == {"tick": "t1"}
    await executor.stop()
    with pytest.raises(StopAsyncIteration):
        await anext(stream)


@pytest.mark.asyncio
async def test_input_output_slot_mapping_via_metadata():
    # Producer with custom output names
    class Producer(BaseNode):
        def __init__(self, id: int, params: Dict[str, Any] = None):
            super().__init__(id=id, params=params)
        inputs = {}
        outputs = {"first": str, "second": str}

        async def _execute_impl(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
            return {"first": "A", "second": "B"}

    # Consumer with custom input names
    class Consumer(BaseNode):
        def __init__(self, id: int, params: Dict[str, Any] = None):
            super().__init__(id=id, params=params)
        inputs = {"x": str, "y": str}
        outputs = {"out": str}

        async def _execute_impl(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
            return {"out": inputs.get("y", "") + inputs.get("x", "")}

    data = {
        "nodes": [
            {"id": 1, "type": "Producer", "outputs": [{"name": "first"}, {"name": "second"}]},
            {"id": 2, "type": "Consumer", "inputs": [{"name": "x"}, {"name": "y"}], "outputs": [{"name": "out"}]},
        ],
        # Link second (slot 1) to y (slot 1) and first (slot 0) to x (slot 0)
        "links": [[0, 1, 1, 2, 1], [0, 1, 0, 2, 0]],
    }
    registry = {"Producer": Producer, "Consumer": Consumer}
    ex = GraphExecutor(data, registry)
    res = await ex.execute()
    assert res[2]["out"] == "BA"


@pytest.mark.asyncio
async def test_llm_like_edge_cases_empty_and_invalid_messages():
    data = {
        "nodes": [
            {"id": 1, "type": "LLMMockBuilder", "properties": {}, "outputs": [{"name": "messages"}]},
            {"id": 2, "type": "LLMLikeNode", "properties": {}, "inputs": [{"name": "messages"}], "outputs": [{"name": "assistant_message"}]},
        ],
        "links": [[0, 1, 0, 2, 0]],
    }

    class LLMMockBuilder(BaseNode):
        def __init__(self, id: int, params: Dict[str, Any] = None):
            super().__init__(id=id, params=params)
        inputs = {}
        outputs = {"messages": list}

        async def _execute_impl(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
            # Mixed valid/invalid, including empty content
            msgs = [
                {"role": "system", "content": ""},
                {"role": "user", "content": "hi"},
                {"role": "weird", "content": "x"},
                "not a dict",
            ]
            return {"messages": msgs}

    registry = {"LLMMockBuilder": LLMMockBuilder, "LLMLikeNode": LLMLikeNode}
    ex = GraphExecutor(data, registry)
    res = await ex.execute()
    # LLMLikeNode should return a valid assistant_message even with mixed inputs
    assert isinstance(res[2]["assistant_message"], dict)


@pytest.mark.asyncio
async def test_graph_with_cycles():
    data = {
        "nodes": [
            {"id": 1, "type": "PassNode"},
            {"id": 2, "type": "PassNode"}
        ],
        "links": [[0, 1, 0, 2, 0], [0, 2, 0, 1, 0]]  # Cycle
    }
    with pytest.raises(ValueError, match="Graph contains cycles"):
        GraphExecutor(data, {"PassNode": PassNode})


@pytest.mark.asyncio
async def test_validate_inputs_skip():
    class InvalidInputNode(BaseNode):
        def __init__(self, id: int, params: Dict[str, Any] = None):
            super().__init__(id=id, params=params)
        inputs = {"required": str}
        outputs = {}
        async def _execute_impl(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
            return {}

    data = {
        "nodes": [{"id": 1, "type": "InvalidInputNode"}],
        "links": []
    }
    ex = GraphExecutor(data, {"InvalidInputNode": InvalidInputNode})
    results = await ex.execute()
    assert 1 not in results  # Skipped due to invalid inputs


@pytest.mark.asyncio
async def test_streaming_stop_mid_stream():
    data = {
        "nodes": [
            {"id": 1, "type": "StreamSrc"},
            {"id": 2, "type": "PassNode", "inputs": [{"name": "input"}], "outputs": [{"name": "output"}]}
        ],
        "links": [[0, 1, 0, 2, 0]]
    }
    registry = {"StreamSrc": StreamSrc, "PassNode": PassNode}
    executor = GraphExecutor(data, registry)
    stream = executor.stream()
    initial = await anext(stream)  # initial
    tick1 = await anext(stream)  # first tick
    # Manually trigger the gate to allow second tick
    executor.nodes[1]._gate.set()
    # Give a tiny delay for the tick to be ready
    await asyncio.sleep(0.1)
    await executor.stop()
    # Should raise StopAsyncIteration on next anext since stopped
    with pytest.raises(StopAsyncIteration):
        await anext(stream)

# Add tests for other missing lines, e.g., error in _execute_subgraph_for_tick, etc.


