import pytest
import asyncio
import os
from unittest.mock import patch, AsyncMock, MagicMock
from core.graph_executor import GraphExecutor
from core.node_registry import NODE_REGISTRY

@pytest.mark.asyncio
@patch("ollama.AsyncClient")
async def test_ollama_integration(mock_ollama_client):
    # Mock model list for selector (now for chat)
    with patch("httpx.AsyncClient.get") as mock_get:
        mock_get.return_value = AsyncMock()
        mock_get.return_value.json.return_value = {"models": [{"name": "test_model:latest"}]}
        mock_get.return_value.raise_for_status.return_value = None
        
        # Mock chat response
        mock_chat = AsyncMock(return_value={"message": {"role": "assistant", "content": "Hello from Ollama"}})
        mock_ollama_client.return_value.chat = mock_chat
        
        # Define graph: OllamaChat (with selected_model)
        graph_data = {
            "nodes": [
                {"id": 1, "type": "OllamaChatNode", "properties": {"stream": False, "selected_model": "test_model:latest"}},
                {"id": 2, "type": "TextInputNode", "properties": {"text": "Hello"}}
            ],
            "links": [
                [0, 2, 0, 1, 1]   # text.text -> chat.prompt (slot 1)
            ]
        }
        
        executor = GraphExecutor(graph_data, NODE_REGISTRY)
        stream_gen = executor.stream()
        
        initial_results = await anext(stream_gen)
        chat_results = await anext(stream_gen)
        
        results = {**initial_results, **chat_results}
        
        assert 1 in results
        assert results[1]["message"]["content"] == "Hello from Ollama"
        assert results[1]["message"]["role"] == "assistant"
        assert isinstance(results[1].get("metrics", {}), dict)
        
        # Verify chat was called with expected args
        mock_chat.assert_called_once()
        call_args = mock_chat.call_args.kwargs
        assert call_args["model"] == "test_model:latest"
        assert call_args["messages"][0]["role"] == "user"
        assert call_args["messages"][0]["content"] == "Hello"
        assert not call_args["stream"]

@pytest.mark.asyncio
@patch("ollama.AsyncClient")
@patch("httpx.AsyncClient")
async def test_ollama_streaming_integration(mock_httpx_client, mock_ollama_client):
    # Mock model list for selector (now for chat)
    httpx_response = MagicMock()
    httpx_response.json.return_value = {"models": [{"name": "test_model:latest"}]}
    httpx_response.raise_for_status.return_value = None
    httpx_client_instance = MagicMock()
    httpx_client_instance.get = AsyncMock(return_value=httpx_response)
    # Async context manager behavior
    mock_httpx_client.return_value.__aenter__.return_value = httpx_client_instance

    # Mock chat stream for quick completion
    mock_response = {
        "message": {"role": "assistant", "content": "{}"},
        "total_duration": 50,
        "eval_count": 5
    }
    mock_chat = AsyncMock(return_value=mock_response)
    mock_ollama_client.return_value.chat = mock_chat

    # Define graph: OllamaChat (with selected_model, streaming) &lt;- TextInput
    graph_data = {
        "nodes": [
            {"id": 1, "type": "OllamaChatNode", "properties": {"stream": False, "json_mode": True, "selected_model": "test_model:latest"}},
            {"id": 2, "type": "TextInputNode", "properties": {"text": "Output empty JSON"}}
        ],
        "links": [
            [0, 2, 0, 1, 1]  # text -> prompt (slot 1)
        ]
    }

    executor = GraphExecutor(graph_data, NODE_REGISTRY)
    stream_gen = executor.stream()

    initial_results = await anext(stream_gen)
    chat_results = await anext(stream_gen)
    results = {**initial_results, **chat_results}

    assert 1 in results
    assert results[1]["message"]["content"] == {}
    assert "total_duration" in results[1].get("metrics", {})
    assert "eval_count" in results[1].get("metrics", {})

    with pytest.raises(StopAsyncIteration):
        await anext(stream_gen)


@pytest.mark.asyncio
@patch("ollama.AsyncClient")
@patch("httpx.AsyncClient")
async def test_web_search_tool_with_ollama_integration(mock_httpx_client, mock_ollama_client):
    # Mock model list for chat
    httpx_response = MagicMock()
    httpx_response.json.return_value = {"models": [{"name": "llama3.2:latest"}]}
    httpx_response.raise_for_status.return_value = None
    httpx_client_instance = MagicMock()
    httpx_client_instance.get = AsyncMock(return_value=httpx_response)
    mock_httpx_client.return_value.__aenter__.return_value = httpx_client_instance
    mock_httpx_client.return_value.__aexit__ = AsyncMock(return_value=False)

    # Mock the tool orchestration chat calls
    mock_responses = [
        {"message": {"role": "assistant", "tool_calls": [{"function": {"name": "web_search", "arguments": {"query": "artificial intelligence news"}}}]}},
        {"message": {"role": "assistant", "content": "Summary of AI news: Recent advancements include..." }}
    ]

    mock_ollama_client.return_value.chat = AsyncMock(side_effect=mock_responses)

    """Test web search tool integration with OllamaChatNode."""
    # Skip if no API key is available
    if not os.getenv("TAVILY_API_KEY"):
        pytest.skip("TAVILY_API_KEY not set, skipping integration test")

    # Define graph: WebSearchToolNode -> OllamaChatNode (with selected_model)
    graph_data = {
        "nodes": [
            {"id": 2, "type": "WebSearchToolNode", "properties": {
                "provider": "tavily",
                "default_k": 2,
                "time_range": "month",
                "lang": "en",
                "require_api_key": True
            }},
            {"id": 3, "type": "OllamaChatNode", "properties": {
                "stream": False,
                "max_tool_iters": 1,  # Limit iterations for test
                "tool_timeout_s": 15,
                "selected_model": "llama3.2:latest"
            }},
            {"id": 4, "type": "TextInputNode", "properties": {
                "text": "Search for the latest news about artificial intelligence and summarize the key findings."
            }}
        ],
        "links": [
            [0, 2, 0, 3, 4],  # web_search_tool.tool -> chat.tool (slot 4)
            [0, 4, 0, 3, 1]   # text.text -> chat.prompt (slot 1)
        ]
    }

    executor = GraphExecutor(graph_data, NODE_REGISTRY)

    # Execute the graph
    results = await executor.execute()

    # Verify results
    assert 3 in results  # OllamaChatNode results
    chat_result = results[3]

    assert "message" in chat_result
    assert "metrics" in chat_result

    message = chat_result["message"]
    assert "role" in message
    assert message["role"] == "assistant"
    assert "content" in message

    # The response should contain some content (either from tool use or direct response)
    assert isinstance(message["content"], str)
    assert len(message["content"]) > 0

    # Check that metrics are present
    metrics = chat_result["metrics"]
    assert isinstance(metrics, dict)

    # Note: In a real scenario, the model might use the web search tool
    # and tool_calls would be present, but for this test we just verify
    # the integration works without errors


@pytest.mark.asyncio
@patch("ollama.AsyncClient")
@patch("httpx.AsyncClient")
async def test_web_search_tool_streaming_with_ollama(mock_httpx_client, mock_ollama_client):
    # Mock model list for chat
    httpx_response = MagicMock()
    httpx_response.json.return_value = {"models": [{"name": "llama3.2:latest"}]}
    httpx_response.raise_for_status.return_value = None
    httpx_client_instance = MagicMock()
    httpx_client_instance.get = AsyncMock(return_value=httpx_response)
    mock_httpx_client.return_value.__aenter__.return_value = httpx_client_instance
    mock_httpx_client.return_value.__aexit__ = AsyncMock(return_value=False)

    # Mock the tool orchestration and streaming
    mock_responses = [
        {"message": {"role": "assistant", "tool_calls": [{"function": {"name": "web_search", "arguments": {"query": "Bitcoin price"}}}]}},
        {"message": {"role": "assistant", "content": "Bitcoin is currently priced at approximately $60,000."}, "total_duration": 100, "eval_count": 10}
    ]

    mock_ollama_client.return_value.chat = AsyncMock(side_effect=mock_responses)

    """Test web search tool integration with streaming OllamaChatNode."""
    # Skip if no API key is available
    if not os.getenv("TAVILY_API_KEY"):
        pytest.skip("TAVILY_API_KEY not set, skipping integration test")

    # Define graph: WebSearchToolNode -> OllamaChatNode (streaming, with selected_model)
    graph_data = {
        "nodes": [
            {"id": 2, "type": "WebSearchToolNode", "properties": {
                "provider": "tavily",
                "default_k": 1,
                "time_range": "week",
                "lang": "en",
                "require_api_key": True
            }},
            {"id": 3, "type": "OllamaChatNode", "properties": {
                "stream": False,
                "max_tool_iters": 1,
                "tool_timeout_s": 10,
                "selected_model": "llama3.2:latest"
            }},
            {"id": 4, "type": "TextInputNode", "properties": {
                "text": "What is the current price of Bitcoin?"
            }}
        ],
        "links": [
            [0, 2, 0, 3, 4],  # web_search_tool.tool -> chat.tool (slot 4)
            [0, 4, 0, 3, 1]   # text.text -> chat.prompt (slot 1)
        ]
    }

    executor = GraphExecutor(graph_data, NODE_REGISTRY)
    stream_gen = executor.stream()

    # Get initial results
    initial_results = await anext(stream_gen)

    # Collect all streaming results
    all_results = dict(initial_results)
    try:
        while True:
            chunk = await anext(stream_gen)
            all_results.update(chunk)
    except StopAsyncIteration:
        pass

    # Verify we got results from the chat node
    assert 3 in all_results
    chat_result = all_results[3]

    assert "message" in chat_result
    assert "metrics" in chat_result
    assert "done" in chat_result
    assert chat_result["done"] is True

    message = chat_result["message"]
    assert "role" in message
    assert message["role"] == "assistant"
    assert "content" in message

    # Content should be non-empty
    assert isinstance(message["content"], str)
    assert len(message["content"]) > 0
