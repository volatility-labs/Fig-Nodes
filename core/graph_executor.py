import rustworkx as rx
from typing import Dict, Any, List, Type, Set, Optional
from nodes.base.base_node import Base
import asyncio
from core.api_key_vault import APIKeyVault
from core.types_registry import NodeExecutionError, SerialisableGraph, SerialisedLink, ProgressCallback
import logging

logger = logging.getLogger(__name__)

NodeId = int
ExecutionResults = Dict[NodeId, Dict[str, Any]]

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
        self._stopped: bool = False
        self._is_force_stopped: bool = False  # For idempotency
        self._progress_callback: Optional[ProgressCallback] = None
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

    # Execute the graph 
    async def execute(self) -> ExecutionResults:
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
            except NodeExecutionError as e: 
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


    def force_stop(self):
        """Single entrypoint to immediately kill all execution. Idempotent."""
        print(f"STOP_TRACE: GraphExecutor.force_stop called, already stopped: {self._is_force_stopped}")
        if self._is_force_stopped:
            return  # Idempotent
        self._is_force_stopped = True
        self._stopped = True

        # Immediately force stop all nodes
        for node_id, node in self.nodes.items():
            print(f"STOP_TRACE: Calling force_stop on node {node_id} ({type(node).__name__})")
            node.force_stop()

        print("STOP_TRACE: Force stop completed in GraphExecutor")

    async def stop(self):
        print("STOP_TRACE: GraphExecutor.stop called")
        self.force_stop()

    def _get_node_inputs(self, node_id: int, results: Dict[int, Dict[str, Any]]) -> Dict[str, Any]:
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

    def set_progress_callback(self, callback: ProgressCallback) -> None:
        """Set a progress callback function."""
        self._progress_callback = callback
        for node in self.nodes.values():
            node.set_progress_callback(callback)

# ---- rustworkx helper shims with precise typing to satisfy the type checker ----
def _rx_topo(dag: Any) -> List[int]:
    return list(rx.topological_sort(dag)) 

def _rx_is_dag(dag: Any) -> bool:
    return rx.is_directed_acyclic_graph(dag)  

