import pytest
from nodes.core.io.system_prompt_loader_node import SystemPromptLoader


@pytest.fixture
def loader_node():
    return SystemPromptLoader(id=1, params={"content": "Test system prompt"})


@pytest.mark.asyncio
async def test_basic_output(loader_node):
    result = await loader_node.execute({})
    assert result["system"] == "Test system prompt"


@pytest.mark.asyncio
async def test_empty_content():
    node = SystemPromptLoader(id=1, params={"content": ""})
    result = await node.execute({})
    assert result["system"] == ""


@pytest.mark.asyncio
async def test_non_string_content():
    node = SystemPromptLoader(id=1, params={"content": 123})
    result = await node.execute({})
    assert result["system"] == "123"


@pytest.mark.asyncio
async def test_param_overriding():
    node = SystemPromptLoader(id=1, params={"content": "Original"})
    node.params["content"] = "Overridden"
    result = await node.execute({})
    assert result["system"] == "Overridden"
