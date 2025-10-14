
import pytest
from unittest.mock import AsyncMock, MagicMock, patch, Mock
import asyncio
from nodes.core.llm.ollama_chat_node import OllamaChatNode
from core.types_registry import LLMChatMessage, LLMChatMetrics
import os
import json
import sys

@pytest.fixture
def chat_node():
    return OllamaChatNode(id=1, params={})

@pytest.mark.asyncio
async def test_start(chat_node):
    # Rename to test_execute since streaming is removed
    # async def test_execute(chat_node):
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
        
        output = await chat_node.execute(inputs)
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

# For test_num_ctx_auto_detect_set_when_missing_start, rename and adjust:
@pytest.mark.asyncio
async def test_num_ctx_auto_detect_set_when_missing_execute(chat_node):
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
                output = await chat_node.execute(inputs)
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
        # First call: tool calls, second call: no tool_calls (end loop)
        mock_responses = [
            {
                "message": {"role": "assistant", "tool_calls": [{"function": {"name": "test_tool", "arguments": {"param": "value"}}}]}
            },
            {
                "message": {"role": "assistant", "content": "Tool executed"}  # No tool_calls, ends loop
            },
        ]
        mock_chat = AsyncMock(side_effect=mock_responses)
        mock_client.return_value.chat = mock_chat
        
        result = await chat_node.execute(inputs)
        # Tool calls are now in tool_history
        assert len(result["tool_history"]) == 1
        assert result["tool_history"][0]["call"]["function"]["name"] == "test_tool"
        assert result["message"]["content"] == "Tool executed"
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

def test_stop_triggers_cli_unload_with_model_and_host(chat_node, monkeypatch):
    monkeypatch.setattr(sys, 'platform', 'win32')
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
    monkeypatch.setattr(sys, 'platform', 'win32')
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


@pytest.mark.asyncio
async def test_start_sets_last_model_and_host(chat_node):
    chat_node.params["stream"] = False
    inputs = {"model": "mistral", "host": "http://h1:11434", "messages": [{"role": "user", "content": "Hi"}]}
    with patch("ollama.AsyncClient") as mock_client:
        mock_client.return_value.chat = AsyncMock(return_value={"message": {"role": "assistant", "content": "ok"}})
        output = await chat_node.execute(inputs)
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


def test_force_stop_idempotent_unload_once(chat_node, monkeypatch):
    monkeypatch.setattr(sys, 'platform', 'win32')
    chat_node._last_model = "llama3.2:latest"
    chat_node._last_host = "http://localhost:11434"
    with patch("nodes.core.llm.ollama_chat_node.sp.Popen") as popen:
        chat_node.force_stop()
        chat_node.force_stop()  # Second call should be a no-op
        popen.assert_called_once()


def test_stop_with_alive_child_process_does_not_break_unload(chat_node, monkeypatch):
    monkeypatch.setattr(sys, 'platform', 'win32')
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
        
        output = await chat_node.execute(inputs)
        assert "error" in output["metrics"]
        assert output["metrics"]["error"] == "API Error"
        assert output["message"]["content"] == ""
        assert output["message"]["role"] == "assistant"


@pytest.mark.asyncio
async def test_stop(chat_node):
    chat_node.stop()  # Should not raise


@pytest.mark.asyncio
async def test_system_input_strict_typing(chat_node):
    # Valid str input
    valid_str_inputs = {
        "model": "test_model",
        "messages": [{"role": "user", "content": "Hello"}],
        "system": "Valid system string"
    }
    with patch("ollama.AsyncClient") as mock_client:
        mock_response = {"message": {"role": "assistant", "content": "Response"}}
        mock_chat = AsyncMock(return_value=mock_response)
        mock_client.return_value.chat = mock_chat

        result = await chat_node.execute(valid_str_inputs)
        assert "error" not in result["metrics"]
        assert result["message"]["content"] == "Response"

    # Valid LLMChatMessage input
    valid_msg_inputs = {
        "model": "test_model",
        "messages": [{"role": "user", "content": "Hello"}],
        "system": {"role": "system", "content": "Valid system message"}
    }
    with patch("ollama.AsyncClient") as mock_client:
        mock_response = {"message": {"role": "assistant", "content": "Response"}}
        mock_chat = AsyncMock(return_value=mock_response)
        mock_client.return_value.chat = mock_chat

        result = await chat_node.execute(valid_msg_inputs)
        assert "error" not in result["metrics"]
        assert result["message"]["content"] == "Response"

    # Invalid: int instead of str or LLMChatMessage
    invalid_int_inputs = {
        "model": "test_model",
        "messages": [{"role": "user", "content": "Hello"}],
        "system": 42
    }
    with patch("ollama.AsyncClient") as mock_client:
        mock_response = {"message": {"role": "assistant", "content": "Response"}}
        mock_chat = AsyncMock(return_value=mock_response)
        mock_client.return_value.chat = mock_chat

        # Should still execute but may log warnings; ensure no crash
        result = await chat_node.execute(invalid_int_inputs)
        assert "error" not in result["metrics"]

    # Invalid: dict without proper structure
    invalid_dict_inputs = {
        "model": "test_model",
        "messages": [{"role": "user", "content": "Hello"}],
        "system": {"role": "user", "content": "Wrong role"}
    }
    with patch("ollama.AsyncClient") as mock_client:
        mock_response = {"message": {"role": "assistant", "content": "Response"}}
        mock_chat = AsyncMock(return_value=mock_response)
        mock_client.return_value.chat = mock_chat

        # Should still execute, as runtime handles it
        result = await chat_node.execute(invalid_dict_inputs)
        assert "error" not in result["metrics"]


# Tests for force kill in _unload_model_via_cli

def test_unload_model_via_cli_force_kill_mac(chat_node, monkeypatch):
    monkeypatch.setattr(sys, 'platform', 'darwin')
    chat_node._last_model = "llama3.2:latest"
    chat_node._last_host = "http://localhost:11434"
    with patch("nodes.core.llm.ollama_chat_node.sp.Popen") as mock_popen:
        chat_node._unload_model_via_cli()
        assert mock_popen.call_count == 2
        # First call: ollama stop
        assert mock_popen.call_args_list[0][0][0] == ["ollama", "stop", "llama3.2:latest"]
        # Second call: force kill
        force_call = mock_popen.call_args_list[1][0][0]
        assert force_call[0] == '/bin/sh'
        assert force_call[1] == '-c'
        cmd = force_call[2]
        expected_cmd = 'sleep 2; pid=$(lsof -ti :11434); [ -n "$pid" ] && kill -9 $pid'
        assert cmd == expected_cmd


def test_unload_model_via_cli_force_kill_linux(chat_node, monkeypatch):
    monkeypatch.setattr(sys, 'platform', 'linux')
    chat_node._last_model = "llama3.2:latest"
    chat_node._last_host = "http://localhost:12345"
    with patch("nodes.core.llm.ollama_chat_node.sp.Popen") as mock_popen:
        chat_node._unload_model_via_cli()
        assert mock_popen.call_count == 2
        # First call: ollama stop
        assert mock_popen.call_args_list[0][0][0] == ["ollama", "stop", "llama3.2:latest"]
        # Second call: force kill with custom port
        force_call = mock_popen.call_args_list[1][0][0]
        assert force_call[0] == '/bin/sh'
        assert force_call[1] == '-c'
        cmd = force_call[2]
        expected_cmd = 'sleep 2; pid=$(lsof -ti :12345); [ -n "$pid" ] && kill -9 $pid'
        assert cmd == expected_cmd


def test_unload_model_via_cli_no_force_kill_windows(chat_node, monkeypatch):
    monkeypatch.setattr(sys, 'platform', 'win32')
    chat_node._last_model = "llama3.2:latest"
    chat_node._last_host = "http://localhost:11434"
    with patch("nodes.core.llm.ollama_chat_node.sp.Popen") as mock_popen:
        chat_node._unload_model_via_cli()
        assert mock_popen.call_count == 1  # Only ollama stop, no force kill
        assert mock_popen.call_args[0][0] == ["ollama", "stop", "llama3.2:latest"]


def test_unload_model_via_cli_force_kill_handles_exception(chat_node, monkeypatch):
    monkeypatch.setattr(sys, 'platform', 'darwin')
    chat_node._last_model = "llama3.2:latest"
    chat_node._last_host = "invalid_url"
    with patch("nodes.core.llm.ollama_chat_node.sp.Popen") as mock_popen:
        mock_popen.side_effect = [None, OSError("command not found")]  # First succeeds, second fails
        chat_node._unload_model_via_cli()  # Should not raise
        assert mock_popen.call_count == 2
