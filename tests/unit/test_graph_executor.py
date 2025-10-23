import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import asyncio
import networkx as nx
from typing import Dict, Any, AsyncGenerator
from core.graph_executor import GraphExecutor
from nodes.base.base_node import Base
from nodes.base.streaming_node import Streaming

# Mock Node Classes
class MockBaseNode(Base):
    def __init__(self, id: int, params: Dict[str, Any] = None):
        super().__init__(id=id, params=params)
    inputs = {"input": str}
    outputs = {"output": str}

    async def _execute_impl(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        return {"output": f"processed_{inputs.get('input', '')}"}

class MockStreamingNode(Streaming):
    def __init__(self, id: int, params: Dict[str, Any] = None):
        super().__init__(id=id, params=params)
    inputs = {}
    outputs = {"stream": str}
    is_streaming = True

    async def _start_impl(self, inputs: Dict[str, Any]) -> AsyncGenerator[Dict[str, Any], None]:
        yield {"stream": "tick1"}
        yield {"stream": "tick2"}

    async def _execute_impl(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        return {"stream": "execute_result"}

    def stop(self):
        pass

@pytest.fixture
def mock_registry():
    return {
        "MockBaseNode": MockBaseNode,
        "MockStreamingNode": MockStreamingNode,
    }

@pytest.fixture
def simple_graph_data():
    return {
        "nodes": [
            {"id": 1, "type": "MockBaseNode", "properties": {}},
            {"id": 2, "type": "MockBaseNode", "properties": {}}
        ],
        "links": [{"id": 0, "origin_id": 1, "origin_slot": 0, "target_id": 2, "target_slot": 0, "type": 0}]
    }

@pytest.mark.asyncio
async def test_build_graph(simple_graph_data, mock_registry):
    executor = GraphExecutor(simple_graph_data, mock_registry)
    assert len(executor.nodes) == 2
    # Check edge using node indices
    from_idx = executor._id_to_idx[1]
    to_idx = executor._id_to_idx[2]
    assert executor.dag.has_edge(from_idx, to_idx)
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
        "links": [
            {"id": 0, "origin_id": 1, "origin_slot": 0, "target_id": 2, "target_slot": 0, "type": 0},
            {"id": 1, "origin_id": 2, "origin_slot": 0, "target_id": 1, "target_slot": 0, "type": 0}
        ]
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
            {"id": 1, "type": "MockBaseNode"},
            {"id": 2, "type": "MockBaseNode"}
        ],
        "links": [{"id": 0, "origin_id": 1, "origin_slot": 0, "target_id": 2, "target_slot": 0, "type": 0}]
    }
    executor = GraphExecutor(data, mock_registry)
    results = await executor.execute()
    assert 1 in results and 2 in results

@pytest.mark.asyncio
async def test_streaming_graph(mock_registry):
    # Streaming support removed - simplified to batch execution only
    data = {
        "nodes": [
            {"id": 1, "type": "MockBaseNode"},
            {"id": 2, "type": "MockBaseNode"}
        ],
        "links": [{"id": 0, "origin_id": 1, "origin_slot": 0, "target_id": 2, "target_slot": 0, "type": 0}]
    }
    executor = GraphExecutor(data, mock_registry)
    assert not executor.is_streaming
    results = await executor.execute()
    assert 1 in results and 2 in results

@pytest.mark.asyncio
async def test_stop_streaming(mock_registry):
    # Streaming support removed - simplified to batch execution only
    data = {"nodes": [{"id": 1, "type": "MockBaseNode"}], "links": []}
    executor = GraphExecutor(data, mock_registry)
    results = await executor.execute()
    assert results == {}
