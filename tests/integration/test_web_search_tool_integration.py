import pytest
import os
from nodes.core.llm.web_search_tool_node import WebSearchTool as WebSearchToolNode
from services.tools.web_search import WebSearchTool
from services.tools.registry import get_tool_handler


# Test API key provided by user
TEST_API_KEY = "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"


@pytest.fixture(scope="module", autouse=True)
def setup_test_api_key():
    """Set up the test API key for integration tests."""
    original_key = os.environ.get("TAVILY_API_KEY")
    os.environ["TAVILY_API_KEY"] = TEST_API_KEY
    yield
    # Restore original key
    if original_key is not None:
        os.environ["TAVILY_API_KEY"] = original_key
    else:
        os.environ.pop("TAVILY_API_KEY", None)


@pytest.fixture
def web_search_tool_node():
    return WebSearchToolNode(id=1, params={
        "provider": "tavily",
        "default_k": 3,  # Use smaller number for faster tests
        "time_range": "month",
        "lang": "en",
        "require_api_key": True,
    })


@pytest.fixture
def web_search_tool():
    return WebSearchTool()


@pytest.mark.asyncio
async def test_web_search_tool_schema(web_search_tool):
    """Test that WebSearchTool returns a valid schema."""
    schema = web_search_tool.schema()

    assert isinstance(schema, dict)
    assert schema["type"] == "function"
    assert schema["function"]["name"] == "web_search"
    assert "description" in schema["function"]

    parameters = schema["function"]["parameters"]
    assert parameters["type"] == "object"
    assert "query" in parameters["properties"]
    assert "k" in parameters["properties"]
    assert "time_range" in parameters["properties"]
    assert "lang" in parameters["properties"]
    assert parameters["required"] == ["query"]


@pytest.mark.asyncio
async def test_web_search_tool_execute_basic_search(web_search_tool):
    """Test basic web search functionality with real API."""
    arguments = {
        "query": "Python programming language",
        "k": 2,  # Small number for faster test
        "time_range": "month",
        "lang": "en"
    }

    context = {
        "model": "test_model",
        "host": "localhost:11434",
        "credentials": {"tavily_api_key": lambda: os.environ.get("TAVILY_API_KEY")}
    }

    result = await web_search_tool.execute(arguments, context)

    assert isinstance(result, dict)
    assert "results" in result
    assert "used_provider" in result
    assert result["used_provider"] == "tavily"

    results = result["results"]
    assert isinstance(results, list)
    assert len(results) <= 2  # Should respect k parameter

    if results:  # Only check structure if we got results
        for item in results:
            assert isinstance(item, dict)
            assert "title" in item
            assert "url" in item
            assert "snippet" in item
            assert isinstance(item["title"], str)
            assert isinstance(item["url"], str)
            assert isinstance(item["snippet"], str)


@pytest.mark.asyncio
async def test_web_search_tool_execute_different_time_ranges(web_search_tool):
    """Test web search with different time ranges."""
    # Test the supported time ranges
    test_cases = [
        {"time_range": "day"},
        {"time_range": "week"},
        {"time_range": "month"}
    ]

    successful_ranges = []
    for case in test_cases:
        arguments = {
            "query": "artificial intelligence news",
            "k": 1,
            "lang": "en",
            **case
        }

        context = {
            "model": "test_model",
            "host": "localhost:11434",
            "credentials": {"tavily_api_key": lambda: os.environ.get("TAVILY_API_KEY")}
        }

        result = await web_search_tool.execute(arguments, context)

        assert isinstance(result, dict)
        # If the API doesn't support this time range, it might return an error
        # That's okay - we just want to test that the tool handles different ranges
        if "results" in result:
            assert "used_provider" in result
            assert result["used_provider"] == "tavily"
            successful_ranges.append(case["time_range"])
        elif "error" in result:
            # API error is acceptable for unsupported time ranges
            assert "message" in result

    # At least one time range should work
    assert len(successful_ranges) > 0, f"No time ranges worked. Tested: {test_cases}"


@pytest.mark.asyncio
async def test_web_search_tool_execute_different_languages(web_search_tool):
    """Test web search with different language codes."""
    test_cases = [{"lang": l} for l in ["en", "es", "fr", "de"]]

    successful_langs = []
    for case in test_cases:
        arguments = {
            "query": "machine learning",
            "k": 1,
            "time_range": "month",
            **case
        }

        context = {
            "model": "test_model",
            "host": "localhost:11434",
            "credentials": {"tavily_api_key": lambda: os.environ.get("TAVILY_API_KEY")}
        }

        result = await web_search_tool.execute(arguments, context)

        assert isinstance(result, dict)
        if "results" in result:
            assert "used_provider" in result
            assert result["used_provider"] == "tavily"
            successful_langs.append(case["lang"])
        elif "error" in result:
            assert "message" in result

    assert len(successful_langs) > 0, f"No languages worked. Tested: {[c['lang'] for c in test_cases]}"


@pytest.mark.asyncio
async def test_web_search_tool_execute_different_k_values(web_search_tool):
    """Test web search with different k values."""
    test_cases = [1, 3, 5, 10]

    for k in test_cases:
        arguments = {
            "query": "quantum computing",
            "k": k,
            "time_range": "month",
            "lang": "en"
        }

        context = {
            "model": "test_model",
            "host": "localhost:11434",
            "credentials": {"tavily_api_key": lambda: os.environ.get("TAVILY_API_KEY")}
        }

        result = await web_search_tool.execute(arguments, context)

        assert isinstance(result, dict)
        assert "results" in result
        assert "used_provider" in result
        assert result["used_provider"] == "tavily"

        results = result["results"]
        assert isinstance(results, list)
        assert len(results) <= k


@pytest.mark.asyncio
async def test_web_search_tool_execute_empty_query(web_search_tool):
    """Test web search with empty query."""
    arguments = {
        "query": "",
        "k": 2,
        "time_range": "month",
        "lang": "en"
    }

    context = {
        "model": "test_model",
        "host": "localhost:11434",
        "credentials": {"tavily_api_key": lambda: os.environ.get("TAVILY_API_KEY")}
    }

    result = await web_search_tool.execute(arguments, context)

    assert isinstance(result, dict)
    assert "error" in result
    assert result["error"] == "invalid_arguments"
    assert "query" in result["message"].lower()


@pytest.mark.asyncio
async def test_web_search_tool_execute_missing_query(web_search_tool):
    """Test web search with missing query."""
    arguments = {
        "k": 2,
        "time_range": "month",
        "lang": "en"
    }

    context = {
        "model": "test_model",
        "host": "localhost:11434",
        "credentials": {"tavily_api_key": lambda: os.environ.get("TAVILY_API_KEY")}
    }

    result = await web_search_tool.execute(arguments, context)

    assert isinstance(result, dict)
    assert "error" in result
    assert result["error"] == "invalid_arguments"
    assert "query" in result["message"].lower()


@pytest.mark.asyncio
async def test_web_search_tool_execute_whitespace_query(web_search_tool):
    """Test web search with whitespace-only query."""
    arguments = {
        "query": "   ",
        "k": 2,
        "time_range": "month",
        "lang": "en"
    }

    context = {
        "model": "test_model",
        "host": "localhost:11434",
        "credentials": {"tavily_api_key": lambda: os.environ.get("TAVILY_API_KEY")}
    }

    result = await web_search_tool.execute(arguments, context)

    assert isinstance(result, dict)
    assert "error" in result
    assert result["error"] == "invalid_arguments"
    assert "query" in result["message"].lower()


@pytest.mark.asyncio
async def test_web_search_tool_node_integration(web_search_tool_node):
    """Test the WebSearchToolNode integration."""
    api_key = os.environ.get("TAVILY_API_KEY")
    result = await web_search_tool_node.execute({"api_key": api_key})

    assert "tool" in result
    tool_schema = result["tool"]

    # Verify the tool schema is properly configured
    assert tool_schema["type"] == "function"
    assert tool_schema["function"]["name"] == "web_search"

    props = tool_schema["function"]["parameters"]["properties"]
    assert props["k"]["default"] == 3  # Our custom value
    assert props["time_range"]["default"] == "month"
    assert props["lang"]["default"] == "en"


@pytest.mark.asyncio
async def test_web_search_tool_via_registry():
    """Test that web search tool is accessible via the registry."""
    handler = get_tool_handler("web_search")

    # Note: Tool registration is handled by WebSearchToolNode, not globally in registry
    # This test verifies the registry behavior for web_search tool
    assert handler is not None
    assert callable(handler)

    # Test the handler with real API call
    arguments = {
        "query": "open source software",
        "k": 2,
        "time_range": "month",
        "lang": "en"
    }

    context = {
        "model": "test_model",
        "host": "localhost:11434",
        "credentials": {"tavily_api_key": lambda: os.environ.get("TAVILY_API_KEY")}
    }

    result = await handler(arguments, context)

    # The handler should work now that credentials are provided in context
    assert isinstance(result, dict)
    assert "results" in result
    assert "used_provider" in result
    assert result["used_provider"] == "tavily"


@pytest.mark.asyncio
async def test_web_search_tool_complex_query(web_search_tool):
    """Test web search with a more complex query."""
    arguments = {
        "query": "latest developments in renewable energy technology 2024",
        "k": 3,
        "time_range": "year",
        "lang": "en"
    }

    context = {
        "model": "test_model",
        "host": "localhost:11434",
        "credentials": {"tavily_api_key": lambda: os.environ.get("TAVILY_API_KEY")}
    }

    result = await web_search_tool.execute(arguments, context)

    assert isinstance(result, dict)
    assert "results" in result
    assert "used_provider" in result
    assert result["used_provider"] == "tavily"

    results = result["results"]
    assert isinstance(results, list)
    assert len(results) <= 3

    if results:
        # Check that results have meaningful content
        for item in results:
            assert len(item["title"]) > 0
            assert len(item["url"]) > 0
            assert len(item["snippet"]) > 0


@pytest.mark.asyncio
async def test_web_search_tool_error_handling_missing_api_key():
    """Test error handling when API key is missing."""
    # Create a tool instance
    tool = WebSearchTool()

    arguments = {
        "query": "test query",
        "k": 1,
        "time_range": "month",
        "lang": "en"
    }

    # Context without credentials
    context = {"model": "test_model", "host": "localhost:11434"}

    result = await tool.execute(arguments, context)

    assert isinstance(result, dict)
    assert "error" in result
    assert result["error"] == "missing_api_key"
    assert "TAVILY_API_KEY credential not available" in result["message"]


@pytest.mark.asyncio
async def test_web_search_tool_timeout_handling(web_search_tool):
    """Test timeout handling (simulate by setting very short timeout)."""
    # Set a very short timeout to force timeout behavior
    original_timeout = os.environ.get("WEB_SEARCH_TIMEOUT_S")
    os.environ["WEB_SEARCH_TIMEOUT_S"] = "1"

    try:
        arguments = {
            "query": "very long query that might timeout " * 100,  # Make it potentially slow
            "k": 10,
            "time_range": "year",
            "lang": "en"
        }

        context = {"model": "test_model", "host": "localhost:11434"}

        result = await web_search_tool.execute(arguments, context)

        # The result should either succeed or fail gracefully
        assert isinstance(result, dict)

        if "error" in result:
            # If it failed, it should be a proper error
            assert isinstance(result["message"], str)
        else:
            # If it succeeded, it should have results
            assert "results" in result
            assert "used_provider" in result

    finally:
        # Restore timeout
        if original_timeout:
            os.environ["WEB_SEARCH_TIMEOUT_S"] = original_timeout
        else:
            os.environ.pop("WEB_SEARCH_TIMEOUT_S", None)
