
import networkx as nx
from typing import Dict, Any, List
from nodes.base_node import BaseNode
from nodes.flow_control_nodes import ForEachNode

class GraphExecutor:
    def __init__(self, graph: Dict[str, Any], node_registry: Dict[str, type]):
        self.graph = graph
        self.node_registry = node_registry
        self.nodes: Dict[int, BaseNode] = {}
        self.dag = nx.DiGraph()
        self._build_graph()

    def _build_graph(self):
        for node_data in self.graph.get('nodes', []):
            node_id = node_data['id']
            node_type = node_data['type']
            if node_type not in self.node_registry:
                raise ValueError(f"Unknown node type: {node_type}")
            properties = node_data.get('properties', {})
            self.nodes[node_id] = self.node_registry[node_type](str(node_id), properties)
            self.dag.add_node(node_id)

        for link in self.graph.get('links', []):
            from_id, to_id = link[1], link[3]
            self.dag.add_edge(from_id, to_id)

        if not nx.is_directed_acyclic_graph(self.dag):
            raise ValueError("Graph contains cycles")

    async def execute(self) -> Dict[str, Any]:
        results: Dict[int, Dict[str, Any]] = {}
        sorted_nodes = list(nx.topological_sort(self.dag))

        for node_id in sorted_nodes:
            node = self.nodes[node_id]
            
            if isinstance(node, ForEachNode):
                # Special handling for ForEachNode
                await self._execute_foreach_subgraph(node, results)
            else:
                # Standard node execution
                inputs = self._get_node_inputs(node_id, results)
                if not node.validate_inputs(inputs):
                    raise ValueError(f"Missing inputs for node {node_id}: {set(node.inputs) - set(inputs.keys())}")
                
                outputs = await node.execute(inputs)
                results[node_id] = outputs
        
        return results

    async def _execute_foreach_subgraph(self, foreach_node: ForEachNode, results: Dict[str, Any]):
        inputs = self._get_node_inputs(foreach_node.id, results)
        item_list = inputs.get("list", [])
        
        # Identify the subgraph connected to the ForEachNode's "item" output
        subgraph_nodes = list(nx.dfs_preorder_nodes(self.dag, source=foreach_node.id))
        subgraph_nodes.remove(foreach_node.id) # Exclude the ForEachNode itself

        foreach_results = []
        for item in item_list:
            # For each item, run the subgraph
            subgraph_results = {}
            # Provide the current item as an output of the ForEachNode
            results[foreach_node.id] = {"item": item}
            
            for sub_node_id in subgraph_nodes:
                sub_node = self.nodes[sub_node_id]
                sub_inputs = self._get_node_inputs(sub_node_id, {**results, **subgraph_results})
                
                if not sub_node.validate_inputs(sub_inputs):
                     raise ValueError(f"Missing inputs for node {sub_node_id} in ForEach loop: {set(sub_node.inputs) - set(sub_inputs.keys())}")

                sub_outputs = await sub_node.execute(sub_inputs)
                subgraph_results[sub_node_id] = sub_outputs
            
            # You might want to collect results from the subgraph execution
            # For now, we'll just store the final result of the last node in the subgraph
            if subgraph_nodes:
                last_node_id = subgraph_nodes[-1]
                foreach_results.append(subgraph_results.get(last_node_id, {}))

        # Store the collected results from all iterations
        results[foreach_node.id] = {"results": foreach_results}


    def _get_node_inputs(self, node_id: int, results: Dict[int, Any]) -> Dict[str, Any]:
        inputs: Dict[str, Any] = {}
        for pred_id in self.dag.predecessors(node_id):
            # Find the specific link to get slot information
            for link in self.graph.get('links', []):
                if link[1] == pred_id and link[3] == node_id:
                    output_slot = link[2]
                    input_slot = link[4]
                    
                    pred_node = self.nodes[pred_id]
                    if output_slot < len(pred_node.outputs):
                        output_key = pred_node.outputs[output_slot]
                        if pred_id in results and output_key in results[pred_id]:
                            value = results[pred_id][output_key]
                            if input_slot < len(self.nodes[node_id].inputs):
                                input_key = self.nodes[node_id].inputs[input_slot]
                                inputs[input_key] = value
        return inputs 