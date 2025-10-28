#!/usr/bin/env python3
"""Test script to verify prevDay data usage in PolygonUniverse node."""

import asyncio
import json

from core.graph_executor import GraphExecutor
from core.node_registry import NODE_REGISTRY


async def main():
    # Load the graph
    with open("testing_artifacts/debug-graph-polygon.json") as f:
        graph_data = json.load(f)

    # Create executor
    executor = GraphExecutor(graph_data, NODE_REGISTRY)

    # Execute the graph
    print("Starting graph execution...")
    results = await executor.execute()

    print(f"\nExecution completed. Results for {len(results)} nodes:")
    for node_id, result in results.items():
        if "symbols" in result:
            print(f"Node {node_id}: {len(result['symbols'])} symbols")
        elif "ohlcv_bundle" in result:
            print(f"Node {node_id}: {len(result['ohlcv_bundle'])} symbols in bundle")
        else:
            print(f"Node {node_id}: {list(result.keys())}")


if __name__ == "__main__":
    asyncio.run(main())
