import pytest
from typing import Dict, Any, List
from unittest.mock import AsyncMock, patch
import pandas as pd
from nodes.core.flow.for_each_node import ForEachNode
from nodes.core.io.text_input_node import TextInputNode
from nodes.core.io.asset_symbol_input_node import AssetSymbolInputNode
from nodes.core.io.logging_node import LoggingNode
from nodes.core.logic.score_node import ScoreNode
from nodes.core.market.utils.instrument_resolver_node import InstrumentResolverNode
from nodes.core.llm.text_to_llm_message_node import TextToLLMMessageNode
from core.types_registry import AssetSymbol, AssetClass, Provider, InstrumentType

# Tests for ForEachNode

@pytest.fixture
def foreach_node():
    return ForEachNode(id=1, params={})

@pytest.mark.asyncio
async def test_foreach_node_execute(foreach_node):
    inputs = {"list": [1, 2, 3]}
    result = await foreach_node.execute(inputs)
    assert result == {"item": [1, 2, 3]}

@pytest.mark.asyncio
async def test_foreach_node_execute_empty(foreach_node):
    inputs = {"list": []}
    result = await foreach_node.execute(inputs)
    assert result == {"item": []}

def test_foreach_node_validate(foreach_node):
    assert foreach_node.validate_inputs({"list": []}) is True
    assert foreach_node.validate_inputs({}) is False  # Missing required


# Tests for TextInputNode

@pytest.fixture
def text_node():
    return TextInputNode(id=1, params={"value": "hello"})

@pytest.mark.asyncio
async def test_text_node_execute(text_node):
    result = await text_node.execute({})
    assert result == {"text": "hello"}

@pytest.mark.asyncio
async def test_text_node_default():
    text_node = TextInputNode(id=1, params={})
    result = await text_node.execute({})
    assert result == {"text": ""}

# Tests for TextToLLMMessageNode

@pytest.mark.asyncio
async def test_text_to_llm_message_default_role():
    node = TextToLLMMessageNode(id=1, params={})
    result = await node.execute({"data": "hello"})
    assert result["message"]["role"] == "user"
    assert result["message"]["content"] == "hello"
    assert isinstance(result["messages"], list) and len(result["messages"]) == 1

@pytest.mark.asyncio
async def test_text_to_llm_message_roles():
    for role in ["user", "assistant", "system", "tool"]:
        node = TextToLLMMessageNode(id=1, params={"role": role})
        result = await node.execute({"data": "x"})
        assert result["message"]["role"] == role
        assert result["messages"][0]["role"] == role

@pytest.mark.asyncio
async def test_text_to_llm_message_non_string():
    node = TextToLLMMessageNode(id=1, params={"role": "assistant"})
    result = await node.execute({"data": 123})
    assert result["message"]["content"] == "123"

# Tests for AssetSymbolInputNode

@pytest.fixture
def asset_node():
    return AssetSymbolInputNode(id=1, params={
        "ticker": "btc",
        "asset_class": AssetClass.CRYPTO,
        "quote_currency": "usdt",
        "provider": Provider.BINANCE.name,
        "instrument_type": InstrumentType.PERPETUAL.name
    })

@pytest.mark.asyncio
async def test_asset_node_execute(asset_node):
    result = await asset_node.execute({})
    sym = result["symbol"]
    assert sym.ticker == "BTC"
    assert sym.asset_class == AssetClass.CRYPTO
    assert sym.quote_currency == "USDT"
    assert sym.provider == Provider.BINANCE
    assert sym.instrument_type == InstrumentType.PERPETUAL

def test_asset_node_params_meta():
    assert len(AssetSymbolInputNode.params_meta) == 5  # Check existence

# Tests for LoggingNode

@pytest.fixture
def logging_node():
    return LoggingNode(id=1, params={})

@pytest.mark.asyncio
@patch("builtins.print")
async def test_logging_node_execute_str(mock_print, logging_node):
    inputs = {"input": "test"}
    result = await logging_node.execute(inputs)
    assert result == {"output": "test"}
    mock_print.assert_called_with("LoggingNode 1: test")

@pytest.mark.asyncio
@patch("builtins.print")
async def test_logging_node_execute_list_symbols(mock_print, logging_node):
    symbols = [AssetSymbol("BTC", AssetClass.CRYPTO), AssetSymbol("ETH", AssetClass.CRYPTO)]
    inputs = {"input": symbols}
    result = await logging_node.execute(inputs)
    assert result == {"output": "BTC, ETH"}
    mock_print.assert_called_with("BTC, ETH")

@pytest.mark.asyncio
@patch("builtins.print")
async def test_logging_node_execute_long_list(mock_print, logging_node):
    symbols = [AssetSymbol(str(i), AssetClass.CRYPTO) for i in range(101)]
    inputs = {"input": symbols}
    await logging_node.execute(inputs)
    call_arg = mock_print.call_args[0][0]
    expected = ", ".join(str(i) for i in range(101))
    assert call_arg == expected

# Tests for ScoreNode

@pytest.fixture
def score_node():
    return ScoreNode(id=1, params={})

@pytest.mark.asyncio
async def test_score_node_execute_empty(score_node):
    result = await score_node.execute({"indicators": {}})
    assert result == {"score": 0.0}

@pytest.mark.asyncio
async def test_score_node_execute_with_indicators(score_node):
    inputs = {"indicators": {"test": 1}}
    result = await score_node.execute(inputs)
    assert result == {"score": 0.0}  # Placeholder

# Tests for InstrumentResolverNode

@pytest.fixture
def resolver_node():
    return InstrumentResolverNode(id=1, params={"exchange": "binance", "instrument_type": "PERPETUAL", "quote_currency": "USDT"})

@pytest.mark.asyncio
@patch("requests.get")
async def test_resolver_node_execute(mock_get, resolver_node):
    mock_get.return_value.status_code = 200
    mock_get.return_value.json.return_value = {
        "symbols": [{"baseAsset": "BTC", "quoteAsset": "USDT", "contractType": "PERPETUAL", "status": "TRADING"}]
    }
    inputs = {"symbols": [AssetSymbol("BTC", AssetClass.CRYPTO)]}
    result = await resolver_node.execute(inputs)
    resolved = result["resolved_symbols"][0]
    assert resolved.ticker == "BTC"
    assert resolved.instrument_type == InstrumentType.PERPETUAL

@pytest.mark.asyncio
@patch("requests.get")
async def test_resolver_node_execute_non_crypto(mock_get, resolver_node):
    inputs = {"symbols": [AssetSymbol("AAPL", AssetClass.STOCKS)]}
    result = await resolver_node.execute(inputs)
    assert len(result["resolved_symbols"]) == 1
    assert result["resolved_symbols"][0].ticker == "AAPL"

@pytest.mark.asyncio
@patch("requests.get")
async def test_resolver_node_execute_no_match(mock_get, resolver_node):
    mock_get.return_value.status_code = 200
    mock_get.return_value.json.return_value = {"symbols": []}
    inputs = {"symbols": [AssetSymbol("UNKNOWN", AssetClass.CRYPTO)]}
    result = await resolver_node.execute(inputs)
    assert result["resolved_symbols"] == []
