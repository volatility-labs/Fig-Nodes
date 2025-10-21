import rustworkx as rx  
from typing import Dict, Any, List, AsyncGenerator, Callable, NotRequired, Required, Type, TypedDict, Union, Set, cast
from nodes.base.base_node import Base
import asyncio
from nodes.base.streaming_node import Streaming
from core.api_key_vault import APIKeyVault
from core.types_registry import NodeExecutionError
import logging

logger = logging.getLogger(__name__)

# Types for the graph serialisation from LiteGraph.asSerialisable().
class SerialisedLink(TypedDict, total=False):
    """Object-based link used by LiteGraph.asSerialisable()."""
    id: Required[int]
    origin_id: Required[int]
    origin_slot: Required[int]
    target_id: Required[int]
    target_slot: Required[int]
    type: Required[Any]
    parentId: NotRequired[int]

class SerialisedNodeInput(TypedDict, total=False):
    name: str
    type: Any
    linkIds: NotRequired[List[int]]

class SerialisedNodeOutput(TypedDict, total=False):
    name: str
    type: Any
    linkIds: NotRequired[List[int]]

class SerialisedNode(TypedDict, total=False):
    id: Required[int]
    type: Required[str]
    title: NotRequired[str]
    pos: NotRequired[List[float]]
    size: NotRequired[List[float]]
    flags: NotRequired[Dict[str, Any]]
    order: NotRequired[int]
    mode: NotRequired[int]
    inputs: NotRequired[List[SerialisedNodeInput]]
    outputs: NotRequired[List[SerialisedNodeOutput]]
    properties: NotRequired[Dict[str, Any]]
    shape: NotRequired[Any]
    boxcolor: NotRequired[str]
    color: NotRequired[str]
    bgcolor: NotRequired[str]
    showAdvanced: NotRequired[bool]
    widgets_values: NotRequired[List[Any]]

class SerialisedGraphState(TypedDict, total=True):
    lastNodeId: int
    lastLinkId: int
    lastGroupId: int
    lastRerouteId: int

# Main graph serialisation type that copies the LiteGraph.asSerialisable() schema.
class SerialisableGraph(TypedDict, total=False):
    """Newer LiteGraph schema produced by graph.asSerialisable()."""
    id: str
    revision: int
    version: int  # 0 | 1
    state: SerialisedGraphState
    nodes: List[SerialisedNode]
    links: NotRequired[List[SerialisedLink]]
    floatingLinks: NotRequired[List[SerialisedLink]]
    reroutes: NotRequired[List[Dict[str, Any]]]
    groups: NotRequired[List[Dict[str, Any]]]
    extra: NotRequired[Dict[str, Any]]
    definitions: NotRequired[Dict[str, Any]]


class GraphExecutor:
    def __init__(self, graph: SerialisableGraph, node_registry: Dict[str, Type[Base]]):
        self.graph = graph
        self.node_registry = node_registry
        self.nodes: Dict[int, Base] = {}
        self.input_names: Dict[int, List[str]] = {}
        self.output_names: Dict[int, List[str]] = {}
        self.dag: rx.PyDiGraph = rx.PyDiGraph() 
        self._id_to_idx: Dict[int, int] = {}
        self._idx_to_id: Dict[int, int] = {}
        self.is_streaming: bool = False
        self.streaming_tasks: List[asyncio.Task[Any]] = []
        self._stopped: bool = False
        self._is_force_stopped: bool = False  # For idempotency
        self._progress_callback: Union[Callable[[int, float, str], None], None] = None
        self.vault = APIKeyVault()
        self._build_graph()

    def _build_graph(self):
        for node_data in self.graph.get('nodes', []) or []:
            node_id = node_data['id']
            node_type = node_data['type']
            if node_type not in self.node_registry:
                raise ValueError(f"Unknown node type: {node_type}")
            properties = node_data.get('properties', {})
            self.nodes[node_id] = self.node_registry[node_type](node_id, properties)
            input_list = [inp.get('name', '') for inp in node_data.get('inputs', [])]
            if input_list:
                self.input_names[node_id] = input_list
            output_list = [out.get('name', '') for out in node_data.get('outputs', [])]
            if output_list:
                self.output_names[node_id] = output_list
            # Add node to rustworkx graph and record index mapping
            idx = self.dag.add_node(node_id)
            self._id_to_idx[node_id] = idx
            self._idx_to_id[idx] = node_id

        for link in self.graph.get('links', []) or []:
            s_link: SerialisedLink = link  # TypedDict with required keys
            from_id = s_link['origin_id']
            to_id = s_link['target_id']
            self.dag.add_edge(self._id_to_idx[from_id], self._id_to_idx[to_id], None)

        if not _rx_is_dag(self.dag):
            raise ValueError("Graph contains cycles")
        
        # Determine if the graph is streaming by checking if any nodes are streaming and have connections
        def _total_degree(idx: int) -> int:
            return self.dag.in_degree(idx) + self.dag.out_degree(idx)

        self.is_streaming = any(
            isinstance(self.nodes[node_id], Streaming) and _total_degree(idx) > 0
            for idx, node_id in self._idx_to_id.items()
        )

    async def execute(self) -> Dict[int, Dict[str, Any]]:
        results: Dict[int, Dict[str, Any]] = {}
        sorted_indices = _rx_topo(self.dag)
        executed_nodes: Set[int] = set()

        for node_idx in sorted_indices:
            node_id = self._idx_to_id[node_idx]
            if self._stopped:
                break
            if node_id in executed_nodes:
                continue
            if self.dag.in_degree(node_idx) == 0 and self.dag.out_degree(node_idx) == 0:
                continue
            node = self.nodes[node_id]
            inputs = self._get_node_inputs(node_id, results)
            merged_inputs = {**{k: v for k, v in node.params.items() if k in node.inputs and k not in inputs and v is not None}, **inputs}
            try:
                outputs = await node.execute(merged_inputs) 
            except NodeExecutionError as e:  # Catches runtime errors only; validation errors propagate to stop graph
                if hasattr(e, 'original_exc') and e.original_exc:
                    print(f"ERROR_TRACE: Original exception: {type(e.original_exc).__name__}: {str(e.original_exc)}")
                logger.error(f"Node {node_id} failed: {str(e)}")
                results[node_id] = {"error": str(e)}
                continue
            except asyncio.CancelledError:
                print("STOP_TRACE: Caught CancelledError in node.execute await in GraphExecutor")
                self.force_stop()
                raise
            except Exception as e:
                print(f"ERROR_TRACE: Unexpected exception in node {node_id}: {type(e).__name__}: {str(e)}")
                logger.error(f"Unexpected error in node {node_id}: {str(e)}", exc_info=True)
                results[node_id] = {"error": f"Unexpected error: {str(e)}"}
                continue
            results[node_id] = outputs
        
        return results

    async def _execute_subgraph_for_tick(self, subgraph_nodes: List[int], context: Dict[int, Any]) -> Dict[int, Any]:
        tick_results: Dict[int, Any] = {}
        for sub_node_id in subgraph_nodes:
            # Important: The context for the current tick can be updated by previous nodes in the same tick
            current_context: Dict[int, Any] = {**context, **tick_results}
            sub_node = self.nodes[sub_node_id]
            sub_inputs = self._get_node_inputs(sub_node_id, current_context)
            merged_inputs = {**{k: v for k, v in sub_node.params.items() if k in sub_node.inputs and k not in sub_inputs and v is not None}, **sub_inputs}
            print(f"GraphExecutor: Merged inputs for sub_node {sub_node_id}: {merged_inputs}")
            
            try:
                print(f"DEBUG: Executing sub_node {sub_node_id} with inputs: {list(merged_inputs.keys())}")
                sub_outputs = await sub_node.execute(merged_inputs)  # Will raise NodeValidationError if invalid
                print(f"DEBUG: Sub_node {sub_node_id} completed with outputs: {list(sub_outputs.keys()) if sub_outputs else 'None'}")
            except NodeExecutionError as e:
                print(f"ERROR_TRACE: NodeExecutionError in sub_node {sub_node_id}: {str(e)}")
                if hasattr(e, 'original_exc') and e.original_exc:
                    print(f"ERROR_TRACE: Original exception: {type(e.original_exc).__name__}: {str(e.original_exc)}")
                logger.error(f"Sub node {sub_node_id} failed: {str(e)}")
                tick_results[sub_node_id] = {"error": str(e)}
                continue
            except Exception as e:
                print(f"ERROR_TRACE: Unexpected exception in sub_node {sub_node_id}: {type(e).__name__}: {str(e)}")
                logger.error(f"Unexpected error in sub_node {sub_node_id}: {str(e)}", exc_info=True)
                tick_results[sub_node_id] = {"error": f"Unexpected error: {str(e)}"}
                continue
            tick_results[sub_node_id] = sub_outputs
        return tick_results

    async def _run_streaming_source(self, source_id: int, initial_results: Dict[int, Any], result_queue: asyncio.Queue[Dict[int, Any]]):
        source_node = cast(Streaming, self.nodes[source_id])
        
        # Define the subgraph that depends on this source using descendants ordered by topological sort
        source_idx = self._id_to_idx[source_id]
        topo = _rx_topo(self.dag)
        descendants = _rx_desc(self.dag, source_idx)
        downstream_indices = [i for i in topo if i in descendants]
        downstream_nodes = [self._idx_to_id[i] for i in downstream_indices]

        source_inputs = self._get_node_inputs(source_id, initial_results)
        
        try:
            async for source_output in source_node.start(source_inputs):
                # The context for this tick includes all initial results plus the new output from the stream source
                tick_context = {**initial_results, source_id: source_output}
                
                # Execute the downstream nodes for this tick
                subgraph_results = await self._execute_subgraph_for_tick(downstream_nodes, tick_context)
                
                # Combine all results for this tick and put them in the queue
                final_tick_results = {source_id: source_output, **subgraph_results}
                await result_queue.put(final_tick_results)
        except NodeExecutionError as e:
            logger.error(f"Streaming source {source_id} failed: {str(e)}")
            error_output = {"error": str(e)}
            final_tick_results = {source_id: error_output}
            await result_queue.put(final_tick_results)

    async def stream(self) -> AsyncGenerator[Dict[int, Dict[str, Any]], None]:
        try:
            static_results: Dict[int, Dict[str, Any]] = {}
            
            streaming_pipeline_nodes: Set[int] = set()
            streaming_sources: List[int] = []
            for idx, node_id in self._idx_to_id.items():
                if isinstance(self.nodes[node_id], Streaming):
                    in_degree = self.dag.in_degree(idx)
                    out_degree = self.dag.out_degree(idx)
                    degree = in_degree + out_degree
                    print(f"GraphExecutor: Streaming {node_id} - degree={degree}, in_degree={in_degree}, out_degree={out_degree}")
                    if degree > 0:
                        streaming_sources.append(node_id)
                        streaming_pipeline_nodes.add(node_id)
                        for descendant_idx in _rx_desc(self.dag, idx):
                            streaming_pipeline_nodes.add(self._idx_to_id[descendant_idx])
                        print(f"GraphExecutor: Added Streaming {node_id} as streaming source")
                    else:
                        print(f"GraphExecutor: Skipped Streaming {node_id} - no connections")
        except Exception as e:
            print(f"GraphExecutor: Exception in stream setup: {e}")
            import traceback
            traceback.print_exc()
            raise

        try:
            # First, execute all nodes that are NOT part of any streaming pipeline
            sorted_indices = _rx_topo(self.dag)
            for node_idx in sorted_indices:
                node_id = self._idx_to_id[node_idx]
                if node_id not in streaming_pipeline_nodes:
                    if self.dag.in_degree(node_idx) == 0 and self.dag.out_degree(node_idx) == 0:
                        continue
                    node = self.nodes[node_id]
                    inputs = self._get_node_inputs(node_id, static_results)
                    merged_inputs = {**{k: v for k, v in node.params.items() if k in node.inputs and k not in inputs and v is not None}, **inputs}
                    print(f"GraphExecutor: Merged inputs for node {node_id}: {merged_inputs}")
                    outputs = await node.execute(merged_inputs)  # Will raise NodeValidationError if invalid
                    static_results[node_id] = outputs
            
            # Yield the initial results from the static part of the graph
            print(f"GraphExecutor: Yielding initial static results: {list(static_results.keys())}")
            yield static_results
            
            # This code will only execute when anext() is called again
            print("GraphExecutor: Successfully yielded initial results, continuing...")

            if self._stopped:
                print("GraphExecutor: Execution stopped, returning early")
                return
            
            print("GraphExecutor: Continuing to streaming phase...")

            print(f"GraphExecutor: Found {len(streaming_sources)} streaming sources: {streaming_sources}")
            
            # If there are no streaming sources, we are done
            if not streaming_sources:
                print("GraphExecutor: No streaming sources found, ending stream")
                return
        except Exception as e:
            print(f"GraphExecutor: Exception in static execution or yield: {e}")
            import traceback
            traceback.print_exc()
            raise

        try:
            # Start the streaming sources and their pipelines
            print("GraphExecutor: Starting streaming sources...")
            final_results_queue: asyncio.Queue[Dict[int, Any]] = asyncio.Queue()
            self.streaming_tasks = []
            for source_id in streaming_sources:
                print(f"GraphExecutor: Creating task for streaming source {source_id}")
                task = asyncio.create_task(self._run_streaming_source(source_id, static_results.copy(), final_results_queue))
                self.streaming_tasks.append(task)
                
            print(f"GraphExecutor: Created {len(self.streaming_tasks)} streaming tasks")
            
            # Main loop to pull from the queue and yield to the websocket
            print("GraphExecutor: Starting main streaming loop")
            while any(not task.done() for task in self.streaming_tasks) or final_results_queue.qsize() > 0:
                if self._stopped:
                    break
                try:
                    final_result = await asyncio.wait_for(final_results_queue.get(), timeout=0.1)
                    print(f"GraphExecutor: Got streaming result: {list(final_result.keys())}")
                    yield final_result
                except asyncio.TimeoutError:
                    continue  # Removed self._stopped check here, already at top
            
            print("GraphExecutor: Streaming loop finished, cleaning up...")
            # Clean up any remaining tasks
            results = await asyncio.gather(*self.streaming_tasks, return_exceptions=True)
            exceptions = [r for r in results if isinstance(r, Exception)]
            if exceptions:
                print(f"GraphExecutor: Exception in streaming task: {exceptions[0]}")
                raise exceptions[0]

            for task in self.streaming_tasks:
                if not task.done():
                    task.cancel()
            await asyncio.gather(*self.streaming_tasks, return_exceptions=True)
            self.streaming_tasks = []
            print("GraphExecutor: Streaming cleanup complete")
        except Exception as e:
            print(f"GraphExecutor: Exception in streaming phase: {e}")
            import traceback
            traceback.print_exc()
            raise

    def force_stop(self):
        """Single entrypoint to immediately kill all execution (batch/stream/mixed). Idempotent."""
        print(f"STOP_TRACE: GraphExecutor.force_stop called, already stopped: {self._is_force_stopped}")
        if self._is_force_stopped:
            return  # Idempotent
        self._is_force_stopped = True
        self._stopped = True

        # Immediately force stop all nodes (batch and stream)
        for node_id, node in self.nodes.items():
            print(f"STOP_TRACE: Calling force_stop on node {node_id} ({type(node).__name__})")
            node.force_stop()

        # Cancel all tasks immediately without awaiting or timeout
        if self.streaming_tasks:
            print(f"GraphExecutor: Cancelling {len(self.streaming_tasks)} streaming tasks")
            for task in self.streaming_tasks:
                if not task.done():
                    task.cancel()
            self.streaming_tasks = []  # Clear list immediately

        print("STOP_TRACE: Force stop completed in GraphExecutor")

    async def stop(self):
        print("STOP_TRACE: GraphExecutor.stop called")
        self.force_stop()

    def _get_node_inputs(self, node_id: int, results: Dict[int, Any]) -> Dict[str, Any]:
        inputs: Dict[str, Any] = {}
        # Derive inputs solely from the link table to avoid index/weight ambiguity
        for link in self.graph.get('links', []) or []:
            s_link: SerialisedLink = link
            if s_link['target_id'] != node_id:
                continue
            pred_id = s_link['origin_id']
            output_slot = s_link['origin_slot']
            input_slot = s_link['target_slot']
            pred_node = self.nodes.get(pred_id)
            if pred_node is None:
                continue
            pred_outputs: List[str] = self.output_names.get(pred_id, [str(k) for k in pred_node.outputs.keys()])
            if output_slot >= len(pred_outputs):
                continue

            output_key = pred_outputs[output_slot]
            if pred_id not in results or output_key not in results[pred_id]:
                continue
            value = results[pred_id][output_key]
            
            node_inputs: List[str] = self.input_names.get(node_id, [str(k) for k in self.nodes[node_id].inputs.keys()])
            if input_slot < len(node_inputs):
                input_key = node_inputs[input_slot]
                inputs[input_key] = value
        return inputs

    def set_progress_callback(self, callback: Callable[[int, float, str], None]) -> None:
        """Set a progress callback function."""
        self._progress_callback = callback
        for node in self.nodes.values():
            node.set_progress_callback(callback)

# ---- rustworkx helper shims with precise typing to satisfy the type checker ----
def _rx_topo(dag: Any) -> List[int]:
    return list(rx.topological_sort(dag))  # type: ignore[attr-defined]

def _rx_desc(dag: Any, idx: int) -> Set[int]:
    return rx.descendants(dag, idx)  # type: ignore[attr-defined]

def _rx_is_dag(dag: Any) -> bool:
    return rx.is_directed_acyclic_graph(dag)  # type: ignore[attr-defined]

