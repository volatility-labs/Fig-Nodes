
import pytest
from unittest.mock import AsyncMock, MagicMock, patch, Mock
import asyncio
from nodes.core.llm.ollama_chat_node import OllamaChatNode
from core.types_registry import LLMChatMessage, LLMChatMetrics
import os
import json

@pytest.fixture
def chat_node():
    return OllamaChatNode(id=1, params={})

@pytest.mark.asyncio
async def test_start(chat_node):
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
        assert output["message"]["role"] == "assistant"
        assert "metrics" in output and output["metrics"]["total_duration"] == 100

@pytest.mark.asyncio
async def test_temperature_application(chat_node):
    chat_node.params["temperature"] = 0.5
    inputs = {"model": "test_model", "messages": [{"role": "user", "content": "Hello"}]}
    
    with patch("ollama.AsyncClient") as mock_client:
        mock_chat = AsyncMock(return_value={"message": {"role": "assistant", "content": "Response"}})
        mock_client.return_value.chat = mock_chat
        
        await chat_node.execute(inputs)
        mock_chat.assert_called_once()
        assert mock_chat.call_args.kwargs["options"]["temperature"] == 0.5

@pytest.mark.asyncio
async def test_num_ctx_auto_detect_and_clamp_execute(chat_node):
    # Mock model list for _get_model to succeed
    with patch("httpx.AsyncClient.get") as mock_get:
        mock_get.return_value = AsyncMock()
        mock_get.return_value.json.return_value = {"models": [{"name": "test_model:latest"}]}
        mock_get.return_value.raise_for_status.return_value = None
        
        inputs = {"model": "test_model", "messages": [{"role": "user", "content": "Hello"}]}
        # Simulate /api/show returning context_length via model_info and parameters
        with patch("httpx.AsyncClient.post") as mock_post:
            mock_post.return_value = AsyncMock()
            mock_post.return_value.json.return_value = {
                "model_info": {
                    "llama.context_length": 8192
                },
                "parameters": "num_ctx 4096\nother 1"
            }
            mock_post.return_value.raise_for_status.return_value = None
            
            with patch("ollama.AsyncClient") as mock_client:
                # Force a user-provided num_ctx above max to verify clamping
                chat_node.params["options"] = json.dumps({"num_ctx": 999999})
                mock_chat = AsyncMock(return_value={"message": {"role": "assistant", "content": "ok"}})
                mock_client.return_value.chat = mock_chat
                await chat_node.execute(inputs)
                sent_opts = mock_chat.call_args.kwargs["options"]
                # Should clamp to the larger of detected values; model_info had 8192
                assert sent_opts.get("num_ctx") == 8192

@pytest.mark.asyncio
async def test_num_ctx_auto_detect_set_when_missing_start(chat_node):
    # Mock model list for _get_model to succeed
    with patch("httpx.AsyncClient.get") as mock_get:
        mock_get.return_value = AsyncMock()
        mock_get.return_value.json.return_value = {"models": [{"name": "test_model:latest"}]}
        mock_get.return_value.raise_for_status.return_value = None
        
        chat_node.params["stream"] = False
        inputs = {"model": "test_model", "messages": [{"role": "user", "content": "Hello"}]}
        # Simulate /api/show returning context_length via model_info and parameters
        with patch("httpx.AsyncClient.post") as mock_post:
            mock_post.return_value = AsyncMock()
            mock_post.return_value.json.return_value = {"model_info": {"qwen.context_length": 32768}}
            mock_post.return_value.raise_for_status.return_value = None
            
            with patch("ollama.AsyncClient") as mock_client:
                mock_response = {"message": {"role": "assistant", "content": "ok"}}
                mock_chat = AsyncMock(return_value=mock_response)
                mock_client.return_value.chat = mock_chat
                gen = chat_node.start(inputs)
                _ = await anext(gen)
                sent_opts = mock_chat.call_args.kwargs["options"]
                assert sent_opts.get("num_ctx") == 32768

@pytest.mark.asyncio
async def test_think_mode(chat_node):
    chat_node.params["think"] = True
    inputs = {"model": "test_model", "messages": [{"role": "user", "content": "Think"}]}
    
    with patch("ollama.AsyncClient") as mock_client:
        mock_response = {
            "message": {"role": "assistant", "content": "Final", "thinking": "Thinking step 1\nThinking step 2"}
        }
        mock_chat = AsyncMock(return_value=mock_response)
        mock_client.return_value.chat = mock_chat
        
        result = await chat_node.execute(inputs)
        assert result["message"]["content"] == "Final"
        assert result["message"]["role"] == "assistant"
        assert result["message"]["thinking"] == "Thinking step 1\nThinking step 2"
        assert len(result["thinking_history"]) == 1
        assert result["thinking_history"][0]["thinking"] == "Thinking step 1\nThinking step 2"

@pytest.mark.asyncio
async def test_tool_calling(chat_node):
    chat_node.params["max_tool_iters"] = 1  # Limit to 1 iteration
    inputs = {
        "model": "test_model",
        "messages": [{"role": "user", "content": "Use tool"}],
        "tools": [{"type": "function", "function": {"name": "test_tool"}}]
    }
    
    with patch("ollama.AsyncClient") as mock_client:
        # First call: tool calls, second call: no tool calls (end loop), third call: final response
        mock_responses = [
            {
                "message": {
                    "role": "assistant",
                    "tool_calls": [{"function": {"name": "test_tool", "arguments": {"param": "value"}}}]
                }
            },
            {
                "message": {"role": "assistant", "content": "Tool executed"}  # No tool_calls, ends loop
            },
            {
                "message": {"role": "assistant", "content": "Final response"}
            }
        ]
        mock_chat = AsyncMock(side_effect=mock_responses)
        mock_client.return_value.chat = mock_chat
        
        result = await chat_node.execute(inputs)
        # Tool calls are now in tool_history
        assert len(result["tool_history"]) == 1
        assert result["tool_history"][0]["call"]["function"]["name"] == "test_tool"
        assert result["message"]["content"] == "Final response"
        assert result["message"]["role"] == "assistant"

@pytest.mark.asyncio
async def test_seed_modes_comprehensive(chat_node):
    inputs = {"model": "test_model", "messages": [{"role": "user", "content": "Test"}]}
    
    # Fixed seed
    chat_node.params["seed_mode"] = "fixed"
    chat_node.params["seed"] = 42
    with patch("ollama.AsyncClient") as mock_client:
        mock_chat = AsyncMock(return_value={"message": {"role": "assistant", "content": ""}})
        mock_client.return_value.chat = mock_chat
        await chat_node.execute(inputs)
        assert mock_chat.call_args.kwargs["options"]["seed"] == 42
    
    # Random seed
    chat_node.params["seed_mode"] = "random"
    with patch("random.randint") as mock_randint:
        mock_randint.return_value = 100
        # Patch AsyncClient for this block so we can assert call args
        with patch("ollama.AsyncClient") as mock_client:
            mock_chat = AsyncMock(return_value={"message": {"role": "assistant", "content": ""}})
            mock_client.return_value.chat = mock_chat
            await chat_node.execute(inputs)
            assert mock_chat.call_args.kwargs["options"]["seed"] == 100
    
    # Increment seed
    chat_node.params["seed_mode"] = "increment"
    chat_node.params["seed"] = 10
    with patch("ollama.AsyncClient") as mock_client:
        mock_chat = AsyncMock(return_value={"message": {"role": "assistant", "content": ""}})
        mock_client.return_value.chat = mock_chat
        
        await chat_node.execute(inputs)
        assert mock_chat.call_args.kwargs["options"]["seed"] == 10
        
        await chat_node.execute(inputs)
        assert mock_chat.call_args.kwargs["options"]["seed"] == 11

# New tests for CLI-based unload via `ollama stop <model>`

def test_stop_triggers_cli_unload_with_model_and_host(chat_node):
    chat_node._last_model = "llama3.2:latest"
    chat_node._last_host = "http://localhost:11434"
    with patch("nodes.core.llm.ollama_chat_node.sp.Popen") as popen:
        chat_node.stop()
        popen.assert_called_once()
        args, kwargs = popen.call_args
        assert args[0] == ["ollama", "stop", "llama3.2:latest"]
        env = kwargs.get("env", {})
        assert env.get("OLLAMA_HOST") == "http://localhost:11434"


def test_stop_uses_env_host_when_no_last_host(chat_node, monkeypatch):
    chat_node._last_model = "deepseek-r1:latest"
    chat_node._last_host = None
    monkeypatch.setenv("OLLAMA_HOST", "http://remote:11434")
    with patch("nodes.core.llm.ollama_chat_node.sp.Popen") as popen:
        chat_node.stop()
        popen.assert_called_once()
        args, kwargs = popen.call_args
        assert args[0] == ["ollama", "stop", "deepseek-r1:latest"]
        assert kwargs["env"]["OLLAMA_HOST"] == "http://remote:11434"


def test_stop_does_not_call_cli_when_no_model(chat_node):
    chat_node._last_model = None
    chat_node._last_host = "http://localhost:11434"
    with patch("nodes.core.llm.ollama_chat_node.sp.Popen") as popen:
        chat_node.stop()
        popen.assert_not_called()


def test_stop_handles_popen_exception(chat_node):
    chat_node._last_model = "llama3.2:latest"
    chat_node._last_host = "http://localhost:11434"
    with patch("nodes.core.llm.ollama_chat_node.sp.Popen") as popen:
        popen.side_effect = OSError("not found")
        # Should not raise
        chat_node.stop()
        popen.assert_called_once()


@pytest.mark.asyncio
async def test_start_sets_last_model_and_host(chat_node):
    chat_node.params["stream"] = False
    inputs = {"model": "mistral", "host": "http://h1:11434", "messages": [{"role": "user", "content": "Hi"}]}
    with patch("ollama.AsyncClient") as mock_client:
        mock_client.return_value.chat = AsyncMock(return_value={"message": {"role": "assistant", "content": "ok"}})
        gen = chat_node.start(inputs)
        _ = await anext(gen)
        assert chat_node._last_model == "mistral"
        assert chat_node._last_host == "http://h1:11434"


@pytest.mark.asyncio
async def test_execute_sets_last_model_and_host(chat_node):
    inputs = {"model": "qwen2", "host": "http://h2:11434", "messages": [{"role": "user", "content": "Hi"}]}
    with patch("ollama.AsyncClient") as mock_client:
        mock_client.return_value.chat = AsyncMock(return_value={"message": {"role": "assistant", "content": "ok"}})
        await chat_node.execute(inputs)
        assert chat_node._last_model == "qwen2"
        assert chat_node._last_host == "http://h2:11434"


def test_force_stop_idempotent_unload_once(chat_node):
    chat_node._last_model = "llama3.2:latest"
    chat_node._last_host = "http://localhost:11434"
    with patch("nodes.core.llm.ollama_chat_node.sp.Popen") as popen:
        chat_node.force_stop()
        chat_node.force_stop()  # Second call should be a no-op
        popen.assert_called_once()


def test_stop_with_alive_child_process_does_not_break_unload(chat_node):
    class _FakeProc:
        def __init__(self):
            self.pid = 123
            self._alive = True
        def is_alive(self):
            return self._alive
        def kill(self):
            self._alive = False
        def join(self, timeout=None):
            self._alive = False

    chat_node._proc = _FakeProc()
    chat_node._ipc_parent = MagicMock()
    chat_node._last_model = "llama3.2:latest"
    chat_node._last_host = "http://localhost:11434"
    with patch("nodes.core.llm.ollama_chat_node.sp.Popen") as popen:
        chat_node.stop()
        popen.assert_called_once()

@pytest.mark.asyncio
async def test_message_building(chat_node):
    inputs = {
        "model": "test_model",
        "prompt": "User prompt",
        "system": "System instruction"
    }
    
    with patch("ollama.AsyncClient") as mock_client:
        mock_chat = AsyncMock(return_value={"message": {"role": "assistant", "content": "Response"}})
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
        mock_chat = AsyncMock(return_value={"message": {"role": "assistant", "content": "Response"}})
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
        assert output["message"]["content"] == ""
        assert output["message"]["role"] == "assistant"

@pytest.mark.asyncio
async def test_stop(chat_node):
    chat_node.stop()  # Should not raise
