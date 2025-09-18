
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import asyncio
from nodes.core.llm.ollama_chat_node import OllamaChatNode
from core.types_registry import LLMChatMessage, LLMChatMetrics

@pytest.fixture
def chat_node():
    return OllamaChatNode(id=1, params={})

@pytest.mark.asyncio
async def test_start_streaming_mode(chat_node):
    chat_node.params["stream"] = True
    inputs = {
        "model": "test_model",
        "messages": [{"role": "user", "content": "Hello"}]
    }
    
    with patch("ollama.AsyncClient") as mock_client:
        mock_stream = AsyncMock()
        mock_stream.__aiter__.return_value = [
            {"message": {"content": "Hi"}},
            {"message": {"content": " there"}},
            {"done": True, "total_duration": 100}  # Final chunk without content to exit loop
        ]
        mock_chat = AsyncMock(return_value=mock_stream)
        mock_client.return_value.chat = mock_chat
        
        gen = chat_node.start(inputs)
        output1 = await anext(gen)
        assert output1["assistant_text"] == "Hi"
        assert not output1["assistant_done"]
        
        output2 = await anext(gen)
        assert output2["assistant_text"] == "Hi there"
        assert not output2["assistant_done"]
        
        output3 = await anext(gen)
        assert output3["assistant_text"] == "Hi there"
        assert not output3["assistant_done"]
        
        output4 = await anext(gen)
        assert output4["assistant_text"] == "Hi there"
        assert output4["assistant_done"]
        assert "total_duration" in output4["metrics"]

@pytest.mark.asyncio
async def test_start_non_streaming_mode(chat_node):
    chat_node.params["stream"] = False
    inputs = {
        "model": "test_model",
        "messages": [{"role": "user", "content": "Hello"}]
    }
    
    with patch("ollama.AsyncClient") as mock_client:
        mock_response = {
            "message": {"content": "Hello back"},
            "total_duration": 100
        }
        mock_chat = AsyncMock(return_value=mock_response)
        mock_client.return_value.chat = mock_chat
        
        gen = chat_node.start(inputs)
        output = await anext(gen)
        assert output["assistant_text"] == "Hello back"
        assert output["assistant_done"]
        assert output["metrics"]["total_duration"] == 100

@pytest.mark.asyncio
async def test_temperature_application(chat_node):
    chat_node.params["temperature"] = 0.5
    inputs = {"model": "test_model", "messages": [{"role": "user", "content": "Hello"}]}
    
    with patch("ollama.AsyncClient") as mock_client:
        mock_chat = AsyncMock(return_value={"message": {"content": "Response"}})
        mock_client.return_value.chat = mock_chat
        
        await chat_node.execute(inputs)
        mock_chat.assert_called_once()
        assert mock_chat.call_args.kwargs["options"]["temperature"] == 0.5

@pytest.mark.asyncio
async def test_think_mode(chat_node):
    chat_node.params["think"] = True
    inputs = {"model": "test_model", "messages": [{"role": "user", "content": "Think"}]}
    
    with patch("ollama.AsyncClient") as mock_client:
        mock_response = {
            "message": {"content": "Final", "thinking": "Thinking step 1\nThinking step 2"}
        }
        mock_chat = AsyncMock(return_value=mock_response)
        mock_client.return_value.chat = mock_chat
        
        result = await chat_node.execute(inputs)
        assert result["thinking"] == "Thinking step 1\nThinking step 2"
        assert result["assistant_text"] == "Final"

@pytest.mark.asyncio
async def test_tool_calling(chat_node):
    inputs = {
        "model": "test_model",
        "messages": [{"role": "user", "content": "Use tool"}],
        "tools": [{"type": "function", "function": {"name": "test_tool"}}]
    }
    
    with patch("ollama.AsyncClient") as mock_client:
        mock_response = {
            "message": {
                "tool_calls": [{"function": {"name": "test_tool", "arguments": {"param": "value"}}}]
            }
        }
        mock_chat = AsyncMock(return_value=mock_response)
        mock_client.return_value.chat = mock_chat
        
        result = await chat_node.execute(inputs)
        assert "tool_calls" in result["assistant_message"]

@pytest.mark.asyncio
async def test_seed_modes_comprehensive(chat_node):
    inputs = {"model": "test_model", "messages": [{"role": "user", "content": "Test"}]}
    
    # Fixed seed
    chat_node.params["seed_mode"] = "fixed"
    chat_node.params["seed"] = 42
    with patch("ollama.AsyncClient") as mock_client:
        mock_chat = AsyncMock(return_value={"message": {}})
        mock_client.return_value.chat = mock_chat
        await chat_node.execute(inputs)
        assert mock_chat.call_args.kwargs["options"]["seed"] == 42
    
    # Random seed
    chat_node.params["seed_mode"] = "random"
    with patch("ollama.AsyncClient") as mock_client, patch("random.randint") as mock_randint:
        mock_randint.return_value = 100
        mock_chat = AsyncMock(return_value={"message": {}})
        mock_client.return_value.chat = mock_chat
        await chat_node.execute(inputs)
        assert mock_chat.call_args.kwargs["options"]["seed"] == 100
    
    # Increment seed
    chat_node.params["seed_mode"] = "increment"
    chat_node.params["seed"] = 10
    with patch("ollama.AsyncClient") as mock_client:
        mock_chat = AsyncMock(return_value={"message": {}})
        mock_client.return_value.chat = mock_chat
        
        await chat_node.execute(inputs)
        assert mock_chat.call_args.kwargs["options"]["seed"] == 10
        
        await chat_node.execute(inputs)
        assert mock_chat.call_args.kwargs["options"]["seed"] == 11

@pytest.mark.asyncio
async def test_error_in_streaming(chat_node):
    chat_node.params["stream"] = True
    inputs = {"model": "test_model", "messages": [{"role": "user", "content": "Test"}]}
    
    with patch("ollama.AsyncClient") as mock_client:
        async def mock_stream():
            yield {"message": {"content": "Partial"}}
            raise Exception("Stream error")
        
        mock_chat = AsyncMock(return_value=mock_stream())
        mock_client.return_value.chat = mock_chat
        
        gen = chat_node.start(inputs)
        partial = await anext(gen)
        assert partial["assistant_text"] == "Partial"
        
        final = await anext(gen)
        assert "error" in final["metrics"]
        assert final["metrics"]["error"] == "Stream error"

@pytest.mark.asyncio
async def test_stop_mid_stream(chat_node):
    chat_node.params["stream"] = True
    inputs = {"model": "test_model", "messages": [{"role": "user", "content": "Long response"}]}
    
    with patch("ollama.AsyncClient") as mock_client:
        async def mock_stream():
            yield {"message": {"content": "Part 1"}}
            await asyncio.sleep(0.1)  # Simulate delay
            yield {"message": {"content": "Part 2"}}
        
        mock_chat = AsyncMock(return_value=mock_stream())
        mock_client.return_value.chat = mock_chat
        
        gen = chat_node.start(inputs)
        part1 = await anext(gen)
        assert part1["assistant_text"] == "Part 1"
        
        chat_node.stop()
        
        with pytest.raises(StopAsyncIteration):
            await anext(gen)

@pytest.mark.asyncio
async def test_message_building(chat_node):
    inputs = {
        "model": "test_model",
        "prompt": "User prompt",
        "system": "System instruction"
    }
    
    with patch("ollama.AsyncClient") as mock_client:
        mock_chat = AsyncMock(return_value={"message": {"content": "Response"}})
        mock_client.return_value.chat = mock_chat
        
        await chat_node.execute(inputs)
        called_messages = mock_chat.call_args.kwargs["messages"]
        assert len(called_messages) == 2
        assert called_messages[0]["role"] == "system"
        assert called_messages[0]["content"] == "System instruction"
        assert called_messages[1]["role"] == "user"
        assert called_messages[1]["content"] == "User prompt"

@pytest.mark.asyncio
async def test_existing_messages_with_prompt_system(chat_node):
    inputs = {
        "model": "test_model",
        "messages": [{"role": "user", "content": "First"}],
        "prompt": "Second",
        "system": "System"
    }
    
    with patch("ollama.AsyncClient") as mock_client:
        mock_chat = AsyncMock(return_value={"message": {"content": "Response"}})
        mock_client.return_value.chat = mock_chat
        
        await chat_node.execute(inputs)
        called_messages = mock_chat.call_args.kwargs["messages"]
        assert len(called_messages) == 3
        assert called_messages[0]["role"] == "system"
        assert called_messages[1]["role"] == "user" and called_messages[1]["content"] == "First"
        assert called_messages[2]["role"] == "user" and called_messages[2]["content"] == "Second"

@pytest.mark.asyncio
async def test_error_handling(chat_node):
    inputs = {"model": "test_model", "messages": [{"role": "user", "content": "Test"}]}
    
    with patch("ollama.AsyncClient") as mock_client:
        mock_client.return_value.chat.side_effect = Exception("API Error")
        
        gen = chat_node.start(inputs)
        output = await anext(gen)
        assert "error" in output["metrics"]
        assert output["metrics"]["error"] == "API Error"

@pytest.mark.asyncio
async def test_stop(chat_node):
    chat_node.stop()  # Should not raise

# Add more tests for other params like temperature, think, etc.
