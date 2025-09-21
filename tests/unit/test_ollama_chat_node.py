
import pytest
from unittest.mock import AsyncMock, MagicMock, patch, Mock
import asyncio
from nodes.core.llm.ollama_chat_node import OllamaChatNode
from core.types_registry import LLMChatMessage, LLMChatMetrics
import os

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
            {"message": {"role": "assistant", "content": "Hi"}},
            {"message": {"role": "assistant", "content": " there"}, "done": True, "total_duration": 100}
        ]
        mock_chat = AsyncMock(return_value=mock_stream)
        mock_client.return_value.chat = mock_chat
        
        gen = chat_node.start(inputs)
        output1 = await anext(gen)
        assert output1["message"]["content"] == "Hi"
        assert "done" in output1 and not output1["done"]
        assert isinstance(output1.get("metrics", {}), dict)
        
        output2 = await anext(gen)
        assert output2["message"]["content"] == "Hi there"
        assert "done" in output2 and not output2["done"]
        
        output3 = await anext(gen)
        assert output3["message"]["content"] == "Hi there"
        assert "metrics" in output3
        assert output3["done"] == True

@pytest.mark.asyncio
async def test_start_non_streaming_mode(chat_node):
    chat_node.params["stream"] = False
    inputs = {
        "model": "test_model",
        "messages": [{"role": "user", "content": "Hello"}]
    }
    
    with patch("ollama.AsyncClient") as mock_client:
        mock_response = {
            "message": {"role": "assistant", "content": "Hello back"},
            "total_duration": 100
        }
        mock_chat = AsyncMock(return_value=mock_response)
        mock_client.return_value.chat = mock_chat
        
        gen = chat_node.start(inputs)
        output = await anext(gen)
        assert output["message"]["content"] == "Hello back"
        assert "metrics" in output and output["metrics"]["total_duration"] == 100

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
        assert result["message"]["thinking"] == "Thinking step 1\nThinking step 2"
        assert result["message"]["content"] == "Final"

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
        assert "tool_calls" in result["message"]

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
        assert partial["message"]["content"] == "Partial"
        
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
        assert part1["message"]["content"] == "Part 1"
        
        chat_node.stop()
        await asyncio.sleep(0.1)  # Allow time for cancellation to propagate

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

@pytest.mark.asyncio
async def test_quick_streaming_completion(chat_node):
    chat_node.params["stream"] = True
    inputs = {
        "model": "test_model",
        "messages": [{"role": "user", "content": "Short"}]
    }
    
    with patch("ollama.AsyncClient") as mock_client:
        mock_stream = AsyncMock()
        mock_stream.__aiter__.return_value = [
            {"message": {"content": "{}"}, "done": True, "total_duration": 50, "eval_count": 10}
        ]
        mock_chat = AsyncMock(return_value=mock_stream)
        mock_client.return_value.chat = mock_chat
        
        gen = chat_node.start(inputs)
        output1 = await anext(gen)
        assert output1["message"]["content"] == "{}"
        
        output2 = await anext(gen)
        assert output2["message"]["content"] == "{}"
        assert "total_duration" in output2["metrics"]
        assert output2["metrics"]["total_duration"] == 50
        assert "eval_count" in output2["metrics"]
        
        with pytest.raises(StopAsyncIteration):
            await anext(gen)

@pytest.mark.asyncio
async def test_streaming_cancellation(chat_node):
    chat_node.params["stream"] = True
    inputs = {"model": "test_model", "messages": [{"role": "user", "content": "Long"}]}

    with patch("ollama.AsyncClient") as mock_client:
        async def mock_stream():
            yield {"message": {"content": "Part1"}}
            await asyncio.sleep(0.5)
            yield {"message": {"content": "Part2"}}
            yield {"done": True}

        mock_chat = AsyncMock(return_value=mock_stream())
        mock_client.return_value.chat = mock_chat

        gen = chat_node.start(inputs)
        part1 = await anext(gen)
        assert "Part1" in part1["message"]["content"]

        chat_node.stop()
        await asyncio.sleep(0.1)  # Allow time for cancellation to propagate

        with pytest.raises(StopAsyncIteration):
            await anext(gen)

@pytest.mark.asyncio
async def test_multiprocessing_fallback(chat_node):
    chat_node.params["stream"] = True
    inputs = {"model": "test_model", "messages": [{"role": "user", "content": "Test"}]}
    
    with patch.dict(os.environ, {"PYTEST_CURRENT_TEST": ""}, clear=False):
        with patch("multiprocessing.Process", side_effect=Exception("MP fail")):
            with patch("ollama.AsyncClient") as mock_client:
                mock_iterator = AsyncMock()
                mock_iterator.__anext__.side_effect = [
                    {"message": {"content": "Fallback"}, "done": True, "total_duration": 100},
                    StopAsyncIteration()
                ]
                mock_stream = AsyncMock()
                mock_stream.__aiter__ = Mock(return_value=mock_iterator)
                mock_chat = AsyncMock(return_value=mock_stream)
                mock_client.return_value.chat = mock_chat

                gen = chat_node.start(inputs)
                output1 = await anext(gen)
                assert output1["message"]["content"] == "Fallback"

                output2 = await anext(gen)
                assert "total_duration" in output2["metrics"]

@pytest.mark.asyncio
async def test_interleaved_streaming(chat_node):
    inputs = {
        "model": "test_model",
        "messages": [{"role": "user", "content": "Complex response with thinking and tools"}]
    }
    
    # Non-streaming baseline
    chat_node.params["stream"] = False
    with patch("ollama.AsyncClient") as mock_client_ns:
        mock_response = {
            "message": {
                "role": "assistant",
                "content": "Final content",
                "thinking": "Thought process",
                "tool_calls": [{"function": {"name": "tool1", "arguments": {"param": "value"}}}]
            },
            "total_duration": 100
        }
        mock_chat_ns = AsyncMock(return_value=mock_response)
        mock_client_ns.return_value.chat = mock_chat_ns
        ns_result = await chat_node.execute(inputs)
    
    # Streaming with interleaved chunks
    chat_node.params["stream"] = True
    with patch("ollama.AsyncClient") as mock_client_s:
        mock_stream = AsyncMock()
        mock_stream.__aiter__.return_value = [
            {"message": {"thinking": "Thought "}},  # Partial thinking
            {"message": {"tool_calls": [{"function": {"name": "tool1"}}]}},  # Partial tool
            {"message": {"content": "Final "}},  # Partial content
            {"message": {"thinking": "process"}},  # More thinking
            {"message": {"tool_calls": [{"function": {"arguments": {"param": "value"}}}]}},  # Complete tool
            {"message": {"content": "content"}, "done": True, "total_duration": 100}  # Final content and done
        ]
        mock_chat_s = AsyncMock(return_value=mock_stream)
        mock_client_s.return_value.chat = mock_chat_s
        
        gen = chat_node.start(inputs)
        outputs = []
        async for out in gen:
            outputs.append(out)
        
        # Assert progressive yields are valid partial LLMChatMessage
        assert len(outputs) > 1
        assert all("message" in o and "role" in o["message"] for o in outputs[:-1])
        assert all(not o.get("done", False) for o in outputs[:-1])
        
        # Assert final matches non-streaming
        s_final = outputs[-1]
        assert s_final["message"] == ns_result["message"]
        assert s_final["metrics"] == ns_result["metrics"]
        assert s_final["done"] is True

@pytest.mark.asyncio
async def test_partial_tool_discard(chat_node):
    chat_node.params["stream"] = True
    inputs = {"model": "test_model", "messages": [{"role": "user", "content": "Test partial tool"}]}
    
    with patch("ollama.AsyncClient") as mock_client:
        mock_stream = AsyncMock()
        mock_stream.__aiter__.return_value = [
            {"message": {"tool_calls": [{"function": {"name": "incomplete_tool"}}]}},  # Incomplete (missing args)
            {"message": {"content": "Content"}},
            {"done": True}
        ]
        mock_chat = AsyncMock(return_value=mock_stream)
        mock_client.return_value.chat = mock_chat
        
        gen = chat_node.start(inputs)
        outputs = [out async for out in gen]
        
        final = outputs[-1]
        assert "tool_calls" not in final["message"] or len(final["message"]["tool_calls"]) == 0  # Discarded incomplete
        assert final["message"]["content"] == "Content"

# Expand existing test_streaming_equals_nonstreaming to include thinking and tool_calls
@pytest.mark.asyncio
async def test_streaming_equals_nonstreaming(chat_node):
    inputs = {
        "model": "test_model",
        "messages": [{"role": "user", "content": "Test equality"}]
    }
    
    # Non-streaming
    chat_node.params["stream"] = False
    with patch("ollama.AsyncClient") as mock_client_ns:
        mock_response = {
            "message": {
                "role": "assistant",
                "content": "Full response",
                "thinking": "Thought",
                "tool_calls": [{"function": {"name": "tool", "arguments": {}}}]
            },
            "total_duration": 100,
            "eval_count": 10
        }
        mock_chat_ns = AsyncMock(return_value=mock_response)
        mock_client_ns.return_value.chat = mock_chat_ns
        ns_result = await chat_node.execute(inputs)
    
    # Streaming
    chat_node.params["stream"] = True
    with patch("ollama.AsyncClient") as mock_client_s:
        mock_stream = AsyncMock()
        mock_stream.__aiter__.return_value = [
            {"message": {"thinking": "Tho"}},
            {"message": {"thinking": "ught"}},
            {"message": {"tool_calls": [{"function": {"name": "tool", "arguments": {}}}]}},
            {"message": {"content": "Full "}},
            {"message": {"content": "response"}},
            {"done": True, "total_duration": 100, "eval_count": 10}
        ]
        mock_chat_s = AsyncMock(return_value=mock_stream)
        mock_client_s.return_value.chat = mock_chat_s
        
        gen = chat_node.start(inputs)
        outputs = [out async for out in gen]
        
        s_final = outputs[-1]
        assert s_final["message"] == ns_result["message"]
        assert s_final["metrics"] == ns_result["metrics"]
        assert s_final["done"] is True

# Add test for error in mid-stream
@pytest.mark.asyncio
async def test_error_mid_stream(chat_node):
    chat_node.params["stream"] = True
    inputs = {"model": "test_model", "messages": [{"role": "user", "content": "Test error"}]}

    with patch("ollama.AsyncClient") as mock_client:
        async def mock_stream():
            yield {"message": {"content": "Partial"}}
            raise Exception("Stream error")
        
        mock_chat = AsyncMock(return_value=mock_stream())
        mock_client.return_value.chat = mock_chat
        
        gen = chat_node.start(inputs)
        partial = await anext(gen)
        assert partial["message"]["content"] == "Partial"
        
        final = await anext(gen)
        assert "error" in final["metrics"]
        assert final["metrics"]["error"] == "Stream error"
        assert final["done"] is True  # Ensure it finalizes on error

# Add test for empty response stream
@pytest.mark.asyncio
async def test_empty_streaming_response(chat_node):
    chat_node.params["stream"] = True
    inputs = {"model": "test_model", "messages": [{"role": "user", "content": "Empty"}]}

    with patch("ollama.AsyncClient") as mock_client:
        mock_stream = AsyncMock()
        mock_stream.__aiter__.return_value = [{"done": True}]
        mock_chat = AsyncMock(return_value=mock_stream)
        mock_client.return_value.chat = mock_chat
        
        gen = chat_node.start(inputs)
        output = await anext(gen)
        assert output["message"] == {"role": "assistant", "content": ""}  # Default empty
        assert output["done"] is True

# Add more tests for other params like temperature, think, etc.
