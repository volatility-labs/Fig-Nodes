import asyncio
import logging
from enum import Enum
from typing import Any

import rustworkx as rx

from core.api_key_vault import APIKeyVault
from core.types_registry import (
    NodeExecutionError,
    ProgressCallback,
    SerialisableGraph,
    SerialisedLink,
)
from nodes.base.base_node import Base

logger = logging.getLogger(__name__)

NodeId = int
ExecutionResults = dict[NodeId, dict[str, Any]]


class _GraphExecutionState(Enum):
    IDLE = "idle"
    RUNNING = "running"
    STOPPING = "stopping"
    STOPPED = "stopped"


class GraphExecutor:
    def __init__(self, graph: SerialisableGraph, node_registry: dict[str, type[Base]]):
        self.graph = graph
        self.node_registry = node_registry
        self.nodes: dict[int, Base] = {}
        self.input_names: dict[int, list[str]] = {}
        self.output_names: dict[int, list[str]] = {}
        self.dag: rx.PyDiGraph = rx.PyDiGraph()
        self._id_to_idx: dict[int, int] = {}
        self._idx_to_id: dict[int, int] = {}
        self._state: _GraphExecutionState = _GraphExecutionState.IDLE
        self._cancellation_reason: str | None = None
        self._progress_callback: ProgressCallback | None = None
        self.vault = APIKeyVault()
        self._active_tasks: list[
            asyncio.Task[tuple[int, dict[str, Any]]]
        ] = []  # Track active tasks for cancellation
        self._build_graph()

    def _build_graph_context(self, node_id: int) -> dict[str, Any]:
        """Build graph context for a node."""
        return {
            "graph_id": self.graph.get("id"),
            "nodes": self.graph.get("nodes", []),
            "links": self.graph.get("links", []),
            "current_node_id": node_id,
        }

    def _build_graph(self):
        for node_data in self.graph.get("nodes", []) or []:
            node_id = node_data["id"]
            node_type = node_data["type"]
            if node_type not in self.node_registry:
                raise ValueError(f"Unknown node type: {node_type}")
            properties = node_data.get("properties", {})

            # Build graph context for nodes to consume when executing
            graph_context = self._build_graph_context(node_id)

            self.nodes[node_id] = self.node_registry[node_type](node_id, properties, graph_context)
            input_list = [inp.get("name", "") for inp in node_data.get("inputs", [])]
            if input_list:
                self.input_names[node_id] = input_list
            output_list = [out.get("name", "") for out in node_data.get("outputs", [])]
            if output_list:
                self.output_names[node_id] = output_list
            idx = self.dag.add_node(node_id)
            self._id_to_idx[node_id] = idx
            self._idx_to_id[idx] = node_id

        for link in self.graph.get("links", []) or []:
            s_link: SerialisedLink = link
            from_id = s_link["origin_id"]
            to_id = s_link["target_id"]
            self.dag.add_edge(self._id_to_idx[from_id], self._id_to_idx[to_id], None)

        if not _rx_is_dag(self.dag):
            raise ValueError("Graph contains cycles")

    # ============================================================================
    # Execution Flow
    # ============================================================================

    async def execute(self) -> ExecutionResults:
        results: dict[int, dict[str, Any]] = {}
        levels = _rx_levels(self.dag)
        self._active_tasks.clear()
        self._state = _GraphExecutionState.RUNNING

        try:
            await self._execute_levels(levels, results)
        except Exception as e:
            logger.error(f"Execution failed: {e}", exc_info=True)
        finally:
            await self._cleanup_execution()

        return results

    async def _execute_levels(
        self, levels: list[list[int]], results: dict[int, dict[str, Any]]
    ) -> None:
        """Execute all levels of the graph."""
        for level in levels:
            if self._should_stop():
                break

            tasks: list[asyncio.Task[tuple[int, dict[str, Any]]]] = []
            for node_idx in level:
                node_id = self._idx_to_id[node_idx]
                if self.dag.in_degree(node_idx) == 0 and self.dag.out_degree(node_idx) == 0:
                    continue

                node = self.nodes[node_id]
                inputs = self._get_node_inputs(node_id, results)

                merged_inputs = {
                    **{
                        k: v
                        for k, v in node.params.items()
                        if k in node.inputs and k not in inputs and v is not None
                    },
                    **inputs,
                }

                task = asyncio.create_task(
                    self._execute_node_with_error_handling(node_id, node, merged_inputs)
                )
                tasks.append(task)
                self._active_tasks.append(task)

            if tasks:
                if self._should_stop():
                    self._cancel_all_tasks(tasks)
                    break

                level_results = await asyncio.gather(*tasks, return_exceptions=True)

                if self._should_stop():
                    break

                self._process_level_results(level_results, results)

    def _process_level_results(
        self, level_results: list[Any], results: dict[int, dict[str, Any]]
    ) -> None:
        """Process results from a level execution."""
        for level_result in level_results:
            if isinstance(level_result, Exception):
                if isinstance(level_result, asyncio.CancelledError):
                    continue
                logger.error(f"Task failed with exception: {level_result}", exc_info=True)
            elif isinstance(level_result, tuple):
                node_id, output = level_result  # type: ignore[assignment]
                if isinstance(node_id, int) and isinstance(output, dict):
                    results[node_id] = output

    async def _cleanup_execution(self) -> None:
        """Clean up execution state and cancel remaining tasks."""
        if self._active_tasks:
            self._cancel_all_tasks(self._active_tasks)
            await asyncio.gather(*self._active_tasks, return_exceptions=True)

        if self._should_stop():
            self._state = _GraphExecutionState.STOPPED

    # ============================================================================
    # Node Execution Utilities
    # ============================================================================

    async def _execute_node_with_error_handling(
        self, node_id: int, node: Base, merged_inputs: dict[str, Any]
    ) -> tuple[int, dict[str, Any]]:
        try:
            outputs = await node.execute(merged_inputs)
            return node_id, outputs
        except NodeExecutionError as e:
            if hasattr(e, "original_exc") and e.original_exc:
                print(
                    f"ERROR_TRACE: Original exception: {type(e.original_exc).__name__}: {str(e.original_exc)}"
                )
            logger.error(f"Node {node_id} failed: {str(e)}")
            return node_id, {"error": str(e)}
        except asyncio.CancelledError:
            print("STOP_TRACE: Caught CancelledError in node.execute await in GraphExecutor")
            self.force_stop()
            raise
        except Exception as e:
            print(
                f"ERROR_TRACE: Unexpected exception in node {node_id}: {type(e).__name__}: {str(e)}"
            )
            logger.error(f"Unexpected error in node {node_id}: {str(e)}", exc_info=True)
            return node_id, {"error": f"Unexpected error: {str(e)}"}

    def _get_node_inputs(self, node_id: int, results: dict[int, dict[str, Any]]) -> dict[str, Any]:
        inputs: dict[str, Any] = {}
        # Derive inputs solely from the link table to avoid index/weight ambiguity
        for link in self.graph.get("links", []) or []:
            s_link: SerialisedLink = link
            if s_link["target_id"] != node_id:
                continue
            pred_id = s_link["origin_id"]
            output_slot = s_link["origin_slot"]
            input_slot = s_link["target_slot"]
            pred_node = self.nodes.get(pred_id)
            if pred_node is None:
                continue
            pred_outputs: list[str] = self.output_names.get(
                pred_id, [str(k) for k in pred_node.outputs.keys()]
            )
            if output_slot >= len(pred_outputs):
                continue

            output_key = pred_outputs[output_slot]
            if pred_id not in results or output_key not in results[pred_id]:
                continue
            value = results[pred_id][output_key]

            node_inputs: list[str] = self.input_names.get(
                node_id, [str(k) for k in self.nodes[node_id].inputs.keys()]
            )
            if input_slot < len(node_inputs):
                input_key = node_inputs[input_slot]
                inputs[input_key] = value
        return inputs

    # ============================================================================
    # Task Management
    # ============================================================================

    def _cancel_all_tasks(self, tasks: list[asyncio.Task[tuple[int, dict[str, Any]]]]):
        """Cancel all active tasks immediately."""
        for task in tasks:
            if not task.done():
                task.cancel()

    # ============================================================================
    # Stop/Cancellation
    # ============================================================================

    def force_stop(self, reason: str = "user"):
        """Single entrypoint to immediately kill all execution. Idempotent."""
        if (
            self.state == _GraphExecutionState.STOPPING
            or self.state == _GraphExecutionState.STOPPED
        ):
            return

        self._state = _GraphExecutionState.STOPPING
        self._cancellation_reason = reason

        # Cancel all active tasks FIRST
        print(f"STOP_TRACE: Cancelling {len(self._active_tasks)} active tasks")
        self._cancel_all_tasks(self._active_tasks)

        # Then force stop all nodes
        for node_id, node in self.nodes.items():
            print(f"STOP_TRACE: Calling force_stop on node {node_id} ({type(node).__name__})")
            node.force_stop()

        print("STOP_TRACE: Force stop completed in GraphExecutor")
        self._state = _GraphExecutionState.STOPPED

    async def stop(self, reason: str = "user"):
        print("STOP_TRACE: GraphExecutor.stop called")
        self.force_stop(reason=reason)

    # ============================================================================
    # State Management
    # ============================================================================

    @property
    def state(self) -> _GraphExecutionState:
        """Read-only property that prevents type narrowing."""
        return self._state

    @property
    def is_running(self) -> bool:
        """Check if executor is currently running."""
        return self._state == _GraphExecutionState.RUNNING

    @property
    def is_stopping(self) -> bool:
        """Check if executor is currently stopping."""
        return self._state == _GraphExecutionState.STOPPING

    @property
    def is_stopped(self) -> bool:
        """Check if executor has stopped."""
        return self._state == _GraphExecutionState.STOPPED

    @property
    def cancellation_reason(self) -> str | None:
        """Get the reason for cancellation, if any."""
        return self._cancellation_reason

    def _should_stop(self) -> bool:
        """Check if execution should stop. Prevents type narrowing."""
        return self.state == _GraphExecutionState.STOPPING

    # ============================================================================
    # Configuration
    # ============================================================================

    def set_progress_callback(self, callback: ProgressCallback) -> None:
        """Set a progress callback function."""
        self._progress_callback = callback
        for node in self.nodes.values():
            node.set_progress_callback(callback)


# ---- rustworkx helper shims with precise typing to satisfy the type checker ----
def _rx_levels(dag: Any) -> Any:
    return list(rx.topological_generations(dag))


def _rx_is_dag(dag: Any) -> bool:
    return rx.is_directed_acyclic_graph(dag)
