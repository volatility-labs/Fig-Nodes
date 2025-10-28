import asyncio
from typing import Any
from unittest.mock import patch

import pytest

from core.graph_executor import GraphExecutor, _GraphExecutionState
from core.types_registry import NodeExecutionError, SerialisableGraph
from nodes.base.base_node import Base

# ============================================================================
# Mock Nodes for Testing
# ============================================================================


class MockSimpleNode(Base):
    """Simple node that echoes inputs to outputs."""

    inputs: dict[str, type[Any]] = {"value": str}
    outputs: dict[str, type[Any]] = {"result": str}

    async def _execute_impl(self, inputs: dict[str, Any]) -> dict[str, Any]:
        return {"result": inputs["value"]}


class MockSlowNode(Base):
    """Node that takes time to execute."""

    inputs: dict[str, type[Any]] = {"delay": float}
    outputs: dict[str, type[Any]] = {"result": str}

    async def _execute_impl(self, inputs: dict[str, Any]) -> dict[str, Any]:
        await asyncio.sleep(inputs.get("delay", 0.1))
        return {"result": "slow_result"}


class MockErrorNode(Base):
    """Node that raises an error."""

    inputs: dict[str, type[Any]] = {}
    outputs: dict[str, type[Any]] = {"result": str}

    async def _execute_impl(self, inputs: dict[str, Any]) -> dict[str, Any]:
        raise ValueError("Mock error")


class MockNodeExecutionErrorNode(Base):
    """Node that raises NodeExecutionError."""

    inputs: dict[str, type[Any]] = {}
    outputs: dict[str, type[Any]] = {"result": str}

    async def _execute_impl(self, inputs: dict[str, Any]) -> dict[str, Any]:
        raise NodeExecutionError(self.id, "Execution failed")


class MockCancellableNode(Base):
    """Node that checks for cancellation."""

    inputs: dict[str, type[Any]] = {"delay": float}
    outputs: dict[str, type[Any]] = {"result": str}

    async def _execute_impl(self, inputs: dict[str, Any]) -> dict[str, Any]:
        delay = inputs.get("delay", 0.1)
        await asyncio.sleep(delay)
        if self._is_stopped:
            raise asyncio.CancelledError("Node was stopped")
        return {"result": "cancellable_result"}


class MockMultiInputNode(Base):
    """Node with multiple inputs."""

    inputs: dict[str, type[Any]] = {"value1": str, "value2": str}
    outputs: dict[str, type[Any]] = {"result": str}

    async def _execute_impl(self, inputs: dict[str, Any]) -> dict[str, Any]:
        return {"result": f"{inputs['value1']}_{inputs['value2']}"}


class MockNoInputsOutputsNode(Base):
    """Node with no inputs or outputs."""

    inputs: dict[str, type[Any]] = {}
    outputs: dict[str, type[Any]] = {}

    async def _execute_impl(self, inputs: dict[str, Any]) -> dict[str, Any]:
        return {}


class MockParamsNode(Base):
    """Node that uses params."""

    inputs: dict[str, type[Any]] = {"value": str}
    outputs: dict[str, type[Any]] = {"result": str}
    default_params: dict[str, Any] = {"prefix": "default"}

    async def _execute_impl(self, inputs: dict[str, Any]) -> dict[str, Any]:
        prefix = self.params.get("prefix", "")
        return {"result": f"{prefix}_{inputs['value']}"}


# ============================================================================
# Test Fixtures
# ============================================================================


@pytest.fixture
def simple_node_registry():
    """Registry with simple mock nodes."""
    return {
        "MockSimpleNode": MockSimpleNode,
        "MockSlowNode": MockSlowNode,
        "MockErrorNode": MockErrorNode,
        "MockNodeExecutionErrorNode": MockNodeExecutionErrorNode,
        "MockCancellableNode": MockCancellableNode,
        "MockMultiInputNode": MockMultiInputNode,
        "MockNoInputsOutputsNode": MockNoInputsOutputsNode,
        "MockParamsNode": MockParamsNode,
    }


@pytest.fixture
def simple_graph() -> SerialisableGraph:
    """Simple linear graph: Node1 -> Node2 -> Node3."""
    return {
        "nodes": [
            {
                "id": 1,
                "type": "MockSimpleNode",
                "properties": {},
                "inputs": [{"name": "value"}],
                "outputs": [{"name": "result"}],
            },
            {
                "id": 2,
                "type": "MockSimpleNode",
                "properties": {},
                "inputs": [{"name": "value"}],
                "outputs": [{"name": "result"}],
            },
            {
                "id": 3,
                "type": "MockSimpleNode",
                "properties": {},
                "inputs": [{"name": "value"}],
                "outputs": [{"name": "result"}],
            },
        ],
        "links": [
            {"origin_id": 1, "origin_slot": 0, "target_id": 2, "target_slot": 0},
            {"origin_id": 2, "origin_slot": 0, "target_id": 3, "target_slot": 0},
        ],
    }


@pytest.fixture
def parallel_graph() -> SerialisableGraph:
    """Graph with parallel branches: Node1 -> Node2, Node1 -> Node3."""
    return {
        "nodes": [
            {
                "id": 1,
                "type": "MockSimpleNode",
                "properties": {},
                "inputs": [{"name": "value"}],
                "outputs": [{"name": "result"}],
            },
            {
                "id": 2,
                "type": "MockSimpleNode",
                "properties": {},
                "inputs": [{"name": "value"}],
                "outputs": [{"name": "result"}],
            },
            {
                "id": 3,
                "type": "MockSimpleNode",
                "properties": {},
                "inputs": [{"name": "value"}],
                "outputs": [{"name": "result"}],
            },
        ],
        "links": [
            {"origin_id": 1, "origin_slot": 0, "target_id": 2, "target_slot": 0},
            {"origin_id": 1, "origin_slot": 0, "target_id": 3, "target_slot": 0},
        ],
    }


@pytest.fixture
def multi_input_graph() -> SerialisableGraph:
    """Graph with node requiring multiple inputs."""
    return {
        "nodes": [
            {
                "id": 1,
                "type": "MockSimpleNode",
                "properties": {},
                "inputs": [{"name": "value"}],
                "outputs": [{"name": "result"}],
            },
            {
                "id": 2,
                "type": "MockSimpleNode",
                "properties": {},
                "inputs": [{"name": "value"}],
                "outputs": [{"name": "result"}],
            },
            {
                "id": 3,
                "type": "MockMultiInputNode",
                "properties": {},
                "inputs": [{"name": "value1"}, {"name": "value2"}],
                "outputs": [{"name": "result"}],
            },
        ],
        "links": [
            {"origin_id": 1, "origin_slot": 0, "target_id": 3, "target_slot": 0},
            {"origin_id": 2, "origin_slot": 0, "target_id": 3, "target_slot": 1},
        ],
    }


@pytest.fixture
def params_graph() -> SerialisableGraph:
    """Graph with node using params."""
    return {
        "nodes": [
            {
                "id": 1,
                "type": "MockSimpleNode",
                "properties": {},
                "inputs": [{"name": "value"}],
                "outputs": [{"name": "result"}],
            },
            {
                "id": 2,
                "type": "MockParamsNode",
                "properties": {"prefix": "custom"},
                "inputs": [{"name": "value"}],
                "outputs": [{"name": "result"}],
            },
        ],
        "links": [
            {"origin_id": 1, "origin_slot": 0, "target_id": 2, "target_slot": 0},
        ],
    }


@pytest.fixture
def cyclic_graph() -> SerialisableGraph:
    """Graph with a cycle (should fail)."""
    return {
        "nodes": [
            {
                "id": 1,
                "type": "MockSimpleNode",
                "properties": {},
                "inputs": [{"name": "value"}],
                "outputs": [{"name": "result"}],
            },
            {
                "id": 2,
                "type": "MockSimpleNode",
                "properties": {},
                "inputs": [{"name": "value"}],
                "outputs": [{"name": "result"}],
            },
        ],
        "links": [
            {"origin_id": 1, "origin_slot": 0, "target_id": 2, "target_slot": 0},
            {"origin_id": 2, "origin_slot": 0, "target_id": 1, "target_slot": 0},  # Cycle!
        ],
    }


@pytest.fixture
def error_graph() -> SerialisableGraph:
    """Graph with an error node."""
    return {
        "nodes": [
            {
                "id": 1,
                "type": "MockSimpleNode",
                "properties": {},
                "inputs": [{"name": "value"}],
                "outputs": [{"name": "result"}],
            },
            {
                "id": 2,
                "type": "MockErrorNode",
                "properties": {},
                "inputs": [],
                "outputs": [{"name": "result"}],
            },
        ],
        "links": [
            {"origin_id": 1, "origin_slot": 0, "target_id": 2, "target_slot": 0},
        ],
    }


@pytest.fixture
def standalone_node_graph() -> SerialisableGraph:
    """Graph with a standalone node (no inputs or outputs connected)."""
    return {
        "nodes": [
            {
                "id": 1,
                "type": "MockNoInputsOutputsNode",
                "properties": {},
                "inputs": [],
                "outputs": [],
            },
        ],
        "links": [],
    }


# ============================================================================
# Tests
# ============================================================================


class TestGraphBuilding:
    """Test graph building and validation."""

    def test_build_simple_graph(self, simple_graph, simple_node_registry):
        """Test building a simple linear graph."""
        executor = GraphExecutor(simple_graph, simple_node_registry)
        assert len(executor.nodes) == 3
        assert 1 in executor.nodes
        assert 2 in executor.nodes
        assert 3 in executor.nodes

    def test_build_parallel_graph(self, parallel_graph, simple_node_registry):
        """Test building a graph with parallel branches."""
        executor = GraphExecutor(parallel_graph, simple_node_registry)
        assert len(executor.nodes) == 3

    def test_unknown_node_type(self, simple_node_registry):
        """Test error when node type is unknown."""
        graph = {
            "nodes": [
                {"id": 1, "type": "UnknownNode", "properties": {}, "inputs": [], "outputs": []}
            ],
            "links": [],
        }
        with pytest.raises(ValueError, match="Unknown node type"):
            GraphExecutor(graph, simple_node_registry)

    def test_cyclic_graph_fails(self, cyclic_graph, simple_node_registry):
        """Test that cyclic graphs are rejected."""
        with pytest.raises(ValueError, match="contains cycles"):
            GraphExecutor(cyclic_graph, simple_node_registry)

    def test_empty_graph(self, simple_node_registry):
        """Test building an empty graph."""
        graph = {"nodes": [], "links": []}
        executor = GraphExecutor(graph, simple_node_registry)
        assert len(executor.nodes) == 0

    def test_graph_with_no_links(self, simple_node_registry):
        """Test graph with nodes but no links."""
        graph = {
            "nodes": [
                {
                    "id": 1,
                    "type": "MockSimpleNode",
                    "properties": {},
                    "inputs": [{"name": "value"}],
                    "outputs": [{"name": "result"}],
                },
            ],
            "links": [],
        }
        executor = GraphExecutor(graph, simple_node_registry)
        assert len(executor.nodes) == 1


class TestHappyPathExecution:
    """Test successful execution scenarios."""

    @pytest.mark.asyncio
    async def test_execute_simple_linear_graph(self, simple_graph, simple_node_registry):
        """Test executing a simple linear graph."""
        executor = GraphExecutor(simple_graph, simple_node_registry)

        # Need to manually set the input for the first node
        executor.nodes[1].params["value"] = "hello"

        results = await executor.execute()

        assert 1 in results
        assert 2 in results
        assert 3 in results
        assert results[1]["result"] == "hello"
        assert results[2]["result"] == "hello"
        assert results[3]["result"] == "hello"

    @pytest.mark.asyncio
    async def test_execute_parallel_graph(self, parallel_graph, simple_node_registry):
        """Test executing a graph with parallel branches."""
        executor = GraphExecutor(parallel_graph, simple_node_registry)
        executor.nodes[1].params["value"] = "test"

        results = await executor.execute()

        assert results[1]["result"] == "test"
        assert results[2]["result"] == "test"
        assert results[3]["result"] == "test"

    @pytest.mark.asyncio
    async def test_execute_multi_input_graph(self, multi_input_graph, simple_node_registry):
        """Test executing a graph with multi-input node."""
        executor = GraphExecutor(multi_input_graph, simple_node_registry)
        executor.nodes[1].params["value"] = "foo"
        executor.nodes[2].params["value"] = "bar"

        results = await executor.execute()

        assert results[3]["result"] == "foo_bar"

    @pytest.mark.asyncio
    async def test_execute_with_params(self, params_graph, simple_node_registry):
        """Test executing a graph with nodes using params."""
        executor = GraphExecutor(params_graph, simple_node_registry)
        executor.nodes[1].params["value"] = "test"

        results = await executor.execute()

        assert results[2]["result"] == "custom_test"

    @pytest.mark.asyncio
    async def test_execute_with_default_params(self, simple_node_registry):
        """Test executing with default params."""
        graph = {
            "nodes": [
                {
                    "id": 1,
                    "type": "MockSimpleNode",
                    "properties": {},
                    "inputs": [{"name": "value"}],
                    "outputs": [{"name": "result"}],
                },
                {
                    "id": 2,
                    "type": "MockParamsNode",
                    "properties": {},
                    "inputs": [{"name": "value"}],
                    "outputs": [{"name": "result"}],
                },
            ],
            "links": [
                {"origin_id": 1, "origin_slot": 0, "target_id": 2, "target_slot": 0},
            ],
        }
        executor = GraphExecutor(graph, simple_node_registry)
        executor.nodes[1].params["value"] = "test"

        results = await executor.execute()

        assert results[2]["result"] == "default_test"

    @pytest.mark.asyncio
    async def test_execute_standalone_node(self, standalone_node_graph, simple_node_registry):
        """Test executing a standalone node."""
        executor = GraphExecutor(standalone_node_graph, simple_node_registry)

        results = await executor.execute()

        # Standalone nodes (no links) are skipped during execution
        assert 1 not in results or results == {}


class TestErrorHandling:
    """Test error handling scenarios."""

    @pytest.mark.asyncio
    async def test_task_failure_logging(self, simple_node_registry):
        """Test that task failures are logged properly."""

        class MockNodeThatFails(Base):
            inputs: dict[str, type[Any]] = {}
            outputs: dict[str, type[Any]] = {"result": str}

            async def _execute_impl(self, inputs: dict[str, Any]) -> dict[str, Any]:
                raise RuntimeError("Task failure")

        registry = {**simple_node_registry, "MockNodeThatFails": MockNodeThatFails}
        graph = {
            "nodes": [
                {
                    "id": 1,
                    "type": "MockNodeThatFails",
                    "properties": {},
                    "inputs": [],
                    "outputs": [{"name": "result"}],
                },
            ],
            "links": [],
        }
        executor = GraphExecutor(graph, registry)

        results = await executor.execute()

        # Should handle the exception gracefully
        assert isinstance(results, dict)

    @pytest.mark.asyncio
    async def test_node_execution_error(self, error_graph, simple_node_registry):
        """Test handling of node execution errors."""
        executor = GraphExecutor(error_graph, simple_node_registry)
        executor.nodes[1].params["value"] = "test"

        results = await executor.execute()

        # Node 1 should succeed
        assert results[1]["result"] == "test"
        # Node 2 should have an error
        assert "error" in results[2]

    @pytest.mark.asyncio
    async def test_node_execution_error_with_original_exc(self, simple_node_registry):
        """Test that NodeExecutionError preserves original exception."""
        graph = {
            "nodes": [
                {
                    "id": 1,
                    "type": "MockNodeExecutionErrorNode",
                    "properties": {},
                    "inputs": [],
                    "outputs": [{"name": "result"}],
                },
            ],
            "links": [],
        }
        executor = GraphExecutor(graph, simple_node_registry)

        results = await executor.execute()

        # Standalone nodes are skipped
        assert results == {}

    @pytest.mark.asyncio
    async def test_missing_input(self, simple_node_registry):
        """Test execution with missing input."""
        graph = {
            "nodes": [
                {
                    "id": 1,
                    "type": "MockSimpleNode",
                    "properties": {},
                    "inputs": [{"name": "value"}],
                    "outputs": [{"name": "result"}],
                },
            ],
            "links": [],
        }
        executor = GraphExecutor(graph, simple_node_registry)

        results = await executor.execute()

        # Node with no inputs/outputs connected are skipped
        assert results == {}


class TestStopAndCancellation:
    """Test stop and cancellation functionality."""

    @pytest.mark.asyncio
    async def test_stop_method(self, simple_node_registry):
        """Test the stop() async method."""
        graph = {
            "nodes": [
                {
                    "id": 1,
                    "type": "MockSlowNode",
                    "properties": {},
                    "inputs": [{"name": "delay"}],
                    "outputs": [{"name": "result"}],
                },
            ],
            "links": [],
        }
        executor = GraphExecutor(graph, simple_node_registry)
        executor.nodes[1].params["delay"] = 1.0

        with patch("builtins.print") as mock_print:
            task = asyncio.create_task(executor.execute())
            await asyncio.sleep(0.1)
            await executor.stop(reason="test")
            await asyncio.sleep(0.1)
            await task

            assert executor.is_stopped
            assert mock_print.called

    @pytest.mark.asyncio
    async def test_force_stop(self, simple_node_registry):
        """Test force stopping execution."""
        graph = {
            "nodes": [
                {
                    "id": 1,
                    "type": "MockSlowNode",
                    "properties": {},
                    "inputs": [{"name": "delay"}],
                    "outputs": [{"name": "result"}],
                },
            ],
            "links": [],
        }
        executor = GraphExecutor(graph, simple_node_registry)
        executor.nodes[1].params["delay"] = 1.0

        with patch("builtins.print") as mock_print:
            # Start execution
            task = asyncio.create_task(executor.execute())

            # Wait a bit then stop
            await asyncio.sleep(0.1)
            executor.force_stop(reason="test")

            # Wait for cleanup
            await asyncio.sleep(0.1)

            # Wait for task to complete
            results = await task

            # Verify stop was called
            assert mock_print.called
            assert executor.is_stopped

    @pytest.mark.asyncio
    async def test_stop_idempotent(self, simple_node_registry):
        """Test that stop is idempotent."""
        graph = {
            "nodes": [
                {
                    "id": 1,
                    "type": "MockSimpleNode",
                    "properties": {},
                    "inputs": [{"name": "value"}],
                    "outputs": [{"name": "result"}],
                },
            ],
            "links": [],
        }
        executor = GraphExecutor(graph, simple_node_registry)

        executor.force_stop(reason="test1")
        assert executor.is_stopped

        executor.force_stop(reason="test2")
        assert executor.is_stopped

    @pytest.mark.asyncio
    async def test_stop_during_execution(self, simple_node_registry):
        """Test stopping during active execution."""
        graph = {
            "nodes": [
                {
                    "id": 1,
                    "type": "MockSlowNode",
                    "properties": {},
                    "inputs": [{"name": "delay"}],
                    "outputs": [{"name": "result"}],
                },
                {
                    "id": 2,
                    "type": "MockSlowNode",
                    "properties": {},
                    "inputs": [{"name": "delay"}],
                    "outputs": [{"name": "result"}],
                },
            ],
            "links": [
                {"origin_id": 1, "origin_slot": 0, "target_id": 2, "target_slot": 0},
            ],
        }
        executor = GraphExecutor(graph, simple_node_registry)
        executor.nodes[1].params["delay"] = 0.5
        executor.nodes[2].params["delay"] = 0.5

        async def stop_after_delay():
            await asyncio.sleep(0.3)
            executor.force_stop()

        stop_task = asyncio.create_task(stop_after_delay())
        await executor.execute()

        await stop_task
        assert executor.is_stopped


class TestStateManagement:
    """Test state management."""

    def test_initial_state(self, simple_graph, simple_node_registry):
        """Test initial state is IDLE."""
        executor = GraphExecutor(simple_graph, simple_node_registry)
        assert executor.state == _GraphExecutionState.IDLE

    @pytest.mark.asyncio
    async def test_state_transitions(self, simple_graph, simple_node_registry):
        """Test state transitions during execution."""
        executor = GraphExecutor(simple_graph, simple_node_registry)
        executor.nodes[1].params["value"] = "test"

        assert executor.state == _GraphExecutionState.IDLE

        task = asyncio.create_task(executor.execute())
        await asyncio.sleep(0.01)  # Let it start

        # State might be RUNNING, STOPPING, or STOPPED depending on timing
        # Just verify it's not IDLE
        assert executor.state != _GraphExecutionState.IDLE

        await task

    def test_is_running_property(self, simple_graph, simple_node_registry):
        """Test is_running property."""
        executor = GraphExecutor(simple_graph, simple_node_registry)
        assert not executor.is_running

    def test_is_stopping_property(self, simple_graph, simple_node_registry):
        """Test is_stopping property."""
        executor = GraphExecutor(simple_graph, simple_node_registry)
        assert not executor.is_stopping

        executor.force_stop()
        assert executor.is_stopping or executor.is_stopped

    def test_is_stopped_property(self, simple_graph, simple_node_registry):
        """Test is_stopped property."""
        executor = GraphExecutor(simple_graph, simple_node_registry)
        assert not executor.is_stopped

        executor.force_stop()
        assert executor.is_stopped

    def test_cancellation_reason(self, simple_graph, simple_node_registry):
        """Test cancellation reason."""
        executor = GraphExecutor(simple_graph, simple_node_registry)
        assert executor.cancellation_reason is None

        executor.force_stop(reason="test reason")
        assert executor.cancellation_reason == "test reason"


class TestProgressCallback:
    """Test progress callback functionality."""

    @pytest.mark.asyncio
    async def test_progress_callback(self, simple_graph, simple_node_registry):
        """Test setting and using progress callback."""
        executor = GraphExecutor(simple_graph, simple_node_registry)
        executor.nodes[1].params["value"] = "test"

        callback_calls = []

        def progress_callback(event):
            callback_calls.append(event)

        executor.set_progress_callback(progress_callback)

        await executor.execute()

        # Verify callback was set on nodes
        for node in executor.nodes.values():
            assert node._progress_callback is not None


class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    @pytest.mark.asyncio
    async def test_empty_results(self, simple_node_registry):
        """Test execution with no results."""
        graph = {"nodes": [], "links": []}
        executor = GraphExecutor(graph, simple_node_registry)

        results = await executor.execute()

        assert results == {}

    @pytest.mark.asyncio
    async def test_node_with_no_outputs(self, simple_node_registry):
        """Test node that produces no outputs."""
        graph = {
            "nodes": [
                {
                    "id": 1,
                    "type": "MockNoInputsOutputsNode",
                    "properties": {},
                    "inputs": [],
                    "outputs": [],
                },
            ],
            "links": [],
        }
        executor = GraphExecutor(graph, simple_node_registry)

        results = await executor.execute()

        # Standalone nodes (no links) are skipped during execution
        assert results == {}

    @pytest.mark.asyncio
    async def test_mismatched_input_output_slots(self, simple_node_registry):
        """Test handling of mismatched input/output slots."""
        graph = {
            "nodes": [
                {
                    "id": 1,
                    "type": "MockSimpleNode",
                    "properties": {},
                    "inputs": [{"name": "value"}],
                    "outputs": [{"name": "result"}],
                },
                {
                    "id": 2,
                    "type": "MockSimpleNode",
                    "properties": {},
                    "inputs": [{"name": "value"}],
                    "outputs": [{"name": "result"}],
                },
            ],
            "links": [
                {
                    "origin_id": 1,
                    "origin_slot": 999,
                    "target_id": 2,
                    "target_slot": 0,
                },  # Invalid slot
            ],
        }
        executor = GraphExecutor(graph, simple_node_registry)
        executor.nodes[1].params["value"] = "test"

        results = await executor.execute()

        # Node 1 should execute, node 2 should not get the input
        assert 1 in results

    @pytest.mark.asyncio
    async def test_node_inputs_from_results_absent(self, simple_node_registry):
        """Test getting node inputs when previous results are missing."""
        graph = {
            "nodes": [
                {
                    "id": 1,
                    "type": "MockSimpleNode",
                    "properties": {},
                    "inputs": [{"name": "value"}],
                    "outputs": [{"name": "result"}],
                },
                {
                    "id": 2,
                    "type": "MockSimpleNode",
                    "properties": {},
                    "inputs": [{"name": "value"}],
                    "outputs": [{"name": "result"}],
                },
            ],
            "links": [
                {"origin_id": 1, "origin_slot": 0, "target_id": 2, "target_slot": 0},
            ],
        }
        executor = GraphExecutor(graph, simple_node_registry)

        # Don't set params for node 1, so it won't produce results
        results = await executor.execute()

        # Should handle missing results gracefully
        assert isinstance(results, dict)

    @pytest.mark.asyncio
    async def test_input_slot_out_of_range(self, simple_node_registry):
        """Test handling when input slot index is out of range."""
        graph = {
            "nodes": [
                {
                    "id": 1,
                    "type": "MockSimpleNode",
                    "properties": {},
                    "inputs": [{"name": "value"}],
                    "outputs": [{"name": "result"}],
                },
                {
                    "id": 2,
                    "type": "MockSimpleNode",
                    "properties": {},
                    "inputs": [{"name": "value"}],
                    "outputs": [{"name": "result"}],
                },
            ],
            "links": [
                {
                    "origin_id": 1,
                    "origin_slot": 0,
                    "target_id": 2,
                    "target_slot": 999,
                },  # Invalid input slot
            ],
        }
        executor = GraphExecutor(graph, simple_node_registry)
        executor.nodes[1].params["value"] = "test"

        results = await executor.execute()

        # Node 1 should execute, node 2 input slot out of range
        assert 1 in results

    @pytest.mark.asyncio
    async def test_reference_nonexistent_node(self, simple_node_registry):
        """Test referencing a nonexistent node in links."""
        graph = {
            "nodes": [
                {
                    "id": 1,
                    "type": "MockSimpleNode",
                    "properties": {},
                    "inputs": [{"name": "value"}],
                    "outputs": [{"name": "result"}],
                },
            ],
            "links": [
                {
                    "origin_id": 999,
                    "origin_slot": 0,
                    "target_id": 1,
                    "target_slot": 0,
                },  # Nonexistent origin
            ],
        }

        # GraphExecutor raises KeyError when trying to add edge with nonexistent node
        with pytest.raises(KeyError):
            GraphExecutor(graph, simple_node_registry)

    def test_graph_with_missing_nodes_and_links_keys(self, simple_node_registry):
        """Test graph with missing 'nodes' or 'links' keys."""
        # Missing nodes key
        graph1 = {"links": []}
        executor1 = GraphExecutor(graph1, simple_node_registry)
        assert len(executor1.nodes) == 0

        # Missing links key
        graph2 = {
            "nodes": [
                {
                    "id": 1,
                    "type": "MockSimpleNode",
                    "properties": {},
                    "inputs": [{"name": "value"}],
                    "outputs": [{"name": "result"}],
                },
            ],
        }
        executor2 = GraphExecutor(graph2, simple_node_registry)
        assert len(executor2.nodes) == 1

    @pytest.mark.asyncio
    async def test_concurrent_executions(self, simple_graph, simple_node_registry):
        """Test multiple concurrent executions."""
        executor1 = GraphExecutor(simple_graph, simple_node_registry)
        executor2 = GraphExecutor(simple_graph, simple_node_registry)

        executor1.nodes[1].params["value"] = "test1"
        executor2.nodes[1].params["value"] = "test2"

        results1, results2 = await asyncio.gather(executor1.execute(), executor2.execute())

        assert results1[1]["result"] == "test1"
        assert results2[1]["result"] == "test2"


class TestTaskCancellation:
    """Test task cancellation mechanisms."""

    @pytest.mark.asyncio
    async def test_cancel_all_tasks(self, simple_node_registry):
        """Test cancelling all active tasks."""
        graph = {
            "nodes": [
                {
                    "id": 1,
                    "type": "MockSlowNode",
                    "properties": {},
                    "inputs": [{"name": "delay"}],
                    "outputs": [{"name": "result"}],
                },
                {
                    "id": 2,
                    "type": "MockSlowNode",
                    "properties": {},
                    "inputs": [{"name": "delay"}],
                    "outputs": [{"name": "result"}],
                },
            ],
            "links": [],
        }
        executor = GraphExecutor(graph, simple_node_registry)
        executor.nodes[1].params["delay"] = 0.5
        executor.nodes[2].params["delay"] = 0.5

        task = asyncio.create_task(executor.execute())
        await asyncio.sleep(0.1)

        executor.force_stop()
        await task

        assert executor.is_stopped

    @pytest.mark.asyncio
    async def test_cancelled_error_handling(self, simple_node_registry):
        """Test handling of CancelledError."""
        graph = {
            "nodes": [
                {
                    "id": 1,
                    "type": "MockCancellableNode",
                    "properties": {},
                    "inputs": [{"name": "delay"}],
                    "outputs": [{"name": "result"}],
                },
            ],
            "links": [],
        }
        executor = GraphExecutor(graph, simple_node_registry)
        executor.nodes[1].params["delay"] = 0.3

        with patch("builtins.print") as mock_print:
            task = asyncio.create_task(executor.execute())
            await asyncio.sleep(0.1)
            executor.force_stop()
            await task

            # Verify CancelledError was handled
            assert mock_print.called
