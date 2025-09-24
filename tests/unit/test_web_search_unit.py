import pytest
import os
from typing import Dict, Any
from unittest.mock import AsyncMock, patch, MagicMock
import httpx

from services.tools.web_search import WebSearchTool, _tavily_search, _create_web_search_tool


class TestTavilySearchFunction:
    """Unit tests for the _tavily_search function."""

    @pytest.mark.asyncio
    async def test_tavily_search_missing_api_key(self):
        """Test _tavily_search with missing API key."""
        result = await _tavily_search("test query", 5, "month", "en", "general", 10, "")
        assert result == {"error": "missing_api_key", "message": "API key is required"}

    @pytest.mark.asyncio
    async def test_tavily_search_none_api_key(self):
        """Test _tavily_search with None API key."""
        result = await _tavily_search("test query", 5, "month", "en", "general", 10, None)
        assert result == {"error": "missing_api_key", "message": "API key is required"}

    @pytest.mark.asyncio
    async def test_tavily_search_successful_response(self):
        """Test _tavily_search with successful API response."""
        mock_response_data = {
            "results": [
                {
                    "title": "Test Title 1",
                    "url": "https://example1.com",
                    "content": "Test content 1",
                },
                {
                    "title": "Test Title 2",
                    "url": "https://example2.com",
                    "content": "Test content 2",
                },
                {
                    "title": "Test Title 3",
                    "url": "https://example3.com",
                    "snippet": "Test snippet 3",  # Note: uses 'snippet' instead of 'content'
                }
            ]
        }

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = mock_response_data
            mock_client.post.return_value = mock_response

            mock_client_class.return_value.__aenter__.return_value = mock_client
            mock_client_class.return_value.__aexit__.return_value = None

            result = await _tavily_search("test query", 5, "month", "en", "general", 10, "test_key")

            assert result == {
                "results": [
                    {"title": "Test Title 1", "url": "https://example1.com", "snippet": "Test content 1"},
                    {"title": "Test Title 2", "url": "https://example2.com", "snippet": "Test content 2"},
                    {"title": "Test Title 3", "url": "https://example3.com", "snippet": "Test snippet 3"},
                ],
                "used_provider": "tavily"
            }

            # Verify API call
            mock_client.post.assert_called_once()
            call_args = mock_client.post.call_args
            assert call_args[1]["json"]["query"] == "test query"
            assert call_args[1]["json"]["max_results"] == 5
            assert call_args[1]["json"]["time_range"] == "month"
            assert call_args[1]["json"]["topic"] == "general"
            assert call_args[1]["headers"]["Authorization"] == "Bearer test_key"

    @pytest.mark.asyncio
    async def test_tavily_search_k_parameter_bounds(self):
        """Test _tavily_search with k parameter at bounds."""
        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {"results": []}
            mock_client.post.return_value = mock_response

            mock_client_class.return_value.__aenter__.return_value = mock_client
            mock_client_class.return_value.__aexit__.return_value = None

            # Test k=0 (k or 5 means it becomes 5)
            result = await _tavily_search("query", 0, "month", "en", "general", 10, "key")
            assert mock_client.post.call_args[1]["json"]["max_results"] == 5

            # Reset mock
            mock_client.reset_mock()

            # Test k=15 (should become 10, max allowed)
            result = await _tavily_search("query", 15, "month", "en", "general", 10, "key")
            assert mock_client.post.call_args[1]["json"]["max_results"] == 10

    @pytest.mark.asyncio
    async def test_tavily_search_missing_result_fields(self):
        """Test _tavily_search with missing fields in results."""
        mock_response_data = {
            "results": [
                {"title": "Title only"},  # Missing url and content
                {"url": "https://example.com"},  # Missing title and content
                {"content": "Content only"},  # Missing title and url
                {},  # Completely empty
            ]
        }

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = mock_response_data
            mock_client.post.return_value = mock_response

            mock_client_class.return_value.__aenter__.return_value = mock_client
            mock_client_class.return_value.__aexit__.return_value = None

            result = await _tavily_search("query", 5, "month", "en", "general", 10, "key")

            expected_results = [
                {"title": "Title only", "url": "", "snippet": ""},
                {"title": "", "url": "https://example.com", "snippet": ""},
                {"title": "", "url": "", "snippet": "Content only"},
                {"title": "", "url": "", "snippet": ""},
            ]
            assert result["results"] == expected_results

    @pytest.mark.asyncio
    async def test_tavily_search_empty_results(self):
        """Test _tavily_search with empty results array."""
        mock_response_data = {"results": []}

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = mock_response_data
            mock_client.post.return_value = mock_response

            mock_client_class.return_value.__aenter__.return_value = mock_client
            mock_client_class.return_value.__aexit__.return_value = None

            result = await _tavily_search("query", 5, "month", "en", "general", 10, "key")
            assert result == {"results": [], "used_provider": "tavily"}

    @pytest.mark.asyncio
    async def test_tavily_search_missing_results_key(self):
        """Test _tavily_search when response has no results key."""
        mock_response_data = {"other_key": "value"}  # No 'results' key

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = mock_response_data
            mock_client.post.return_value = mock_response

            mock_client_class.return_value.__aenter__.return_value = mock_client
            mock_client_class.return_value.__aexit__.return_value = None

            result = await _tavily_search("query", 5, "month", "en", "general", 10, "key")
            assert result == {"results": [], "used_provider": "tavily"}

    @pytest.mark.asyncio
    async def test_tavily_search_http_error(self):
        """Test _tavily_search with HTTP error."""
        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_response = MagicMock()
            mock_response.status_code = 403
            mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
                "403 Forbidden", request=MagicMock(), response=mock_response
            )
            mock_client.post.return_value = mock_response

            mock_client_class.return_value.__aenter__.return_value = mock_client
            mock_client_class.return_value.__aexit__.return_value = None

            result = await _tavily_search("query", 5, "month", "en", "general", 10, "key")
            assert result["error"] == "provider_error"
            assert "403" in result["message"]

    @pytest.mark.asyncio
    async def test_tavily_search_network_error(self):
        """Test _tavily_search with network/connection error."""
        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.post.side_effect = httpx.ConnectError("Connection failed")

            mock_client_class.return_value.__aenter__.return_value = mock_client
            mock_client_class.return_value.__aexit__.return_value = None

            result = await _tavily_search("query", 5, "month", "en", "general", 10, "key")
            assert result["error"] == "provider_error"
            assert "Connection failed" in result["message"]

    @pytest.mark.asyncio
    async def test_tavily_search_json_error(self):
        """Test _tavily_search when response JSON parsing fails."""
        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.side_effect = ValueError("Invalid JSON")
            mock_client.post.return_value = mock_response

            mock_client_class.return_value.__aenter__.return_value = mock_client
            mock_client_class.return_value.__aexit__.return_value = None

            result = await _tavily_search("query", 5, "month", "en", "general", 10, "key")
            assert result["error"] == "provider_error"
            assert "Invalid JSON" in result["message"]

    @pytest.mark.asyncio
    async def test_tavily_search_default_parameters(self):
        """Test _tavily_search with None/default parameters."""
        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {"results": []}
            mock_client.post.return_value = mock_response

            mock_client_class.return_value.__aenter__.return_value = mock_client
            mock_client_class.return_value.__aexit__.return_value = None

            # Test with None values (should use defaults)
            result = await _tavily_search("query", None, None, None, None, 10, "key")

            call_args = mock_client.post.call_args
            payload = call_args[1]["json"]
            assert payload["max_results"] == 5  # Default k
            assert payload["time_range"] == "month"  # Default time_range
            assert payload["topic"] == "general"  # Default topic


class TestWebSearchTool:
    """Unit tests for the WebSearchTool class."""

    def test_web_search_tool_initialization(self):
        """Test WebSearchTool initialization."""
        tool = WebSearchTool()
        assert tool.name == "web_search"

    def test_web_search_tool_schema(self):
        """Test WebSearchTool schema structure."""
        tool = WebSearchTool()
        schema = tool.schema()

        assert schema["type"] == "function"
        assert schema["function"]["name"] == "web_search"
        assert "description" in schema["function"]

        parameters = schema["function"]["parameters"]
        assert parameters["type"] == "object"
        assert "query" in parameters["properties"]
        assert "k" in parameters["properties"]
        assert "time_range" in parameters["properties"]
        assert "topic" in parameters["properties"]
        assert "lang" in parameters["properties"]
        assert parameters["required"] == ["query"]

        # Check k parameter constraints
        k_param = parameters["properties"]["k"]
        assert k_param["minimum"] == 1
        assert k_param["maximum"] == 10
        assert k_param["default"] == 5

        # Check time_range enum
        time_range_param = parameters["properties"]["time_range"]
        assert time_range_param["enum"] == ["day", "week", "month", "year"]
        assert time_range_param["default"] == "month"

        # Check topic enum
        topic_param = parameters["properties"]["topic"]
        assert topic_param["enum"] == ["general", "news", "finance"]
        assert topic_param["default"] == "general"

    @pytest.mark.asyncio
    async def test_execute_missing_credentials(self):
        """Test execute with missing credentials."""
        tool = WebSearchTool()
        result = await tool.execute({}, {})

        assert result == {
            "error": "missing_api_key",
            "message": "TAVILY_API_KEY credential not available"
        }

    @pytest.mark.asyncio
    async def test_execute_missing_query(self):
        """Test execute with missing query."""
        tool = WebSearchTool()

        # Test with empty arguments
        result = await tool.execute({}, {"credentials": {"tavily_api_key": lambda: "key"}})
        assert result["error"] == "invalid_arguments"
        assert "query" in result["message"]

        # Test with None query
        result = await tool.execute({"query": None}, {"credentials": {"tavily_api_key": lambda: "key"}})
        assert result["error"] == "invalid_arguments"

        # Test with empty string query
        result = await tool.execute({"query": ""}, {"credentials": {"tavily_api_key": lambda: "key"}})
        assert result["error"] == "invalid_arguments"

        # Test with whitespace-only query
        result = await tool.execute({"query": "   "}, {"credentials": {"tavily_api_key": lambda: "key"}})
        assert result["error"] == "invalid_arguments"

    @pytest.mark.asyncio
    async def test_execute_non_string_query(self):
        """Test execute with non-string query."""
        tool = WebSearchTool()

        result = await tool.execute({"query": 123}, {"credentials": {"tavily_api_key": lambda: "key"}})
        assert result["error"] == "invalid_arguments"

    @pytest.mark.asyncio
    async def test_execute_successful_call(self):
        """Test successful execute call."""
        tool = WebSearchTool()

        expected_result = {"results": [], "used_provider": "tavily"}

        with patch("services.tools.web_search._tavily_search", new_callable=AsyncMock) as mock_search:
            mock_search.return_value = expected_result

            result = await tool.execute(
                {"query": "test query", "k": 3, "time_range": "week", "topic": "news", "lang": "fr"},
                {"credentials": {"tavily_api_key": lambda: "test_key"}}
            )

            assert result == expected_result

            # Verify _tavily_search was called with correct parameters
            mock_search.assert_called_once_with(
                query="test query",
                k=3,
                time_range="week",
                lang="fr",
                topic="news",
                timeout_s=12,  # Default timeout
                api_key="test_key"
            )

    @pytest.mark.asyncio
    async def test_execute_default_parameters(self):
        """Test execute with default parameter values."""
        tool = WebSearchTool()

        with patch("services.tools.web_search._tavily_search", new_callable=AsyncMock) as mock_search:
            mock_search.return_value = {"results": []}

            result = await tool.execute(
                {"query": "test"},
                {"credentials": {"tavily_api_key": lambda: "key"}}
            )

            # Verify defaults were used
            mock_search.assert_called_once_with(
                query="test",
                k=5,  # Default
                time_range="month",  # Default
                lang="en",  # Default
                topic="general",  # Default
                timeout_s=12,
                api_key="key"
            )

    @pytest.mark.asyncio
    async def test_execute_custom_timeout(self):
        """Test execute with custom timeout from environment."""
        tool = WebSearchTool()

        with patch("services.tools.web_search._tavily_search", new_callable=AsyncMock) as mock_search, \
             patch.dict(os.environ, {"WEB_SEARCH_TIMEOUT_S": "25"}):
            mock_search.return_value = {"results": []}

            await tool.execute(
                {"query": "test"},
                {"credentials": {"tavily_api_key": lambda: "key"}}
            )

            # Verify custom timeout was used
            call_args = mock_search.call_args
            assert call_args[1]["timeout_s"] == 25

    @pytest.mark.asyncio
    async def test_execute_invalid_timeout_env(self):
        """Test execute with invalid timeout environment variable."""
        tool = WebSearchTool()

        with patch("services.tools.web_search._tavily_search", new_callable=AsyncMock) as mock_search, \
             patch.dict(os.environ, {"WEB_SEARCH_TIMEOUT_S": "invalid"}):
            mock_search.return_value = {"results": []}

            await tool.execute(
                {"query": "test"},
                {"credentials": {"tavily_api_key": lambda: "key"}}
            )

            # Should fall back to default timeout (12) when env var is invalid
            call_args = mock_search.call_args
            assert call_args[1]["timeout_s"] == 12

    @pytest.mark.asyncio
    async def test_execute_credential_provider_failure(self):
        """Test execute when credential provider fails."""
        tool = WebSearchTool()

        def failing_provider():
            raise RuntimeError("Provider failed")

        result = await tool.execute(
            {"query": "test"},
            {"credentials": {"tavily_api_key": failing_provider}}
        )

        assert result == {
            "error": "missing_api_key",
            "message": "TAVILY_API_KEY credential not available"
        }

    @pytest.mark.asyncio
    async def test_execute_empty_arguments(self):
        """Test execute with None arguments."""
        tool = WebSearchTool()

        result = await tool.execute(None, {"credentials": {"tavily_api_key": lambda: "key"}})
        assert result["error"] == "invalid_arguments"

    @pytest.mark.asyncio
    async def test_execute_empty_context(self):
        """Test execute with None context."""
        tool = WebSearchTool()

        # The tool should handle None context gracefully
        result = await tool.execute({"query": "test"}, None)
        assert result["error"] == "missing_api_key"


class TestWebSearchToolFactory:
    """Tests for the web search tool factory."""

    def test_create_web_search_tool_factory(self):
        """Test that the factory creates WebSearchTool instances."""
        tool = _create_web_search_tool()
        assert isinstance(tool, WebSearchTool)
        assert tool.name == "web_search"

    def test_factory_creates_new_instances(self):
        """Test that factory creates new instances each time."""
        tool1 = _create_web_search_tool()
        tool2 = _create_web_search_tool()

        assert tool1 is not tool2
        assert isinstance(tool1, WebSearchTool)
        assert isinstance(tool2, WebSearchTool)


class TestWebSearchToolIntegration:
    """Integration tests for WebSearchTool with registry."""

    def test_tool_registration(self):
        """Test that web search tool factory works correctly."""
        # Test the factory function directly
        from services.tools.web_search import _create_web_search_tool

        tool = _create_web_search_tool()
        assert isinstance(tool, WebSearchTool)
        assert tool.name == "web_search"

        # Test schema
        schema = tool.schema()
        assert schema["type"] == "function"
        assert schema["function"]["name"] == "web_search"

        # Test that we can register the tool manually
        from services.tools.registry import register_tool_object

        # Clear any existing registration first
        from services.tools.registry import _TOOL_SCHEMAS, _TOOL_HANDLERS
        _TOOL_SCHEMAS.pop("web_search", None)
        _TOOL_HANDLERS.pop("web_search", None)

        # Register the tool
        register_tool_object(tool)

        # Now check registration worked
        from services.tools.registry import get_tool_schema, get_tool_handler
        schema = get_tool_schema("web_search")
        assert schema is not None
        assert schema["function"]["name"] == "web_search"

        handler = get_tool_handler("web_search")
        assert handler is not None
