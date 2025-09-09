import networkx as nx
from typing import Dict, Any, List, AsyncGenerator
from nodes.base.base_node import BaseNode
from nodes.impl.flow_control_nodes import ForEachNode
import asyncio
from nodes.base.streaming_node import StreamingNode
from collections import defaultdict

class GraphExecutor:
    def __init__(self, graph: Dict[str, Any], node_registry: Dict[str, type]):
        self.graph = graph
        self.node_registry = node_registry
        self.nodes: Dict[int, BaseNode] = {}
        self.input_names: Dict[int, List[str]] = {}
        self.output_names: Dict[int, List[str]] = {}
        self.dag = nx.DiGraph()
        self.is_streaming = False
        self.streaming_tasks: List[asyncio.Task] = []
        self._stopped = False
        self._build_graph()

    def _build_graph(self):
        for node_data in self.graph.get('nodes', []):
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
            self.dag.add_node(node_id)

        for link in self.graph.get('links', []):
            from_id, to_id = link[1], link[3]
            self.dag.add_edge(from_id, to_id)

        if not nx.is_directed_acyclic_graph(self.dag):
            raise ValueError("Graph contains cycles")
        
        self.is_streaming = any(isinstance(node, StreamingNode) for node in self.nodes.values())

    async def execute(self) -> Dict[str, Any]:
        if self.is_streaming:
            raise RuntimeError("Cannot use execute() on a streaming graph. Use stream() instead.")

        results: Dict[int, Dict[str, Any]] = {}
        sorted_nodes = list(nx.topological_sort(self.dag))
        executed_nodes = set()

        for node_id in sorted_nodes:
            if node_id in executed_nodes:
                continue
            if self.dag.in_degree(node_id) == 0 and self.dag.out_degree(node_id) == 0:
                continue
            node = self.nodes[node_id]
            if isinstance(node, ForEachNode):
                await self._execute_foreach_subgraph(node, results)
                subgraph_nodes = list(nx.dfs_preorder_nodes(self.dag, source=node_id))
                executed_nodes.update(subgraph_nodes)
            else:
                inputs = self._get_node_inputs(node_id, results)
                merged_inputs = {**{k: node.params.get(k) for k in node.inputs if k not in inputs}, **inputs}
                if not node.validate_inputs(merged_inputs):
                    continue
                outputs = await node.execute(merged_inputs)
                results[node_id] = outputs
        
        return results

    async def _execute_subgraph_for_tick(self, subgraph_nodes: List[int], context: Dict[str, Any]) -> Dict[str, Any]:
        tick_results = {}
        for sub_node_id in subgraph_nodes:
            # Important: The context for the current tick can be updated by previous nodes in the same tick
            current_context = {**context, **tick_results}
            sub_node = self.nodes[sub_node_id]
            sub_inputs = self._get_node_inputs(sub_node_id, current_context)
            merged_inputs = {**{k: sub_node.params.get(k) for k in sub_node.inputs if k not in sub_inputs}, **sub_inputs}
            
            if not sub_node.validate_inputs(merged_inputs):
                # TODO: Handle errors more gracefully
                print(f"Skipping node {sub_node_id} due to missing inputs in stream.")
                continue
                
            sub_outputs = await sub_node.execute(merged_inputs)
            tick_results[sub_node_id] = sub_outputs
        return tick_results

    async def _run_streaming_source(self, source_id: int, initial_results: Dict[int, Any], result_queue: asyncio.Queue):
        source_node = self.nodes[source_id]
        
        # Define the subgraph that depends on this source
        downstream_nodes = list(nx.dfs_preorder_nodes(self.dag, source=source_id))
        downstream_nodes.remove(source_id)

        source_inputs = self._get_node_inputs(source_id, initial_results)
        
        async for source_output in source_node.start(source_inputs):
            # The context for this tick includes all initial results plus the new output from the stream source
            tick_context = {**initial_results, source_id: source_output}
            
            # Execute the downstream nodes for this tick
            subgraph_results = await self._execute_subgraph_for_tick(downstream_nodes, tick_context)
            
            # Combine all results for this tick and put them in the queue
            final_tick_results = {source_id: source_output, **subgraph_results}
            await result_queue.put(final_tick_results)

    async def stream(self) -> AsyncGenerator[Dict[str, Any], None]:
        static_results: Dict[int, Dict[str, Any]] = {}
        
        streaming_pipeline_nodes = set()
        streaming_sources = []
        for node_id in self.dag.nodes:
            if isinstance(self.nodes[node_id], StreamingNode) and self.dag.degree(node_id) > 0:
                streaming_sources.append(node_id)
                streaming_pipeline_nodes.add(node_id)
                for descendant in nx.descendants(self.dag, node_id):
                    streaming_pipeline_nodes.add(descendant)

        # First, execute all nodes that are NOT part of any streaming pipeline
        sorted_nodes = list(nx.topological_sort(self.dag))
        for node_id in sorted_nodes:
            if node_id not in streaming_pipeline_nodes:
                if self.dag.in_degree(node_id) == 0 and self.dag.out_degree(node_id) == 0:
                    continue
                node = self.nodes[node_id]
                inputs = self._get_node_inputs(node_id, static_results)
                merged_inputs = {**{k: node.params.get(k) for k in node.inputs if k not in inputs}, **inputs}
                if not node.validate_inputs(merged_inputs):
                    continue
                outputs = await node.execute(merged_inputs)
                static_results[node_id] = outputs
        
        # Yield the initial results from the static part of the graph
        yield static_results

        if self._stopped:
            return

        # If there are no streaming sources, we are done
        if not streaming_sources:
            return

        # Start the streaming sources and their pipelines
        final_results_queue = asyncio.Queue()
        self.streaming_tasks = []
        for source_id in streaming_sources:
            task = asyncio.create_task(self._run_streaming_source(source_id, static_results.copy(), final_results_queue))
            self.streaming_tasks.append(task)
            
        # Main loop to pull from the queue and yield to the websocket
        while any(not task.done() for task in self.streaming_tasks) or final_results_queue.qsize() > 0:
            try:
                final_result = await asyncio.wait_for(final_results_queue.get(), timeout=1.0)
                yield final_result
            except asyncio.TimeoutError:
                if self._stopped:
                    break
                continue
        
        # Clean up any remaining tasks
        results = await asyncio.gather(*self.streaming_tasks, return_exceptions=True)
        exceptions = [r for r in results if isinstance(r, Exception)]
        if exceptions:
            raise exceptions[0]

        for task in self.streaming_tasks:
            if not task.done():
                task.cancel()
        await asyncio.gather(*self.streaming_tasks, return_exceptions=True)
        self.streaming_tasks = []

    async def stop(self):
        self._stopped = True
        for task in self.streaming_tasks:
            if not task.done():
                task.cancel()
        for node in self.nodes.values():
            if isinstance(node, StreamingNode):
                node.stop()
        if self.streaming_tasks:
            await asyncio.gather(*self.streaming_tasks, return_exceptions=True)
        self.streaming_tasks = []

    async def _execute_foreach_subgraph(self, foreach_node: ForEachNode, results: Dict[str, Any]):
        inputs = self._get_node_inputs(foreach_node.id, results)
        merged_inputs = {**{k: foreach_node.params.get(k) for k in foreach_node.inputs if k not in inputs}, **inputs}
        item_list = merged_inputs.get("list") or []
        
        subgraph_nodes = list(nx.dfs_preorder_nodes(self.dag, source=foreach_node.id))
        subgraph_nodes.remove(foreach_node.id)

        foreach_results = []
        for item in item_list:
            subgraph_context = {**results, foreach_node.id: {"item": item}}
            subgraph_results = await self._execute_subgraph_for_tick(subgraph_nodes, subgraph_context)
            
            if subgraph_nodes:
                last_node_id = subgraph_nodes[-1]
                foreach_results.append(subgraph_results.get(last_node_id, {}))

        results[foreach_node.id] = {"results": foreach_results}

    def _get_node_inputs(self, node_id: int, results: Dict[int, Any]) -> Dict[str, Any]:
        inputs: Dict[str, Any] = {}
        for pred_id in self.dag.predecessors(node_id):
            for link in self.graph.get('links', []):
                if link[1] == pred_id and link[3] == node_id:
                    output_slot, input_slot = link[2], link[4]
                    pred_node = self.nodes[pred_id]
                    pred_outputs = self.output_names.get(pred_id, list(pred_node.outputs.keys()))
                    if output_slot < len(pred_outputs):
                        output_key = pred_outputs[output_slot]
                        if pred_id in results and output_key in results[pred_id]:
                            value = results[pred_id][output_key]
                            node_inputs = self.input_names.get(node_id, list(self.nodes[node_id].inputs.keys()))
                            if input_slot < len(node_inputs):
                                input_key = node_inputs[input_slot]
                                inputs[input_key] = value
        return inputs
