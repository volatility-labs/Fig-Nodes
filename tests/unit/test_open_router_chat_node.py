import asyncio
from typing import Any
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest

from core.types_registry import NodeExecutionError
from nodes.core.llm.open_router_chat_node import OpenRouterChat


@pytest.fixture
def chat_node() -> OpenRouterChat:
    return OpenRouterChat(id=1, params={})


def create_mock_context_manager(data: dict[str, Any]) -> Mock:
    """Helper to create a mock async context manager for aiohttp response."""

    async def json_func():
        return data

    response = Mock()
    response.json = json_func
    response.raise_for_status = Mock()

    context_manager = MagicMock()
    context_manager.__aenter__ = AsyncMock(return_value=response)
    context_manager.__aexit__ = AsyncMock(return_value=None)

    return context_manager


@pytest.mark.asyncio
async def test_execute_basic(chat_node: OpenRouterChat) -> None:
    """Test basic execution without tools."""
    inputs: dict[str, Any] = {"messages": [{"role": "user", "content": "Hello"}]}

    with (
        patch(
            "nodes.core.llm.open_router_chat_node.OpenRouterChat._get_session"
        ) as mock_get_session,
        patch("core.api_key_vault.APIKeyVault.get") as mock_get,
    ):
        mock_get.return_value = "fake-api-key"

        response_data = {
            "id": "gen-123",
            "model": "test-model",
            "created": 1234567890,
            "object": "chat.completion",
            "choices": [
                {
                    "finish_reason": "stop",
                    "message": {"role": "assistant", "content": "Hello back"},
                }
            ],
            "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
        }
        mock_response_context = create_mock_context_manager(response_data)

        mock_session = AsyncMock()
        mock_session.post = Mock(return_value=mock_response_context)
        mock_get_session.return_value = mock_session

        result = await chat_node.execute(inputs)
        assert result["message"]["content"] == "Hello back"
        assert result["message"]["role"] == "assistant"
        assert result["metrics"]["prompt_tokens"] == 10
        assert result["metrics"]["completion_tokens"] == 5
        assert result["metrics"]["total_tokens"] == 15
        assert result["metrics"]["finish_reason"] == "stop"


@pytest.mark.asyncio
async def test_finish_reason_in_metrics(chat_node):
    """Test that finish_reason is included in metrics."""
    inputs = {"messages": [{"role": "user", "content": "Hello"}]}

    with (
        patch(
            "nodes.core.llm.open_router_chat_node.OpenRouterChat._get_session"
        ) as mock_get_session,
        patch("core.api_key_vault.APIKeyVault.get") as mock_get,
    ):
        mock_get.return_value = "fake-api-key"

        response_data = {
            "id": "gen-123",
            "model": "test-model",
            "created": 1234567890,
            "object": "chat.completion",
            "choices": [
                {
                    "finish_reason": "length",
                    "native_finish_reason": "length",
                    "message": {"role": "assistant", "content": "Truncated"},
                }
            ],
            "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
        }
        mock_response_context = create_mock_context_manager(response_data)

        mock_session = AsyncMock()
        mock_session.post = Mock(return_value=mock_response_context)
        mock_get_session.return_value = mock_session

        result = await chat_node.execute(inputs)
        assert result["metrics"]["finish_reason"] == "length"
        assert result["metrics"]["native_finish_reason"] == "length"


@pytest.mark.asyncio
async def test_error_finish_reason_handling(chat_node):
    """Test that error finish_reason is properly handled."""
    inputs = {"messages": [{"role": "user", "content": "Hello"}]}

    with (
        patch(
            "nodes.core.llm.open_router_chat_node.OpenRouterChat._get_session"
        ) as mock_get_session,
        patch("core.api_key_vault.APIKeyVault.get") as mock_get,
    ):
        mock_get.return_value = "fake-api-key"

        response_data = {
            "id": "gen-123",
            "model": "test-model",
            "created": 1234567890,
            "object": "chat.completion",
            "choices": [
                {
                    "finish_reason": "error",
                    "message": {"role": "assistant", "content": ""},
                }
            ],
            "usage": {"prompt_tokens": 10, "completion_tokens": 0, "total_tokens": 10},
        }
        mock_response_context = create_mock_context_manager(response_data)

        mock_session = AsyncMock()
        mock_session.post = Mock(return_value=mock_response_context)
        mock_get_session.return_value = mock_session

        result = await chat_node.execute(inputs)
        assert result["message"]["content"] == "API returned error"
        assert "error" in result["metrics"]
        assert "finish_reason: error" in result["metrics"]["error"]


@pytest.mark.asyncio
async def test_temperature_and_seed(chat_node):
    """Test temperature and seed parameters."""
    chat_node.params["temperature"] = 0.8
    chat_node.params["seed"] = 42
    inputs = {"messages": [{"role": "user", "content": "Hello"}]}

    with (
        patch(
            "nodes.core.llm.open_router_chat_node.OpenRouterChat._get_session"
        ) as mock_get_session,
        patch("core.api_key_vault.APIKeyVault.get") as mock_get,
    ):
        mock_get.return_value = "fake-api-key"

        response_data = {
            "id": "gen-123",
            "model": "test-model",
            "created": 1234567890,
            "object": "chat.completion",
            "choices": [
                {"finish_reason": "stop", "message": {"role": "assistant", "content": "Response"}}
            ],
            "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
        }
        mock_response_context = create_mock_context_manager(response_data)

        mock_session = AsyncMock()
        mock_session.post = Mock(return_value=mock_response_context)
        mock_get_session.return_value = mock_session

        await chat_node.execute(inputs)
        call_args = mock_session.post.call_args
        request_body = call_args.kwargs["json"]
        assert request_body["temperature"] == 0.8
        assert request_body["seed"] == 42


@pytest.mark.asyncio
async def test_tool_choice_normalization(chat_node):
    """Test that tool_choice is properly normalized."""
    chat_node.params["tool_choice"] = "NONE"  # Test case conversion
    inputs = {"messages": [{"role": "user", "content": "Hello"}]}

    with (
        patch(
            "nodes.core.llm.open_router_chat_node.OpenRouterChat._get_session"
        ) as mock_get_session,
        patch("core.api_key_vault.APIKeyVault.get") as mock_get,
    ):
        mock_get.return_value = "fake-api-key"

        response_data = {
            "id": "gen-123",
            "model": "test-model",
            "created": 1234567890,
            "object": "chat.completion",
            "choices": [
                {"finish_reason": "stop", "message": {"role": "assistant", "content": "Response"}}
            ],
            "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
        }
        mock_response_context = create_mock_context_manager(response_data)

        mock_session = AsyncMock()
        mock_session.post = Mock(return_value=mock_response_context)
        mock_get_session.return_value = mock_session

        await chat_node.execute(inputs)
        call_args = mock_session.post.call_args
        request_body = call_args.kwargs["json"]
        # When no tools are provided, tool_choice should be None
        assert request_body["tool_choice"] is None


@pytest.mark.asyncio
async def test_tool_calling_with_finish_reason(chat_node):
    """Test tool calling with proper finish_reason handling."""
    chat_node.params["max_tool_iters"] = 1
    inputs = {
        "messages": [{"role": "user", "content": "Use tool"}],
        "tools": [{"type": "function", "function": {"name": "test_tool", "parameters": {}}}],
    }

    with (
        patch(
            "nodes.core.llm.open_router_chat_node.OpenRouterChat._get_session"
        ) as mock_get_session,
        patch("core.api_key_vault.APIKeyVault.get") as mock_get,
        patch("services.tools.registry.get_tool_handler") as mock_handler,
    ):
        mock_get.return_value = "fake-api-key"
        mock_handler.return_value = AsyncMock(return_value={"result": "executed"})

        # First call: tool calls with finish_reason
        first_response = create_mock_context_manager(
            {
                "id": "gen-123",
                "model": "test-model",
                "created": 1234567890,
                "object": "chat.completion",
                "choices": [
                    {
                        "finish_reason": "tool_calls",
                        "message": {
                            "role": "assistant",
                            "tool_calls": [
                                {
                                    "id": "call_123",
                                    "type": "function",
                                    "function": {"name": "test_tool", "arguments": "{}"},
                                }
                            ],
                        },
                    }
                ],
                "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
            }
        )

        # Second call: final response after tool execution
        second_response = create_mock_context_manager(
            {
                "id": "gen-124",
                "model": "test-model",
                "created": 1234567891,
                "object": "chat.completion",
                "choices": [
                    {"finish_reason": "stop", "message": {"role": "assistant", "content": "Done"}}
                ],
                "usage": {"prompt_tokens": 15, "completion_tokens": 3, "total_tokens": 18},
            }
        )

        mock_session = AsyncMock()
        mock_session.post = Mock(side_effect=[first_response, second_response])
        mock_get_session.return_value = mock_session

        result = await chat_node.execute(inputs)
        assert len(result["tool_history"]) == 1
        assert result["tool_history"][0]["call"]["id"] == "call_123"
        assert result["message"]["content"] == "Done"
        assert result["metrics"]["finish_reason"] == "stop"


@pytest.mark.asyncio
async def test_tool_calling_without_finish_reason_but_with_tool_calls(chat_node):
    """Test that tool_calls presence takes precedence over finish_reason."""
    chat_node.params["max_tool_iters"] = 1
    inputs = {
        "messages": [{"role": "user", "content": "Use tool"}],
        "tools": [{"type": "function", "function": {"name": "test_tool", "parameters": {}}}],
    }

    with (
        patch(
            "nodes.core.llm.open_router_chat_node.OpenRouterChat._get_session"
        ) as mock_get_session,
        patch("core.api_key_vault.APIKeyVault.get") as mock_get,
        patch("services.tools.registry.get_tool_handler") as mock_handler,
    ):
        mock_get.return_value = "fake-api-key"
        mock_handler.return_value = AsyncMock(return_value={"result": "executed"})

        # First call: tool calls with finish_reason=None (edge case)
        first_response = create_mock_context_manager(
            {
                "id": "gen-123",
                "model": "test-model",
                "created": 1234567890,
                "object": "chat.completion",
                "choices": [
                    {
                        "finish_reason": None,
                        "message": {
                            "role": "assistant",
                            "tool_calls": [
                                {
                                    "id": "call_123",
                                    "type": "function",
                                    "function": {"name": "test_tool", "arguments": "{}"},
                                }
                            ],
                        },
                    }
                ],
                "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
            }
        )

        # Second call: final response
        second_response = create_mock_context_manager(
            {
                "id": "gen-124",
                "model": "test-model",
                "created": 1234567891,
                "object": "chat.completion",
                "choices": [
                    {"finish_reason": "stop", "message": {"role": "assistant", "content": "Done"}}
                ],
                "usage": {"prompt_tokens": 15, "completion_tokens": 3, "total_tokens": 18},
            }
        )

        mock_session = AsyncMock()
        mock_session.post = Mock(side_effect=[first_response, second_response])
        mock_get_session.return_value = mock_session

        result = await chat_node.execute(inputs)
        # Should still execute tools even though finish_reason is None
        assert len(result["tool_history"]) == 1


@pytest.mark.asyncio
async def test_tool_calling_stops_on_error_finish_reason(chat_node):
    """Test that tool calling stops when finish_reason is error."""
    chat_node.params["max_tool_iters"] = 2
    inputs = {
        "messages": [{"role": "user", "content": "Use tool"}],
        "tools": [{"type": "function", "function": {"name": "test_tool", "parameters": {}}}],
    }

    with (
        patch(
            "nodes.core.llm.open_router_chat_node.OpenRouterChat._get_session"
        ) as mock_get_session,
        patch("core.api_key_vault.APIKeyVault.get") as mock_get,
    ):
        mock_get.return_value = "fake-api-key"

        # Response with error finish_reason
        error_response = create_mock_context_manager(
            {
                "id": "gen-123",
                "model": "test-model",
                "created": 1234567890,
                "object": "chat.completion",
                "choices": [
                    {
                        "finish_reason": "error",
                        "message": {"role": "assistant", "content": ""},
                    }
                ],
                "usage": {"prompt_tokens": 10, "completion_tokens": 0, "total_tokens": 10},
            }
        )

        mock_session = AsyncMock()
        mock_session.post = Mock(return_value=error_response)
        mock_get_session.return_value = mock_session

        result = await chat_node.execute(inputs)
        # Should return early with error
        assert result["message"]["content"] == "API returned error"
        assert "error" in result["metrics"]


@pytest.mark.asyncio
async def test_json_mode(chat_node):
    """Test JSON mode parsing."""
    chat_node.params["json_mode"] = True
    inputs = {"messages": [{"role": "user", "content": "Hello"}]}

    with (
        patch(
            "nodes.core.llm.open_router_chat_node.OpenRouterChat._get_session"
        ) as mock_get_session,
        patch("core.api_key_vault.APIKeyVault.get") as mock_get,
    ):
        mock_get.return_value = "fake-api-key"

        response_data = {
            "id": "gen-123",
            "model": "test-model",
            "created": 1234567890,
            "object": "chat.completion",
            "choices": [
                {
                    "finish_reason": "stop",
                    "message": {"role": "assistant", "content": '{"key": "value"}'},
                }
            ],
            "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
        }
        mock_response_context = create_mock_context_manager(response_data)

        mock_session = AsyncMock()
        mock_session.post = Mock(return_value=mock_response_context)
        mock_get_session.return_value = mock_session

        result = await chat_node.execute(inputs)
        assert result["message"]["content"] == {"key": "value"}


@pytest.mark.asyncio
async def test_error_handling(chat_node):
    """Test error handling for API failures."""
    inputs = {"messages": [{"role": "user", "content": "Hello"}]}

    with (
        patch(
            "nodes.core.llm.open_router_chat_node.OpenRouterChat._get_session"
        ) as mock_get_session,
        patch("core.api_key_vault.APIKeyVault.get") as mock_get,
    ):
        mock_get.return_value = "fake-api-key"

        mock_session = AsyncMock()
        mock_session.post = Mock(side_effect=Exception("API Error"))
        mock_get_session.return_value = mock_session

        with pytest.raises(NodeExecutionError) as excinfo:
            await chat_node.execute(inputs)
        assert "Execution failed" in str(excinfo.value)
        assert str(excinfo.value.original_exc) == "API Error"


@pytest.mark.asyncio
async def test_message_building(chat_node):
    """Test message building from prompt and system."""
    inputs = {"prompt": "User prompt", "system": "System instruction"}

    with (
        patch(
            "nodes.core.llm.open_router_chat_node.OpenRouterChat._get_session"
        ) as mock_get_session,
        patch("core.api_key_vault.APIKeyVault.get") as mock_get,
    ):
        mock_get.return_value = "fake-api-key"

        response_data = {
            "id": "gen-123",
            "model": "test-model",
            "created": 1234567890,
            "object": "chat.completion",
            "choices": [
                {"finish_reason": "stop", "message": {"role": "assistant", "content": "Response"}}
            ],
            "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
        }
        mock_response_context = create_mock_context_manager(response_data)

        mock_session = AsyncMock()
        mock_session.post = Mock(return_value=mock_response_context)
        mock_get_session.return_value = mock_session

        await chat_node.execute(inputs)
        call_args = mock_session.post.call_args
        request_body = call_args.kwargs["json"]
        messages = request_body["messages"]
        assert len(messages) == 2
        assert messages[0]["role"] == "system"
        assert messages[0]["content"] == "System instruction"
        assert messages[1]["role"] == "user"
        assert messages[1]["content"] == "User prompt"


@pytest.mark.asyncio
async def test_missing_api_key(chat_node):
    """Test handling of missing API key."""
    inputs = {"messages": [{"role": "user", "content": "Hello"}]}

    with patch("core.api_key_vault.APIKeyVault.get") as mock_get:
        mock_get.return_value = None

        result = await chat_node.execute(inputs)
        assert "error" in result["metrics"]
        assert "OPENROUTER_API_KEY not found" in result["metrics"]["error"]


@pytest.mark.asyncio
async def test_empty_tool_calls_list(chat_node):
    """Test handling of empty tool_calls list."""
    chat_node.params["max_tool_iters"] = 1
    inputs = {
        "messages": [{"role": "user", "content": "Hello"}],
        "tools": [{"type": "function", "function": {"name": "test_tool", "parameters": {}}}],
    }

    with (
        patch(
            "nodes.core.llm.open_router_chat_node.OpenRouterChat._get_session"
        ) as mock_get_session,
        patch("core.api_key_vault.APIKeyVault.get") as mock_get,
    ):
        mock_get.return_value = "fake-api-key"

        # Response with empty tool_calls list
        response_data = {
            "id": "gen-123",
            "model": "test-model",
            "created": 1234567890,
            "object": "chat.completion",
            "choices": [
                {
                    "finish_reason": "stop",
                    "message": {"role": "assistant", "content": "Done", "tool_calls": []},
                }
            ],
            "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
        }
        mock_response_context = create_mock_context_manager(response_data)

        mock_session = AsyncMock()
        mock_session.post = Mock(return_value=mock_response_context)
        mock_get_session.return_value = mock_session

        result = await chat_node.execute(inputs)
        # Should stop iteration with empty tool_calls
        assert len(result["tool_history"]) == 0
        assert result["message"]["content"] == "Done"


@pytest.mark.asyncio
async def test_max_tool_iters_limit(chat_node):
    """Test that max_tool_iters limit is respected."""
    chat_node.params["max_tool_iters"] = 2
    inputs = {
        "messages": [{"role": "user", "content": "Use tool"}],
        "tools": [{"type": "function", "function": {"name": "test_tool", "parameters": {}}}],
    }

    with (
        patch(
            "nodes.core.llm.open_router_chat_node.OpenRouterChat._get_session"
        ) as mock_get_session,
        patch("core.api_key_vault.APIKeyVault.get") as mock_get,
        patch("nodes.core.llm.open_router_chat_node.get_tool_handler") as mock_handler,
    ):
        mock_get.return_value = "fake-api-key"
        mock_handler.return_value = AsyncMock(return_value={"result": "executed"})

        # Multiple tool calling responses - need different IDs for each round
        tool_response_round1 = create_mock_context_manager(
            {
                "id": "gen-123",
                "model": "test-model",
                "created": 1234567890,
                "object": "chat.completion",
                "choices": [
                    {
                        "finish_reason": "tool_calls",
                        "message": {
                            "role": "assistant",
                            "tool_calls": [
                                {
                                    "id": "call_123",
                                    "type": "function",
                                    "function": {"name": "test_tool", "arguments": "{}"},
                                }
                            ],
                        },
                    }
                ],
                "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
            }
        )

        tool_response_round2 = create_mock_context_manager(
            {
                "id": "gen-124",
                "model": "test-model",
                "created": 1234567891,
                "object": "chat.completion",
                "choices": [
                    {
                        "finish_reason": "tool_calls",
                        "message": {
                            "role": "assistant",
                            "tool_calls": [
                                {
                                    "id": "call_124",
                                    "type": "function",
                                    "function": {"name": "test_tool", "arguments": "{}"},
                                }
                            ],
                        },
                    }
                ],
                "usage": {"prompt_tokens": 15, "completion_tokens": 5, "total_tokens": 20},
            }
        )

        final_response = create_mock_context_manager(
            {
                "id": "gen-125",
                "model": "test-model",
                "created": 1234567892,
                "object": "chat.completion",
                "choices": [
                    {"finish_reason": "stop", "message": {"role": "assistant", "content": "Done"}}
                ],
                "usage": {"prompt_tokens": 20, "completion_tokens": 3, "total_tokens": 23},
            }
        )

        # Should make max_tool_iters (2) calls during tool execution, plus 1 final call
        mock_session = AsyncMock()
        mock_session.post = Mock(
            side_effect=[tool_response_round1, tool_response_round2, final_response]
        )
        mock_get_session.return_value = mock_session

        result = await chat_node.execute(inputs)
        # Should execute exactly 2 tool calls
        assert len(result["tool_history"]) == 2


@pytest.mark.asyncio
async def test_seed_mode_random(chat_node):
    """Test random seed mode."""
    chat_node.params["seed_mode"] = "random"
    inputs = {"messages": [{"role": "user", "content": "Hello"}]}

    with (
        patch(
            "nodes.core.llm.open_router_chat_node.OpenRouterChat._get_session"
        ) as mock_get_session,
        patch("core.api_key_vault.APIKeyVault.get") as mock_get,
    ):
        mock_get.return_value = "fake-api-key"

        response_data = {
            "id": "gen-123",
            "model": "test-model",
            "created": 1234567890,
            "object": "chat.completion",
            "choices": [
                {"finish_reason": "stop", "message": {"role": "assistant", "content": "Response"}}
            ],
            "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
        }
        mock_response_context = create_mock_context_manager(response_data)

        mock_session = AsyncMock()
        mock_session.post = Mock(return_value=mock_response_context)
        mock_get_session.return_value = mock_session

        await chat_node.execute(inputs)
        call_args = mock_session.post.call_args
        request_body = call_args.kwargs["json"]
        # Seed should be set (random integer)
        assert "seed" in request_body
        assert isinstance(request_body["seed"], int)


@pytest.mark.asyncio
async def test_seed_mode_increment(chat_node):
    """Test increment seed mode."""
    chat_node.params["seed_mode"] = "increment"
    chat_node.params["seed"] = 10
    inputs = {"messages": [{"role": "user", "content": "Hello"}]}

    with (
        patch(
            "nodes.core.llm.open_router_chat_node.OpenRouterChat._get_session"
        ) as mock_get_session,
        patch("core.api_key_vault.APIKeyVault.get") as mock_get,
    ):
        mock_get.return_value = "fake-api-key"

        response_data = {
            "id": "gen-123",
            "model": "test-model",
            "created": 1234567890,
            "object": "chat.completion",
            "choices": [
                {"finish_reason": "stop", "message": {"role": "assistant", "content": "Response"}}
            ],
            "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
        }
        mock_response_context = create_mock_context_manager(response_data)

        mock_session = AsyncMock()
        mock_session.post = Mock(return_value=mock_response_context)
        mock_get_session.return_value = mock_session

        # First call
        await chat_node.execute(inputs)
        call_args = mock_session.post.call_args
        request_body = call_args.kwargs["json"]
        assert request_body["seed"] == 10

        # Second call should increment
        await chat_node.execute(inputs)
        call_args = mock_session.post.call_args
        request_body = call_args.kwargs["json"]
        assert request_body["seed"] == 11


@pytest.mark.asyncio
async def test_empty_messages_error(chat_node):
    """Test error handling when no messages or prompt provided."""
    inputs = {"messages": None}

    result = await chat_node.execute(inputs)
    assert "error" in result["metrics"]
    assert "No messages or prompt provided" in result["metrics"]["error"]


@pytest.mark.asyncio
async def test_collect_tools_multi_input(chat_node):
    """Test collecting tools from multiple inputs."""
    inputs = {
        "messages": [{"role": "user", "content": "Hello"}],
        "tool": [
            {"type": "function", "function": {"name": "tool1", "parameters": {}}},
            {"type": "function", "function": {"name": "tool2", "parameters": {}}},
        ],
    }

    tools = chat_node._collect_tools(inputs)
    assert len(tools) == 2
    assert tools[0]["function"]["name"] == "tool1"
    assert tools[1]["function"]["name"] == "tool2"


@pytest.mark.asyncio
async def test_empty_tools_handling(chat_node):
    """Test handling when no tools are provided."""
    inputs = {"messages": [{"role": "user", "content": "Hello"}]}

    with (
        patch(
            "nodes.core.llm.open_router_chat_node.OpenRouterChat._get_session"
        ) as mock_get_session,
        patch("core.api_key_vault.APIKeyVault.get") as mock_get,
    ):
        mock_get.return_value = "fake-api-key"

        response_data = {
            "id": "gen-123",
            "model": "test-model",
            "created": 1234567890,
            "object": "chat.completion",
            "choices": [
                {"finish_reason": "stop", "message": {"role": "assistant", "content": "Response"}}
            ],
            "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
        }
        mock_response_context = create_mock_context_manager(response_data)

        mock_session = AsyncMock()
        mock_session.post = Mock(return_value=mock_response_context)
        mock_get_session.return_value = mock_session

        result = await chat_node.execute(inputs)
        assert result["message"]["content"] == "Response"
        assert len(result["tool_history"]) == 0


@pytest.mark.asyncio
async def test_system_input_as_dict(chat_node):
    """Test system input provided as dictionary."""
    inputs = {
        "prompt": "User message",
        "system": {"role": "system", "content": "You are a helpful assistant"},
    }

    with (
        patch(
            "nodes.core.llm.open_router_chat_node.OpenRouterChat._get_session"
        ) as mock_get_session,
        patch("core.api_key_vault.APIKeyVault.get") as mock_get,
    ):
        mock_get.return_value = "fake-api-key"

        response_data = {
            "id": "gen-123",
            "model": "test-model",
            "created": 1234567890,
            "object": "chat.completion",
            "choices": [
                {"finish_reason": "stop", "message": {"role": "assistant", "content": "Response"}}
            ],
            "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
        }
        mock_response_context = create_mock_context_manager(response_data)

        mock_session = AsyncMock()
        mock_session.post = Mock(return_value=mock_response_context)
        mock_get_session.return_value = mock_session

        await chat_node.execute(inputs)
        call_args = mock_session.post.call_args
        request_body = call_args.kwargs["json"]
        messages = request_body["messages"]
        assert len(messages) == 2
        assert messages[0]["role"] == "system"
        assert messages[0]["content"] == "You are a helpful assistant"


@pytest.mark.asyncio
async def test_tool_execution_timeout(chat_node):
    """Test tool execution timeout handling."""
    chat_node.params["max_tool_iters"] = 1
    inputs = {
        "messages": [{"role": "user", "content": "Use tool"}],
        "tools": [{"type": "function", "function": {"name": "slow_tool", "parameters": {}}}],
    }

    async def slow_handler(args, ctx):
        await asyncio.sleep(20)  # Simulate timeout
        return {"result": "never_reached"}

    with (
        patch(
            "nodes.core.llm.open_router_chat_node.OpenRouterChat._get_session"
        ) as mock_get_session,
        patch("core.api_key_vault.APIKeyVault.get") as mock_get,
        patch("nodes.core.llm.open_router_chat_node.get_tool_handler") as mock_handler,
    ):
        mock_get.return_value = "fake-api-key"
        mock_handler.return_value = slow_handler

        tool_response = create_mock_context_manager(
            {
                "id": "gen-123",
                "model": "test-model",
                "created": 1234567890,
                "object": "chat.completion",
                "choices": [
                    {
                        "finish_reason": "tool_calls",
                        "message": {
                            "role": "assistant",
                            "tool_calls": [
                                {
                                    "id": "call_123",
                                    "type": "function",
                                    "function": {"name": "slow_tool", "arguments": "{}"},
                                }
                            ],
                        },
                    }
                ],
                "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
            }
        )

        final_response = create_mock_context_manager(
            {
                "id": "gen-124",
                "model": "test-model",
                "created": 1234567891,
                "object": "chat.completion",
                "choices": [
                    {"finish_reason": "stop", "message": {"role": "assistant", "content": "Done"}}
                ],
                "usage": {"prompt_tokens": 15, "completion_tokens": 3, "total_tokens": 18},
            }
        )

        mock_session = AsyncMock()
        mock_session.post = Mock(side_effect=[tool_response, final_response])
        mock_get_session.return_value = mock_session

        result = await chat_node.execute(inputs)
        # Should have timeout error in tool history
        assert len(result["tool_history"]) == 1
        assert "error" in result["tool_history"][0]["result"]
        assert "timeout" in result["tool_history"][0]["result"]["error"]


@pytest.mark.asyncio
async def test_tool_execution_exception(chat_node):
    """Test tool execution exception handling."""
    chat_node.params["max_tool_iters"] = 1
    inputs = {
        "messages": [{"role": "user", "content": "Use tool"}],
        "tools": [{"type": "function", "function": {"name": "error_tool", "parameters": {}}}],
    }

    async def error_handler(args, ctx):
        raise ValueError("Tool error")

    with (
        patch(
            "nodes.core.llm.open_router_chat_node.OpenRouterChat._get_session"
        ) as mock_get_session,
        patch("core.api_key_vault.APIKeyVault.get") as mock_get,
        patch("nodes.core.llm.open_router_chat_node.get_tool_handler") as mock_handler,
    ):
        mock_get.return_value = "fake-api-key"
        mock_handler.return_value = error_handler

        tool_response = create_mock_context_manager(
            {
                "id": "gen-123",
                "model": "test-model",
                "created": 1234567890,
                "object": "chat.completion",
                "choices": [
                    {
                        "finish_reason": "tool_calls",
                        "message": {
                            "role": "assistant",
                            "tool_calls": [
                                {
                                    "id": "call_123",
                                    "type": "function",
                                    "function": {"name": "error_tool", "arguments": "{}"},
                                }
                            ],
                        },
                    }
                ],
                "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
            }
        )

        final_response = create_mock_context_manager(
            {
                "id": "gen-124",
                "model": "test-model",
                "created": 1234567891,
                "object": "chat.completion",
                "choices": [
                    {"finish_reason": "stop", "message": {"role": "assistant", "content": "Done"}}
                ],
                "usage": {"prompt_tokens": 15, "completion_tokens": 3, "total_tokens": 18},
            }
        )

        mock_session = AsyncMock()
        mock_session.post = Mock(side_effect=[tool_response, final_response])
        mock_get_session.return_value = mock_session

        result = await chat_node.execute(inputs)
        assert len(result["tool_history"]) == 1
        assert "error" in result["tool_history"][0]["result"]
        assert result["tool_history"][0]["result"]["error"] == "exception"


@pytest.mark.asyncio
async def test_tool_arguments_as_string(chat_node):
    """Test tool arguments provided as JSON string."""
    chat_node.params["max_tool_iters"] = 1
    inputs = {
        "messages": [{"role": "user", "content": "Use tool"}],
        "tools": [{"type": "function", "function": {"name": "test_tool", "parameters": {}}}],
    }

    with (
        patch(
            "nodes.core.llm.open_router_chat_node.OpenRouterChat._get_session"
        ) as mock_get_session,
        patch("core.api_key_vault.APIKeyVault.get") as mock_get,
        patch("nodes.core.llm.open_router_chat_node.get_tool_handler") as mock_handler,
    ):
        mock_get.return_value = "fake-api-key"
        mock_handler.return_value = AsyncMock(return_value={"result": "executed"})

        tool_response = create_mock_context_manager(
            {
                "id": "gen-123",
                "model": "test-model",
                "created": 1234567890,
                "object": "chat.completion",
                "choices": [
                    {
                        "finish_reason": "tool_calls",
                        "message": {
                            "role": "assistant",
                            "tool_calls": [
                                {
                                    "id": "call_123",
                                    "type": "function",
                                    "function": {
                                        "name": "test_tool",
                                        "arguments": '{"key": "value"}',
                                    },
                                }
                            ],
                        },
                    }
                ],
                "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
            }
        )

        final_response = create_mock_context_manager(
            {
                "id": "gen-124",
                "model": "test-model",
                "created": 1234567891,
                "object": "chat.completion",
                "choices": [
                    {"finish_reason": "stop", "message": {"role": "assistant", "content": "Done"}}
                ],
                "usage": {"prompt_tokens": 15, "completion_tokens": 3, "total_tokens": 18},
            }
        )

        mock_session = AsyncMock()
        mock_session.post = Mock(side_effect=[tool_response, final_response])
        mock_get_session.return_value = mock_session

        result = await chat_node.execute(inputs)
        assert len(result["tool_history"]) == 1
        # Verify the handler was called with parsed dict
        assert mock_handler.return_value.called


@pytest.mark.asyncio
async def test_web_search_disabled(chat_node):
    """Test web search disabled behavior."""
    chat_node.params["web_search_enabled"] = False
    inputs = {"messages": [{"role": "user", "content": "Hello"}]}

    with (
        patch(
            "nodes.core.llm.open_router_chat_node.OpenRouterChat._get_session"
        ) as mock_get_session,
        patch("core.api_key_vault.APIKeyVault.get") as mock_get,
    ):
        mock_get.return_value = "fake-api-key"

        response_data = {
            "id": "gen-123",
            "model": "test-model",
            "created": 1234567890,
            "object": "chat.completion",
            "choices": [
                {"finish_reason": "stop", "message": {"role": "assistant", "content": "Response"}}
            ],
            "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
        }
        mock_response_context = create_mock_context_manager(response_data)

        mock_session = AsyncMock()
        mock_session.post = Mock(return_value=mock_response_context)
        mock_get_session.return_value = mock_session

        await chat_node.execute(inputs)
        call_args = mock_session.post.call_args
        request_body = call_args.kwargs["json"]
        # Model should not have :online suffix
        assert not request_body["model"].endswith(":online")


@pytest.mark.asyncio
async def test_model_already_has_online_suffix(chat_node):
    """Test model that already has :online suffix."""
    chat_node.params["model"] = "test-model:online"
    inputs = {"messages": [{"role": "user", "content": "Hello"}]}

    with (
        patch(
            "nodes.core.llm.open_router_chat_node.OpenRouterChat._get_session"
        ) as mock_get_session,
        patch("core.api_key_vault.APIKeyVault.get") as mock_get,
    ):
        mock_get.return_value = "fake-api-key"

        response_data = {
            "id": "gen-123",
            "model": "test-model",
            "created": 1234567890,
            "object": "chat.completion",
            "choices": [
                {"finish_reason": "stop", "message": {"role": "assistant", "content": "Response"}}
            ],
            "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
        }
        mock_response_context = create_mock_context_manager(response_data)

        mock_session = AsyncMock()
        mock_session.post = Mock(return_value=mock_response_context)
        mock_get_session.return_value = mock_session

        await chat_node.execute(inputs)
        call_args = mock_session.post.call_args
        request_body = call_args.kwargs["json"]
        # Should not add another :online suffix
        assert request_body["model"] == "test-model:online"


@pytest.mark.asyncio
async def test_ensure_assistant_role(chat_node):
    """Test ensuring assistant role in message."""
    message = {"content": "test"}
    chat_node._ensure_assistant_role_inplace(message)
    assert message["role"] == "assistant"


@pytest.mark.asyncio
async def test_is_complete_tool_call(chat_node):
    """Test checking if tool call is complete."""
    # Complete call with name and arguments
    complete_call = {"function": {"name": "test", "arguments": {"key": "value"}}}
    result = chat_node._is_complete_tool_call(complete_call)
    assert result is not None
    assert bool(result) is True

    # Incomplete call - missing arguments
    incomplete_call = {"function": {"name": "test"}}
    result = chat_node._is_complete_tool_call(incomplete_call)
    assert bool(result) is False

    # Empty call
    empty_call = {}
    result = chat_node._is_complete_tool_call(empty_call)
    assert bool(result) is False


@pytest.mark.asyncio
async def test_parse_tool_calls_from_message(chat_node):
    """Test parsing tool calls from message content."""
    message = {
        "content": "_TOOL_WEB_SEARCH_: test query _RESULT_: some result",
        "role": "assistant",
    }
    chat_node._parse_tool_calls_from_message(message)
    assert "tool_calls" in message
    assert len(message["tool_calls"]) == 1
    assert message["tool_calls"][0]["function"]["name"] == "web_search"
    assert message["tool_calls"][0]["function"]["arguments"]["query"] == "test query"


@pytest.mark.asyncio
async def test_parse_tool_calls_with_existing_tool_calls(chat_node):
    """Test parsing when message already has tool_calls."""
    message = {
        "content": "test",
        "role": "assistant",
        "tool_calls": [{"function": {"name": "existing", "arguments": {"key": "value"}}}],
    }
    chat_node._parse_tool_calls_from_message(message)
    assert len(message["tool_calls"]) == 1
    assert message["tool_name"] == "existing"


@pytest.mark.asyncio
async def test_generation_stats_with_cost(chat_node):
    """Test fetching generation stats with cost information."""
    inputs = {"messages": [{"role": "user", "content": "Hello"}]}

    with (
        patch(
            "nodes.core.llm.open_router_chat_node.OpenRouterChat._get_session"
        ) as mock_get_session,
        patch("core.api_key_vault.APIKeyVault.get") as mock_get,
    ):
        mock_get.return_value = "fake-api-key"

        response_data = {
            "id": "gen-123",
            "model": "test-model",
            "created": 1234567890,
            "object": "chat.completion",
            "choices": [
                {"finish_reason": "stop", "message": {"role": "assistant", "content": "Response"}}
            ],
            "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
        }
        mock_response_context = create_mock_context_manager(response_data)

        # Mock generation stats endpoint
        gen_stats_response = create_mock_context_manager(
            {
                "data": {
                    "total_cost": 0.001,
                    "native_tokens_prompt": 10,
                    "native_tokens_completion": 5,
                    "latency": 500,
                    "generation_time": 400,
                }
            }
        )

        mock_session = AsyncMock()
        mock_session.post = Mock(return_value=mock_response_context)
        mock_session.get = Mock(return_value=gen_stats_response)
        mock_get_session.return_value = mock_session

        result = await chat_node.execute(inputs)
        # Should include generation stats
        assert "total_cost" in result["metrics"]
        assert result["metrics"]["total_cost"] == 0.001
        assert "latency" in result["metrics"]
        assert "generation_time" in result["metrics"]
