import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from nodes.core.llm.web_search_tool_node import WebSearchToolNode


@pytest.fixture
def web_search_tool_node():
    return WebSearchToolNode(id=1, params={
        "provider": "tavily",
        "default_k": 5,
        "time_range": "month",
        "lang": "en",
        "require_api_key": True,
    })


@pytest.fixture
def mock_web_search_tool():
    """Mock WebSearchTool with schema method."""
    mock_tool = MagicMock()
    mock_tool.schema.return_value = {
        "type": "function",
        "function": {
            "name": "web_search",
            "description": "Search the web and return concise findings with sources.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search query"},
                    "k": {"type": "integer", "minimum": 1, "maximum": 10},
                    "time_range": {
                        "type": "string",
                        "enum": ["day", "week", "month", "year", "all"],
                    },
                    "lang": {"type": "string", "description": "Language code like en, fr"},
                },
                "required": ["query"],
            },
        },
    }
    return mock_tool


@pytest.mark.asyncio
async def test_execute_returns_tool_schema(web_search_tool_node, mock_web_search_tool):
    """Test that execute returns the tool schema with injected defaults."""
    with patch("nodes.core.llm.web_search_tool_node.WebSearchTool", return_value=mock_web_search_tool):
        result = await web_search_tool_node.execute({"api_key": "test_key"})

        assert "tool" in result
        tool_schema = result["tool"]

        # Verify it's the schema from the tool
        assert tool_schema["type"] == "function"
        assert tool_schema["function"]["name"] == "web_search"

        # Verify defaults are injected
        props = tool_schema["function"]["parameters"]["properties"]
        assert props["k"]["default"] == 5
        assert props["time_range"]["default"] == "month"
        assert props["lang"]["default"] == "en"


@pytest.mark.asyncio
async def test_execute_with_custom_params():
    """Test execute with custom parameter values."""
    node = WebSearchToolNode(id=2, params={
        "provider": "tavily",
        "default_k": 3,
        "time_range": "week",
        "lang": "fr",
        "require_api_key": True,
    })

    mock_tool = MagicMock()
    mock_tool.schema.return_value = {
        "type": "function",
        "function": {
            "name": "web_search",
            "description": "Search the web",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                    "k": {"type": "integer", "minimum": 1, "maximum": 10},
                    "time_range": {"type": "string", "enum": ["day", "week", "month", "year", "all"]},
                    "lang": {"type": "string"},
                },
                "required": ["query"],
            },
        },
    }

    with patch("nodes.core.llm.web_search_tool_node.WebSearchTool", return_value=mock_tool):
        result = await node.execute({"api_key": "test_key"})

        props = result["tool"]["function"]["parameters"]["properties"]
        assert props["k"]["default"] == 3
        assert props["time_range"]["default"] == "week"
        assert props["lang"]["default"] == "fr"


@pytest.mark.asyncio
async def test_execute_handles_missing_properties_gracefully(web_search_tool_node):
    """Test that execute handles missing properties in schema gracefully."""
    mock_tool = MagicMock()
    mock_tool.schema.return_value = {
        "type": "function",
        "function": {
            "name": "web_search",
            "description": "Search the web",
            "parameters": {
                "type": "object",
                "properties": {
                    # Missing k, time_range, and lang properties
                    "query": {"type": "string"},
                },
                "required": ["query"],
            },
        },
    }

    with patch("nodes.core.llm.web_search_tool_node.WebSearchTool", return_value=mock_tool):
        # Should not raise an exception even if properties are missing
        result = await web_search_tool_node.execute({"api_key": "test_key"})
        assert "tool" in result


@pytest.mark.asyncio
async def test_execute_with_none_params():
    """Test execute with None parameter values (should use defaults)."""
    node = WebSearchToolNode(id=3, params={
        "provider": "tavily",
        "default_k": None,
        "time_range": None,
        "lang": None,
        "require_api_key": True,
    })

    mock_tool = MagicMock()
    mock_tool.schema.return_value = {
        "type": "function",
        "function": {
            "name": "web_search",
            "description": "Search the web",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                    "k": {"type": "integer", "minimum": 1, "maximum": 10},
                    "time_range": {"type": "string", "enum": ["day", "week", "month", "year", "all"]},
                    "lang": {"type": "string"},
                },
                "required": ["query"],
            },
        },
    }

    with patch("nodes.core.llm.web_search_tool_node.WebSearchTool", return_value=mock_tool):
        result = await node.execute({"api_key": "test_key"})

        props = result["tool"]["function"]["parameters"]["properties"]
        # Should use fallback defaults when params are None
        assert props["k"]["default"] == 5  # fallback default
        assert props["time_range"]["default"] == "month"  # fallback default
        assert props["lang"]["default"] == "en"  # fallback default


@pytest.mark.asyncio
async def test_execute_with_empty_params():
    """Test execute with empty string parameter values."""
    node = WebSearchToolNode(id=4, params={
        "provider": "tavily",
        "default_k": "",
        "time_range": "",
        "lang": "",
        "require_api_key": True,
    })

    mock_tool = MagicMock()
    mock_tool.schema.return_value = {
        "type": "function",
        "function": {
            "name": "web_search",
            "description": "Search the web",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                    "k": {"type": "integer", "minimum": 1, "maximum": 10},
                    "time_range": {"type": "string", "enum": ["day", "week", "month", "year", "all"]},
                    "lang": {"type": "string"},
                },
                "required": ["query"],
            },
        },
    }

    with patch("nodes.core.llm.web_search_tool_node.WebSearchTool", return_value=mock_tool):
        result = await node.execute({"api_key": "test_key"})

        props = result["tool"]["function"]["parameters"]["properties"]
        # Should use fallback defaults when params are empty strings
        assert props["k"]["default"] == 5  # fallback default
        assert props["time_range"]["default"] == "month"  # fallback default
        assert props["lang"]["default"] == "en"  # fallback default


@pytest.mark.asyncio
async def test_execute_with_invalid_time_range():
    """Test execute with invalid time_range parameter."""
    node = WebSearchToolNode(id=5, params={
        "provider": "tavily",
        "default_k": 5,
        "time_range": "invalid_range",
        "lang": "en",
        "require_api_key": True,
    })

    # The schema now comes from the registry, not from WebSearchTool
    result = await node.execute({"api_key": "test_key"})

    props = result["tool"]["function"]["parameters"]["properties"]
    # Invalid time_range should not override the registry default
    # The registry schema has "month" as default, and invalid params are ignored
    assert props["time_range"]["default"] == "month"


@pytest.mark.asyncio
async def test_execute_with_k_out_of_bounds():
    """Test execute with k parameter out of bounds."""
    node = WebSearchToolNode(id=6, params={
        "provider": "tavily",
        "default_k": 15,  # Out of bounds (max 10)
        "time_range": "month",
        "lang": "en",
        "require_api_key": True,
    })

    mock_tool = MagicMock()
    mock_tool.schema.return_value = {
        "type": "function",
        "function": {
            "name": "web_search",
            "description": "Search the web",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                    "k": {"type": "integer", "minimum": 1, "maximum": 10},
                    "time_range": {"type": "string", "enum": ["day", "week", "month", "year", "all"]},
                    "lang": {"type": "string"},
                },
                "required": ["query"],
            },
        },
    }

    with patch("nodes.core.llm.web_search_tool_node.WebSearchTool", return_value=mock_tool):
        result = await node.execute({"api_key": "test_key"})

        props = result["tool"]["function"]["parameters"]["properties"]
        # Should still set the value even if out of bounds (validation happens at tool execution)
        assert props["k"]["default"] == 15


def test_node_inputs_outputs(web_search_tool_node):
    """Test that the node has correct inputs and outputs."""
    from core.types_registry import get_type
    expected_inputs = {"api_key": get_type("APIKey")}
    assert web_search_tool_node.inputs == expected_inputs
    assert web_search_tool_node.outputs == {"tool": web_search_tool_node.outputs["tool"]}


def test_node_category(web_search_tool_node):
    """Test that the node has correct category."""
    assert web_search_tool_node.CATEGORY == "llm"


def test_default_params(web_search_tool_node):
    """Test default parameters."""
    expected_defaults = {
        "provider": "tavily",
        "default_k": 5,
        "time_range": "month",
        "topic": "general",
        "lang": "en",
    }
    assert web_search_tool_node.default_params == expected_defaults


def test_params_meta(web_search_tool_node):
    """Test parameter metadata."""
    meta = web_search_tool_node.params_meta
    assert len(meta) == 5

    # Check provider parameter
    provider_meta = next(p for p in meta if p["name"] == "provider")
    assert provider_meta["type"] == "combo"
    assert provider_meta["default"] == "tavily"
    assert provider_meta["options"] == ["tavily"]

    # Check default_k parameter
    k_meta = next(p for p in meta if p["name"] == "default_k")
    assert k_meta["type"] == "number"
    assert k_meta["default"] == 5

    # Check time_range parameter
    time_meta = next(p for p in meta if p["name"] == "time_range")
    assert time_meta["type"] == "combo"
    assert time_meta["default"] == "month"
    assert time_meta["options"] == ["day", "week", "month", "year"]

    # Check topic parameter
    topic_meta = next(p for p in meta if p["name"] == "topic")
    assert topic_meta["type"] == "combo"
    assert topic_meta["default"] == "general"
    assert topic_meta["options"] == ["general", "news", "finance"]

    # Check lang parameter
    lang_meta = next(p for p in meta if p["name"] == "lang")
    assert lang_meta["type"] == "text"
    assert lang_meta["default"] == "en"
