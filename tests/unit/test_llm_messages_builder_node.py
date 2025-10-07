import asyncio
import pytest

from nodes.core.llm.llm_messages_builder_node import LLMMessagesBuilderNode


@pytest.mark.asyncio
async def test_builder_merges_multiple_message_lists():
    node = LLMMessagesBuilderNode(1, {})
    inputs = {
        "message_0": [{"role": "system", "content": "You are an assistant."}],
        "message_1": [{"role": "user", "content": "Hi"}],
        "message_2": [{"role": "user", "content": "What is AAPL price?"}],
    }
    out = await node.execute(inputs)
    msgs = out["messages"]
    assert len(msgs) == 3
    assert msgs[0] == {"role": "system", "content": "You are an assistant."}
    assert msgs[1] == {"role": "user", "content": "Hi"}
    assert msgs[2] == {"role": "user", "content": "What is AAPL price?"}


@pytest.mark.asyncio
async def test_builder_drops_empty_with_param_true():
    node = LLMMessagesBuilderNode(2, {"drop_empty": True})
    inputs = {
        "message_0": [{"role": "user", "content": "u1"}, {"role": "user", "content": " "}],
        "message_1": [{"role": "assistant", "content": "a1"}, {"role": "assistant", "content": ""}],
        "message_2": [{"role": "tool", "tool_name": "get_klines", "content": "{...}"}],
    }
    out = await node.execute(inputs)
    msgs = out["messages"]
    assert len(msgs) == 3  # Empties dropped
    roles = [m["role"] for m in msgs]
    assert roles == ["user", "assistant", "tool"]
    assert msgs[0]["content"] == "u1"


@pytest.mark.asyncio
async def test_builder_keeps_empty_with_param_false():
    node = LLMMessagesBuilderNode(3, {"drop_empty": False})
    inputs = {
        "message_0": [{"role": "user", "content": "u1"}, {"role": "user", "content": " "}],
        "message_1": [{"role": "assistant", "content": ""}],
    }
    out = await node.execute(inputs)
    msgs = out["messages"]
    assert len(msgs) == 3  # Empties kept
    assert msgs[1]["content"] == " "
    assert msgs[2]["content"] == ""


