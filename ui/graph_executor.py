import networkx as nx
from typing import Dict, Any, List
from nodes.base_node import BaseNode

class GraphExecutor:
    def __init__(self, graph: Dict[str, Any], node_registry: Dict[str, type]):
        self.graph = graph
        self.node_registry = node_registry
        self.nodes: Dict[int, BaseNode] = {}  # Node IDs are integers in LiteGraph
        self.dag = nx.DiGraph()
        self._build_graph()

    def _build_graph(self):
        # Process nodes
        for node_data in self.graph.get('nodes', []):
            node_id = node_data['id']
            node_type = node_data['type']
            if node_type not in self.node_registry:
                raise ValueError(f"Unknown node type: {node_type}")
            properties = node_data.get('properties', {})
            self.nodes[node_id] = self.node_registry[node_type](str(node_id), properties)
            self.dag.add_node(node_id)

        # Process links and build DAG edges (node to node)
        for link in self.graph.get('links', []):
            # link format: [id, from_node, from_slot, to_node, to_slot, type?]
            from_id = link[1]
            to_id = link[3]
            self.dag.add_edge(from_id, to_id)

        if not nx.is_directed_acyclic_graph(self.dag):
            raise ValueError("Graph contains cycles")

    def execute(self) -> Dict[str, Any]:
        results: Dict[int, Dict[str, Any]] = {}
        for node_id in nx.topological_sort(self.dag):
            node = self.nodes[node_id]
            inputs: Dict[str, Any] = {}

            # Find incoming links
            for link in self.graph.get('links', []):
                if link[3] == node_id:  # to_node == node_id
                    pred_id = link[1]
                    output_slot = link[2]
                    input_slot = link[4]

                    pred_node = self.nodes[pred_id]
                    if output_slot < len(pred_node.outputs):
                        output_key = pred_node.outputs[output_slot]
                        if pred_id in results and output_key in results[pred_id]:
                            value = results[pred_id][output_key]
                            if input_slot < len(node.inputs):
                                input_key = node.inputs[input_slot]
                                inputs[input_key] = value
                            else:
                                raise ValueError(f"Invalid input slot {input_slot} for node {node_id}")
                        else:
                            raise ValueError(f"Missing output {output_key} from predecessor {pred_id}")
                    else:
                        raise ValueError(f"Invalid output slot {output_slot} for predecessor {pred_id}")

            # Validate all required inputs are present
            if not node.validate_inputs(inputs):
                raise ValueError(f"Missing inputs for node {node_id}: {set(node.inputs) - set(inputs.keys())}")

            outputs = node.execute(inputs)
            results[node_id] = outputs

        return results 