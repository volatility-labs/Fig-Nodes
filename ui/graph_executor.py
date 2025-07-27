import networkx as nx
from typing import Dict, Any, List
from nodes.base_node import BaseNode

class GraphExecutor:
    def __init__(self, graph: Dict[str, Any], node_registry: Dict[str, type]):
        self.graph = graph
        self.node_registry = node_registry
        self.nodes = {}
        self.dag = nx.DiGraph()
        self._build_graph()

    def _build_graph(self):
        for node_id, node_data in self.graph['nodes'].items():
            node_type = node_data['type']
            if node_type not in self.node_registry:
                raise ValueError(f"Unknown node type: {node_type}")
            self.nodes[node_id] = self.node_registry[node_type](node_id, node_data.get('params', {}))
            self.dag.add_node(node_id)
        for conn in self.graph.get('connections', []):
            self.dag.add_edge(conn['from'], conn['to'])
        if not nx.is_directed_acyclic_graph(self.dag):
            raise ValueError("Graph contains cycles")

    def execute(self) -> Dict[str, Any]:
        results = {}
        for node_id in nx.topological_sort(self.dag):
            node = self.nodes[node_id]
            inputs = {input_key: results[pred][input_key] for pred in self.dag.predecessors(node_id) for input_key in node.inputs}
            outputs = node.execute(inputs)
            results[node_id] = outputs
        return results 