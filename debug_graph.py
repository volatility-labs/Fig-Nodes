#!/usr/bin/env python3
import asyncio
import json
from core.graph_executor import GraphExecutor
from core.node_registry import NODE_REGISTRY

async def debug_polygon_graph():
    # Load the graph
    with open('polygon-test-graph.json', 'r') as f:
        graph_data = json.load(f)

    print("Graph data loaded:")
    print(json.dumps(graph_data, indent=2))

    # Create executor
    executor = GraphExecutor(graph_data, NODE_REGISTRY)

    print(f"GraphExecutor created, is_streaming={executor.is_streaming}")

    # Execute the graph
    try:
        results = await executor.execute()
        print(f"Execution results: {results}")

        # Check if node 1 (PolygonCustomBarsNode) has results
        if 1 in results:
            print(f"Node 1 results: {results[1]}")
            if 'ohlcv' in results[1]:
                ohlcv_data = results[1]['ohlcv']
                print(f"OHLCV data type: {type(ohlcv_data)}")
                print(f"OHLCV data: {ohlcv_data}")
        else:
            print("Node 1 not in results")

        # Check if node 5 (LoggingNode) has results
        if 5 in results:
            print(f"Node 5 results: {results[5]}")
        else:
            print("Node 5 not in results")

    except Exception as e:
        print(f"Error executing graph: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(debug_polygon_graph())
