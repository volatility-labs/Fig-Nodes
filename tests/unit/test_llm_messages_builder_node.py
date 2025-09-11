import asyncio
import pytest

from nodes.core.llm.llm_messages_builder_node import LLMMessagesBuilderNode


@pytest.mark.asyncio
async def test_builder_merges_base_and_prompt_and_system():
    node = LLMMessagesBuilderNode(1, {})
    inputs = {
        "base": [{"role": "user", "content": "Hi"}],
        "system_text": "You are an assistant.",
        "prompt": "What is AAPL price?",
    }
    out = await node.execute(inputs)
    msgs = out["messages"]
    assert msgs[0]["role"] == "system"
    assert msgs[0]["content"].startswith("You are an assistant")
    assert msgs[1] == {"role": "user", "content": "Hi"}
    assert msgs[-1] == {"role": "user", "content": "What is AAPL price?"}


@pytest.mark.asyncio
async def test_builder_multi_inputs_and_drop_empty():
    node = LLMMessagesBuilderNode(2, {"drop_empty": True})
    inputs = {
        "user": [[{"role": "user", "content": "u1"}], {"role": "user", "content": " "}],
        "assistant": [[{"role": "assistant", "content": "a1"}]],
        "tool": [[{"role": "tool", "tool_name": "get_klines", "content": "{...}"}]],
    }
    out = await node.execute(inputs)
    msgs = out["messages"]
    roles = [m["role"] for m in msgs]
    assert roles == ["user", "assistant", "tool"]
    assert msgs[0]["content"] == "u1"


@pytest.mark.asyncio
async def test_builder_enforces_single_system_and_moves_first():
    node = LLMMessagesBuilderNode(3, {"enforce_single_system": True, "ensure_system_first": True})
    inputs = {
        "base": [
            {"role": "user", "content": "Hi"},
            {"role": "system", "content": "Existing system"},
            {"role": "assistant", "content": "Hello"},
        ],
        "system_text": "New system should not duplicate",
    }
    out = await node.execute(inputs)
    msgs = out["messages"]
    assert msgs[0]["role"] == "system"
    assert msgs[0]["content"] == "Existing system"
    assert sum(1 for m in msgs if m.get("role") == "system") == 1


