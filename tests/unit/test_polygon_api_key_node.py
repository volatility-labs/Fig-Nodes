import pytest
from custom_nodes.polygon.polygon_api_key_node import PolygonAPIKeyNode


@pytest.fixture
def polygon_api_key_node():
    return PolygonAPIKeyNode("polygon_key_id", {
        "api_key": "test_api_key_123"
    })


@pytest.mark.asyncio
async def test_execute_success(polygon_api_key_node):
    """Test successful execution with valid API key."""
    result = await polygon_api_key_node.execute({})

    assert "api_key" in result
    assert result["api_key"] == "test_api_key_123"


@pytest.mark.asyncio
async def test_execute_empty_key(polygon_api_key_node):
    """Test error when API key is empty."""
    polygon_api_key_node.params["api_key"] = ""

    with pytest.raises(ValueError, match="Polygon API key is required"):
        await polygon_api_key_node.execute({})


@pytest.mark.asyncio
async def test_execute_whitespace_key(polygon_api_key_node):
    """Test error when API key is only whitespace."""
    polygon_api_key_node.params["api_key"] = "   "

    with pytest.raises(ValueError, match="Polygon API key is required"):
        await polygon_api_key_node.execute({})


@pytest.mark.asyncio
async def test_execute_default_params():
    """Test with default parameters (empty key)."""
    node = PolygonAPIKeyNode("key_id", {})

    with pytest.raises(ValueError, match="Polygon API key is required"):
        await node.execute({})


@pytest.mark.asyncio
async def test_execute_strip_whitespace(polygon_api_key_node):
    """Test that whitespace is stripped from API key."""
    polygon_api_key_node.params["api_key"] = "  test_key_with_spaces  "

    result = await polygon_api_key_node.execute({})

    assert result["api_key"] == "test_key_with_spaces"


@pytest.mark.asyncio
async def test_execute_long_key(polygon_api_key_node):
    """Test with a realistic long API key."""
    long_key = "sk-1234567890abcdef1234567890abcdef1234567890abcdef"
    polygon_api_key_node.params["api_key"] = long_key

    result = await polygon_api_key_node.execute({})

    assert result["api_key"] == long_key


@pytest.mark.asyncio
async def test_execute_special_characters(polygon_api_key_node):
    """Test API key with special characters."""
    special_key = "api_key-with.special_chars_123!@#"
    polygon_api_key_node.params["api_key"] = special_key

    result = await polygon_api_key_node.execute({})

    assert result["api_key"] == special_key
