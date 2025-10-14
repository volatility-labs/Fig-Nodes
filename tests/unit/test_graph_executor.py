import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import asyncio
import networkx as nx
from typing import Dict, Any, AsyncGenerator
from core.graph_executor import GraphExecutor
from nodes.base.base_node import BaseNode
from nodes.base.streaming_node import StreamingNode
from nodes.core.flow.for_each_node import ForEachNode
from core.node_registry import NODE_REGISTRY  # Assuming it's empty or mock

# Mock Node Classes
class MockBaseNode(BaseNode):
    def __init__(self, id: int, params: Dict[str, Any] = None):
        super().__init__(id=id, params=params)
    inputs = {"input": str}
    outputs = {"output": str}

    async def _execute_impl(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        return {"output": f"processed_{inputs.get('input', '')}"}

class MockStreamingNode(StreamingNode):
    def __init__(self, id: int, params: Dict[str, Any] = None):
        super().__init__(id=id, params=params)
    inputs = {}
    outputs = {"stream": str}
    is_streaming = True

    async def _start_impl(self, inputs: Dict[str, Any]) -> AsyncGenerator[Dict[str, Any], None]:
        yield {"stream": "tick1"}
        yield {"stream": "tick2"}

    def stop(self):
        pass

@pytest.fixture
def mock_registry():
    return {
        "MockBaseNode": MockBaseNode,
        "MockStreamingNode": MockStreamingNode,
        "ForEachNode": ForEachNode
    }

@pytest.fixture
def simple_graph_data():
    return {
        "nodes": [
            {"id": 1, "type": "MockBaseNode", "properties": {}},
            {"id": 2, "type": "MockBaseNode", "properties": {}}
        ],
        "links": [[0, 1, 0, 2, 0]]  # Link output 0 of 1 to input 0 of 2
    }

@pytest.mark.asyncio
async def test_build_graph(simple_graph_data, mock_registry):
    executor = GraphExecutor(simple_graph_data, mock_registry)
    assert len(executor.nodes) == 2
    assert executor.dag.has_edge(1, 2)
    assert not executor.is_streaming

@pytest.mark.asyncio
async def test_execute_simple_graph(simple_graph_data, mock_registry):
    simple_graph_data["nodes"][0]["properties"] = {"input": "start"}  # Simulate input
    executor = GraphExecutor(simple_graph_data, mock_registry)
    results = await executor.execute()
    assert results[2]["output"] == "processed_processed_start"  # Double processed

def test_build_graph_cycle():
    cycle_data = {
        "nodes": [{"id": 1, "type": "MockBaseNode"}, {"id": 2, "type": "MockBaseNode"}],
        "links": [[0, 1, 0, 2, 0], [0, 2, 0, 1, 0]]
    }
    with pytest.raises(ValueError, match="Graph contains cycles"):
        GraphExecutor(cycle_data, {"MockBaseNode": MockBaseNode})

@pytest.mark.asyncio
async def test_execute_isolated_node(mock_registry):
    data = {"nodes": [{"id": 1, "type": "MockBaseNode"}], "links": []}
    executor = GraphExecutor(data, mock_registry)
    results = await executor.execute()
    assert 1 not in results  # Skipped isolated

@pytest.mark.asyncio
async def test_execute_foreach(mock_registry):
    data = {
        "nodes": [
            {"id": 1, "type": "ForEachNode"},
            {"id": 2, "type": "MockBaseNode"}  # Subgraph node
        ],
        "links": [[0, 1, 0, 2, 0]]  # ForEach to Mock
    }
    executor = GraphExecutor(data, mock_registry)
    results = await executor.execute()
    assert results[1] == {"results": []}  # Empty list

@pytest.mark.asyncio
async def test_streaming_graph(mock_registry):
    data = {
        "nodes": [
            {"id": 1, "type": "MockStreamingNode"},
            {"id": 2, "type": "MockBaseNode"}
        ],
        "links": [[0, 1, 0, 2, 0]]
    }
    executor = GraphExecutor(data, mock_registry)
    assert executor.is_streaming
    with pytest.raises(RuntimeError, match="Cannot use execute"):
        await executor.execute()

    stream = executor.stream()
    initial = await anext(stream)
    assert initial == {}  # No static nodes

    tick1 = await anext(stream)
    assert tick1[1] == {"stream": "tick1"}
    assert tick1[2] == {"output": "processed_tick1"}  # Processed input from stream

    tick2 = await anext(stream)
    assert tick2[1] == {"stream": "tick2"}
    assert tick2[2] == {"output": "processed_tick2"}

    await executor.stop()

@pytest.mark.asyncio
async def test_stop_streaming(mock_registry):
    data = {"nodes": [{"id": 1, "type": "MockStreamingNode"}], "links": []}
    executor = GraphExecutor(data, mock_registry)
    stream = executor.stream()
    await anext(stream)  # Initial
    await executor.stop()
    with pytest.raises(StopAsyncIteration):
        await anext(stream)
