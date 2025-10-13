import pytest
from unittest.mock import AsyncMock, patch
from nodes.core.llm.open_router_chat_node import OpenRouterChatNode

@pytest.fixture
def chat_node():
    return OpenRouterChatNode(id=1, params={})

@pytest.mark.asyncio
async def test_execute_basic(chat_node):
    inputs = {
        "messages": [{"role": "user", "content": "Hello"}]
    }

    with patch("httpx.AsyncClient") as mock_client_class, patch("core.api_key_vault.APIKeyVault.get") as mock_get:
        from unittest.mock import Mock, AsyncMock
        mock_get.return_value = "fake-api-key"
        mock_client = AsyncMock()
        mock_response = Mock()
        mock_response.json.return_value = {
            "choices": [{"message": {"role": "assistant", "content": "Hello back"}}],
            "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15}
        }
        mock_response.raise_for_status.return_value = None
        mock_client.post.return_value = mock_response

        mock_client_class.return_value.__aenter__.return_value = mock_client
        mock_client_class.return_value.__aexit__.return_value = None

        result = await chat_node.execute(inputs)
        assert result["message"]["content"] == "Hello back"
        assert result["message"]["role"] == "assistant"
        assert result["metrics"]["prompt_tokens"] == 10
        assert result["metrics"]["completion_tokens"] == 5
        assert result["metrics"]["total_tokens"] == 15

@pytest.mark.asyncio
async def test_temperature_and_seed(chat_node):
    chat_node.params["temperature"] = 0.8
    chat_node.params["seed"] = 42
    inputs = {"messages": [{"role": "user", "content": "Hello"}]}

    with patch("httpx.AsyncClient") as mock_client_class, patch("core.api_key_vault.APIKeyVault.get") as mock_get:
        from unittest.mock import Mock, AsyncMock
        mock_get.return_value = "fake-api-key"
        mock_client = AsyncMock()
        mock_response = Mock()
        mock_response.json.return_value = {"choices": [{"message": {"role": "assistant", "content": "Response"}}]}
        mock_response.raise_for_status.return_value = None
        mock_client.post.return_value = mock_response

        mock_client_class.return_value.__aenter__.return_value = mock_client
        mock_client_class.return_value.__aexit__.return_value = None

        await chat_node.execute(inputs)
        call_args = mock_client.post.call_args
        request_body = call_args.kwargs["json"]
        assert request_body["temperature"] == 0.8
        assert request_body["seed"] == 42

@pytest.mark.asyncio
async def test_tool_choice(chat_node):
    chat_node.params["tool_choice"] = "none"
    inputs = {"messages": [{"role": "user", "content": "Hello"}], "tools": [{"type": "function", "function": {"name": "test"}}]}

    with patch("httpx.AsyncClient") as mock_client_class, patch("core.api_key_vault.APIKeyVault.get") as mock_get:
        from unittest.mock import Mock, AsyncMock
        mock_get.return_value = "fake-api-key"
        mock_client = AsyncMock()
        mock_response = Mock()
        mock_response.json.return_value = {"choices": [{"message": {"role": "assistant", "content": "Response"}}]}
        mock_response.raise_for_status.return_value = None
        mock_client.post.return_value = mock_response

        mock_client_class.return_value.__aenter__.return_value = mock_client
        mock_client_class.return_value.__aexit__.return_value = None

        await chat_node.execute(inputs)
        call_args = mock_client.post.call_args
        request_body = call_args.kwargs["json"]
        assert request_body["tool_choice"] == "none"

@pytest.mark.asyncio
async def test_json_mode(chat_node):
    chat_node.params["json_mode"] = True
    inputs = {"messages": [{"role": "user", "content": "Hello"}]}

    with patch("httpx.AsyncClient") as mock_client_class, patch("core.api_key_vault.APIKeyVault.get") as mock_get:
        from unittest.mock import Mock, AsyncMock
        mock_get.return_value = "fake-api-key"
        mock_client = AsyncMock()
        mock_response = Mock()
        mock_response.json.return_value = {"choices": [{"message": {"role": "assistant", "content": '{"key": "value"}'}}]}
        mock_response.raise_for_status.return_value = None
        mock_client.post.return_value = mock_response

        mock_client_class.return_value.__aenter__.return_value = mock_client
        mock_client_class.return_value.__aexit__.return_value = None

        result = await chat_node.execute(inputs)
        assert result["message"]["content"] == {"key": "value"}

@pytest.mark.asyncio
async def test_tool_calling(chat_node):
    chat_node.params["max_tool_iters"] = 1
    inputs = {
        "messages": [{"role": "user", "content": "Use tool"}],
        "tools": [{"type": "function", "function": {"name": "test_tool"}}]
    }

    with patch("httpx.AsyncClient") as mock_client_class, patch("core.api_key_vault.APIKeyVault.get") as mock_get, patch("services.tools.registry.get_tool_handler") as mock_handler:
        from unittest.mock import Mock, AsyncMock
        mock_get.return_value = "fake-api-key"
        mock_handler.return_value = AsyncMock(return_value={"result": "executed"})

        mock_client = AsyncMock()

        # First call: tool calls
        first_response = Mock()
        first_response.json.return_value = {
            "choices": [{"message": {"role": "assistant", "tool_calls": [{"id": "call_123", "function": {"name": "test_tool", "arguments": "{}"}}]}}]
        }
        first_response.raise_for_status.return_value = None

        # Second call: final response
        second_response = Mock()
        second_response.json.return_value = {"choices": [{"message": {"role": "assistant", "content": "Done"}}]}
        second_response.raise_for_status.return_value = None

        mock_client.post.side_effect = [first_response, second_response, second_response]

        mock_client_class.return_value.__aenter__.return_value = mock_client
        mock_client_class.return_value.__aexit__.return_value = None

        result = await chat_node.execute(inputs)
        assert len(result["tool_history"]) == 1
        assert result["tool_history"][0]["call"]["id"] == "call_123"
        assert result["tool_history"][0]["call"]["function"]["name"] == "test_tool"
        assert result["message"]["content"] == "Done"

@pytest.mark.asyncio
async def test_error_handling(chat_node):
    inputs = {"messages": [{"role": "user", "content": "Hello"}]}

    with patch("httpx.AsyncClient") as mock_client_class, patch("core.api_key_vault.APIKeyVault.get") as mock_get:
        from unittest.mock import AsyncMock
        mock_get.return_value = "fake-api-key"
        mock_client = AsyncMock()
        mock_client.post.side_effect = Exception("API Error")

        mock_client_class.return_value.__aenter__.return_value = mock_client
        mock_client_class.return_value.__aexit__.return_value = None

        result = await chat_node.execute(inputs)
        assert "error" in result["metrics"]
        assert result["metrics"]["error"] == "API Error"
        assert result["message"]["content"] == ""
        assert result["message"]["role"] == "assistant"

@pytest.mark.asyncio
async def test_message_building(chat_node):
    inputs = {
        "prompt": "User prompt",
        "system": "System instruction"
    }

    with patch("httpx.AsyncClient") as mock_client_class, patch("core.api_key_vault.APIKeyVault.get") as mock_get:
        from unittest.mock import Mock, AsyncMock
        mock_get.return_value = "fake-api-key"
        mock_client = AsyncMock()
        mock_response = Mock()
        mock_response.json.return_value = {"choices": [{"message": {"role": "assistant", "content": "Response"}}]}
        mock_response.raise_for_status.return_value = None
        mock_client.post.return_value = mock_response

        mock_client_class.return_value.__aenter__.return_value = mock_client
        mock_client_class.return_value.__aexit__.return_value = None

        await chat_node.execute(inputs)
        call_args = mock_client.post.call_args
        request_body = call_args.kwargs["json"]
        messages = request_body["messages"]
        assert len(messages) == 2
        assert messages[0]["role"] == "system"
        assert messages[0]["content"] == "System instruction"
        assert messages[1]["role"] == "user"
        assert messages[1]["content"] == "User prompt"

@pytest.mark.asyncio
async def test_missing_api_key(chat_node):
    inputs = {"messages": [{"role": "user", "content": "Hello"}]}

    with patch("core.api_key_vault.APIKeyVault.get") as mock_get:
        mock_get.return_value = None

        result = await chat_node.execute(inputs)
        assert "error" in result["metrics"]
        assert "OPENROUTER_API_KEY not found" in result["metrics"]["error"]
