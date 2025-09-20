import pytest
import asyncio
from unittest.mock import patch, AsyncMock
from core.graph_executor import GraphExecutor
from core.node_registry import NODE_REGISTRY

@pytest.mark.asyncio
@patch("ollama.AsyncClient")
async def test_ollama_integration(mock_ollama_client):
    # Mock model list for selector
    with patch("httpx.AsyncClient.get") as mock_get:
        mock_get.return_value = AsyncMock()
        mock_get.return_value.json.return_value = {"models": [{"name": "test_model:latest"}]}
        mock_get.return_value.raise_for_status.return_value = None
        
        # Mock chat response
        mock_chat = AsyncMock(return_value={"message": {"content": "Hello from Ollama"}})
        mock_ollama_client.return_value.chat = mock_chat
        
        # Define graph: ModelSelector -> OllamaChat
        graph_data = {
            "nodes": [
                {"id": 1, "type": "OllamaModelSelectorNode", "properties": {"selected": "test_model:latest"}},
                {"id": 2, "type": "OllamaChatNode", "properties": {"stream": False}},
                {"id": 3, "type": "TextInputNode", "properties": {"text": "Hello"}}
            ],
            "links": [
                [0, 1, 0, 2, 0],  # selector.host -> chat.host
                [0, 1, 1, 2, 1],  # selector.model -> chat.model
                [0, 3, 0, 2, 3]   # text.text -> chat.prompt (slot 3)
            ]
        }
        
        executor = GraphExecutor(graph_data, NODE_REGISTRY)
        stream_gen = executor.stream()
        
        initial_results = await anext(stream_gen)
        chat_results = await anext(stream_gen)
        
        results = {**initial_results, **chat_results}
        
        assert 2 in results
        assert results[2]["message"]["content"] == "Hello from Ollama"
        assert isinstance(results[2].get("metrics", {}), dict)
        
        # Verify chat was called with expected args
        mock_chat.assert_called_once()
        call_args = mock_chat.call_args.kwargs
        assert call_args["model"] == "test_model:latest"
        assert call_args["messages"][0]["role"] == "user"
        assert call_args["messages"][0]["content"] == "Hello"
        assert not call_args["stream"]

@pytest.mark.asyncio
@patch("ollama.AsyncClient")
async def test_ollama_streaming_integration(mock_ollama_client):
    # Mock chat stream for quick completion
    async def mock_stream():
        yield {"message": {"content": "{}"}}
        yield {"done": True, "total_duration": 50, "eval_count": 5}

    mock_chat = AsyncMock(return_value=mock_stream())
    mock_ollama_client.return_value.chat = mock_chat

    # Define graph: TextInput -> OllamaChat (streaming)
    graph_data = {
        "nodes": [
            {"id": 1, "type": "OllamaChatNode", "properties": {"stream": True, "json_mode": True}},
            {"id": 2, "type": "TextInputNode", "properties": {"text": "Output empty JSON"}}
        ],
        "links": [
            [0, 2, 0, 1, 3]  # text -> prompt
        ]
    }

    executor = GraphExecutor(graph_data, NODE_REGISTRY)
    stream_gen = executor.stream()

    initial_results = await anext(stream_gen)
    stream_tick1 = await anext(stream_gen)
    final_tick = await anext(stream_gen)

    results = {**initial_results, **stream_tick1, **final_tick}

    assert 1 in results
    assert results[1]["message"]["content"] == "{}"
    assert "total_duration" in results[1].get("metrics", {})
    assert "eval_count" in results[1].get("metrics", {})

    with pytest.raises(StopAsyncIteration):
        await anext(stream_gen)
