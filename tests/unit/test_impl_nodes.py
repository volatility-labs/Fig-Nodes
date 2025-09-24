import pytest
from typing import Dict, Any, List
from unittest.mock import AsyncMock, patch
import pandas as pd
from nodes.core.flow.for_each_node import ForEachNode
from nodes.core.market.indicators_bundle_node import IndicatorsBundleNode
from nodes.core.io.text_input_node import TextInputNode
from nodes.core.io.asset_symbol_input_node import AssetSymbolInputNode
from nodes.core.io.logging_node import LoggingNode
from nodes.core.logic.score_node import ScoreNode
from nodes.core.market.instrument_resolver_node import InstrumentResolverNode
from nodes.core.llm.text_to_llm_message_node import TextToLLMMessageNode
from core.types_registry import AssetSymbol, AssetClass, Provider, InstrumentType

# Tests for ForEachNode

@pytest.fixture
def foreach_node():
    return ForEachNode("foreach_id", {})

@pytest.mark.asyncio
async def test_foreach_node_execute(foreach_node):
    inputs = {"list": [1, 2, 3]}
    result = await foreach_node.execute(inputs)
    assert result == {"list": [1, 2, 3]}

@pytest.mark.asyncio
async def test_foreach_node_execute_empty(foreach_node):
    inputs = {}
    result = await foreach_node.execute(inputs)
    assert result == {"list": []}

def test_foreach_node_validate(foreach_node):
    assert foreach_node.validate_inputs({"list": []}) is True
    assert foreach_node.validate_inputs({}) is False  # Missing required

# Tests for IndicatorsBundleNode

@pytest.fixture
def indicators_node():
    return IndicatorsBundleNode("ind_id", {"timeframe": "1h"})

@pytest.mark.asyncio
async def test_indicators_node_execute_empty(indicators_node):
    result = await indicators_node.execute({})
    assert result == {"indicators": {}}

@pytest.mark.asyncio
async def test_indicators_node_execute_single(indicators_node):
    # Create mock OHLCV bars as list of dictionaries
    klines_data = [
        {"timestamp": 1000, "open": 1.0, "high": 2.0, "low": 0.5, "close": 1.5, "volume": 100.0},
        {"timestamp": 2000, "open": 1.5, "high": 3.0, "low": 1.0, "close": 2.5, "volume": 150.0},
        {"timestamp": 3000, "open": 2.5, "high": 4.0, "low": 2.0, "close": 3.5, "volume": 200.0},
        {"timestamp": 4000, "open": 3.5, "high": 5.0, "low": 3.0, "close": 4.5, "volume": 250.0},
        {"timestamp": 5000, "open": 4.5, "high": 6.0, "low": 4.0, "close": 5.5, "volume": 300.0},
        {"timestamp": 6000, "open": 5.5, "high": 7.0, "low": 5.0, "close": 6.5, "volume": 350.0},
        {"timestamp": 7000, "open": 6.5, "high": 8.0, "low": 6.0, "close": 7.5, "volume": 400.0},
        {"timestamp": 8000, "open": 7.5, "high": 9.0, "low": 7.0, "close": 8.5, "volume": 450.0},
        {"timestamp": 9000, "open": 8.5, "high": 10.0, "low": 8.0, "close": 9.5, "volume": 500.0},
        {"timestamp": 10000, "open": 9.5, "high": 11.0, "low": 9.0, "close": 10.5, "volume": 550.0},
        {"timestamp": 11000, "open": 10.5, "high": 12.0, "low": 10.0, "close": 11.5, "volume": 600.0},
        {"timestamp": 12000, "open": 11.5, "high": 13.0, "low": 11.0, "close": 12.5, "volume": 650.0},
        {"timestamp": 13000, "open": 12.5, "high": 14.0, "low": 12.0, "close": 13.5, "volume": 700.0},
        {"timestamp": 14000, "open": 13.5, "high": 15.0, "low": 13.0, "close": 14.5, "volume": 750.0},
        {"timestamp": 15000, "open": 14.5, "high": 16.0, "low": 14.0, "close": 15.5, "volume": 800.0}
    ]
    inputs = {"klines": {AssetSymbol("TEST", AssetClass.CRYPTO): klines_data}}
    result = await indicators_node.execute(inputs)
    assert isinstance(result["indicators"], dict)
    assert AssetSymbol("TEST", AssetClass.CRYPTO) in result["indicators"]

@pytest.mark.asyncio
async def test_indicators_node_execute_multi(indicators_node):
    # Create mock OHLCV bars as list of dictionaries (same data for both symbols)
    klines_data = [
        {"timestamp": 1000, "open": 1.0, "high": 2.0, "low": 0.5, "close": 1.5, "volume": 100.0},
        {"timestamp": 2000, "open": 1.5, "high": 3.0, "low": 1.0, "close": 2.5, "volume": 150.0},
        {"timestamp": 3000, "open": 2.5, "high": 4.0, "low": 2.0, "close": 3.5, "volume": 200.0},
        {"timestamp": 4000, "open": 3.5, "high": 5.0, "low": 3.0, "close": 4.5, "volume": 250.0},
        {"timestamp": 5000, "open": 4.5, "high": 6.0, "low": 4.0, "close": 5.5, "volume": 300.0},
        {"timestamp": 6000, "open": 5.5, "high": 7.0, "low": 5.0, "close": 6.5, "volume": 350.0},
        {"timestamp": 7000, "open": 6.5, "high": 8.0, "low": 6.0, "close": 7.5, "volume": 400.0},
        {"timestamp": 8000, "open": 7.5, "high": 9.0, "low": 7.0, "close": 8.5, "volume": 450.0},
        {"timestamp": 9000, "open": 8.5, "high": 10.0, "low": 8.0, "close": 9.5, "volume": 500.0},
        {"timestamp": 10000, "open": 9.5, "high": 11.0, "low": 9.0, "close": 10.5, "volume": 550.0},
        {"timestamp": 11000, "open": 10.5, "high": 12.0, "low": 10.0, "close": 11.5, "volume": 600.0},
        {"timestamp": 12000, "open": 11.5, "high": 13.0, "low": 11.0, "close": 12.5, "volume": 650.0},
        {"timestamp": 13000, "open": 12.5, "high": 14.0, "low": 12.0, "close": 13.5, "volume": 700.0},
        {"timestamp": 14000, "open": 13.5, "high": 15.0, "low": 13.0, "close": 14.5, "volume": 750.0},
        {"timestamp": 15000, "open": 14.5, "high": 16.0, "low": 14.0, "close": 15.5, "volume": 800.0}
    ]
    inputs = {"klines_0": {AssetSymbol("A", AssetClass.CRYPTO): klines_data},
              "klines_1": {AssetSymbol("B", AssetClass.CRYPTO): klines_data}}
    result = await indicators_node.execute(inputs)
    assert set(result["indicators"].keys()) == {AssetSymbol("A", AssetClass.CRYPTO), AssetSymbol("B", AssetClass.CRYPTO)}

@pytest.mark.asyncio
async def test_indicators_node_execute_empty_df(indicators_node):
    inputs = {"klines": {AssetSymbol("TEST", AssetClass.CRYPTO): []}}
    result = await indicators_node.execute(inputs)
    assert result["indicators"] == {}

# Tests for TextInputNode

@pytest.fixture
def text_node():
    return TextInputNode("text_id", {"value": "hello"})

@pytest.mark.asyncio
async def test_text_node_execute(text_node):
    result = await text_node.execute({})
    assert result == {"text": "hello"}

@pytest.mark.asyncio
async def test_text_node_default():
    text_node = TextInputNode("text_id", {})
    result = await text_node.execute({})
    assert result == {"text": ""}

# Tests for TextToLLMMessageNode

@pytest.mark.asyncio
async def test_text_to_llm_message_default_role():
    node = TextToLLMMessageNode("adapter_id", {})
    result = await node.execute({"data": "hello"})
    assert result["message"]["role"] == "user"
    assert result["message"]["content"] == "hello"
    assert isinstance(result["messages"], list) and len(result["messages"]) == 1

@pytest.mark.asyncio
async def test_text_to_llm_message_roles():
    for role in ["user", "assistant", "system", "tool"]:
        node = TextToLLMMessageNode("adapter_id", {"role": role})
        result = await node.execute({"data": "x"})
        assert result["message"]["role"] == role
        assert result["messages"][0]["role"] == role

@pytest.mark.asyncio
async def test_text_to_llm_message_non_string():
    node = TextToLLMMessageNode("adapter_id", {"role": "assistant"})
    result = await node.execute({"data": 123})
    assert result["message"]["content"] == "123"

# Tests for AssetSymbolInputNode

@pytest.fixture
def asset_node():
    return AssetSymbolInputNode("asset_id", {
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
    return LoggingNode("log_id", {})

@pytest.mark.asyncio
@patch("builtins.print")
async def test_logging_node_execute_str(mock_print, logging_node):
    inputs = {"input": "test"}
    result = await logging_node.execute(inputs)
    assert result == {"output": "test"}
    mock_print.assert_called_with("LoggingNode log_id: test")

@pytest.mark.asyncio
@patch("builtins.print")
async def test_logging_node_execute_list_symbols(mock_print, logging_node):
    symbols = [AssetSymbol("BTC", AssetClass.CRYPTO), AssetSymbol("ETH", AssetClass.CRYPTO)]
    inputs = {"input": symbols}
    result = await logging_node.execute(inputs)
    assert result == {"output": "Preview of first 100 symbols:\nBTC\nETH"}
    mock_print.assert_called()

@pytest.mark.asyncio
@patch("builtins.print")
async def test_logging_node_execute_long_list(mock_print, logging_node):
    symbols = [AssetSymbol(str(i), AssetClass.CRYPTO) for i in range(101)]
    inputs = {"input": symbols}
    await logging_node.execute(inputs)
    call_arg = mock_print.call_args[0][0]
    assert "and 1 more" in call_arg

# Tests for ScoreNode

@pytest.fixture
def score_node():
    return ScoreNode("score_id", {})

@pytest.mark.asyncio
async def test_score_node_execute_empty(score_node):
    result = await score_node.execute({})
    assert result == {"score": 0.0}

@pytest.mark.asyncio
async def test_score_node_execute_with_indicators(score_node):
    inputs = {"indicators": {"test": 1}}
    result = await score_node.execute(inputs)
    assert result == {"score": 0.0}  # Placeholder

# Tests for InstrumentResolverNode

@pytest.fixture
def resolver_node():
    return InstrumentResolverNode("res_id", {"exchange": "binance", "instrument_type": "PERPETUAL", "quote_currency": "USDT"})

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
