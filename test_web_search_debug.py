#!/usr/bin/env python3
import asyncio
import json
from core.graph_executor import GraphExecutor
from core.node_registry import NODE_REGISTRY

async def debug_web_search_graph():
    # Load the graph
    with open('test-web-search.json', 'r') as f:
        graph_data = json.load(f)

    print("Graph data loaded for web search test")

    # Create executor
    executor = GraphExecutor(graph_data, NODE_REGISTRY)

    print(f"GraphExecutor created, is_streaming={executor.is_streaming}")

    # Execute the graph
    try:
        if executor.is_streaming:
            print("Streaming graph detected, using stream() method")
            stream_gen = executor.stream()
            async for result in stream_gen:
                print(f"Stream result: {list(result.keys())}")
                # Look for OllamaChatNode results (node 2)
                if 2 in result:
                    message = result[2].get('message', {})
                    print(f"OllamaChatNode message: {message}")
                    tool_calls = message.get('tool_calls', [])
                    if tool_calls:
                        print(f"Tool calls made: {tool_calls}")
                    else:
                        print("No tool calls made")
                    break  # Just get the first result for debugging
        else:
            results = await executor.execute()
            print(f"Execution results: {results}")

    except Exception as e:
        print(f"Error executing graph: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(debug_web_search_graph())

