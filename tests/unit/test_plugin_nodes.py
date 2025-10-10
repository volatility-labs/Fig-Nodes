import pytest
from typing import Dict, Any, List
from unittest.mock import AsyncMock, patch, MagicMock
import json
import asyncio
import pandas as pd
from nodes.custom.binance.binance_klines_streaming_node import BinanceKlinesStreamingNode
from nodes.custom.binance.binance_universe_node import BinancePerpsUniverseNode
from nodes.custom.samples.sample_node import SampleCustomNode
from nodes.core.io.websocket_node import WebSocketNode
from core.types_registry import AssetSymbol, AssetClass, InstrumentType
from nodes.base.base_node import BaseNode
import websockets.exceptions

# Tests for BinanceKlinesStreamingNode

@pytest.fixture
def mock_connect():
    with patch("websockets.connect") as mock:
        yield mock

@pytest.fixture
def binance_klines_node():
    return BinanceKlinesStreamingNode("bk_id", {"interval": "1m"})

class MockWS:
    def __init__(self, messages):
        self.messages = iter(messages)
        self.send = AsyncMock()
        self.close = AsyncMock()

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        pass

    def __aiter__(self):
        return self

    async def __anext__(self):
        try:
            return next(self.messages)
        except StopIteration:
            raise StopAsyncIteration

    async def recv(self):
        return await self.__anext__()

@pytest.mark.asyncio
async def test_binance_klines_start(mock_connect):
    messages = [
        json.dumps({"result": None}),
        json.dumps({
            "e": "kline",
            "k": {
                "s": "BTCUSDT",
                "t": 123456789,
                "x": True,
                "o": "1",
                "h": "2",
                "l": "3",
                "c": "4",
                "v": "5"
            }
        })
    ]
    mock_connect.return_value = MockWS(messages)

    node = BinanceKlinesStreamingNode("bk_id", {"interval": "1m"})
    inputs = {"symbols_0": [AssetSymbol("BTC", AssetClass.CRYPTO, "USDT")]}
    gen = node.start(inputs)
    output = await anext(gen)
    assert "ohlcv" in output
    bars = output["ohlcv"][AssetSymbol("BTC", AssetClass.CRYPTO, "USDT", exchange="binance", instrument_type=InstrumentType.PERPETUAL)]
    assert isinstance(bars, list)
    assert len(bars) == 1
    assert bars[0]["close"] == 4.0

    await gen.aclose()

def test_binance_klines_stop(binance_klines_node):
    binance_klines_node.ws = MagicMock()
    binance_klines_node.stop()
    binance_klines_node.ws.close.assert_called()

@pytest.mark.asyncio
async def test_binance_klines_no_symbols(binance_klines_node):
    gen = binance_klines_node.start({})
    with pytest.raises(StopAsyncIteration):
        await anext(gen)

# Tests for BinancePerpsUniverseNode

@pytest.fixture
def binance_universe_node():
    return BinancePerpsUniverseNode("bu_id", {})

@pytest.mark.asyncio
@patch("requests.get")
async def test_binance_universe_fetch_symbols(mock_get, binance_universe_node):
    mock_get.return_value.status_code = 200
    mock_get.return_value.json.return_value = {
        "symbols": [{
            "baseAsset": "BTC",
            "quoteAsset": "USDT",
            "contractType": "PERPETUAL",
            "status": "TRADING"
        }]
    }
    symbols = await binance_universe_node._fetch_symbols()
    assert len(symbols) == 1
    assert symbols[0].ticker == "BTC"

@pytest.mark.asyncio
@patch("requests.get")
async def test_binance_universe_rate_limit(mock_get, binance_universe_node):
    mock_get.side_effect = [MagicMock(status_code=429), MagicMock(status_code=200, json=lambda: {"symbols": []})]
    symbols = await binance_universe_node._fetch_symbols()
    assert symbols == []

@pytest.mark.asyncio
@patch("requests.get")
async def test_binance_universe_max_attempts(mock_get, binance_universe_node):
    mock_get.return_value = MagicMock(status_code=429)
    symbols = await binance_universe_node._fetch_symbols()
    assert symbols == []
    assert mock_get.call_count == 5


# Tests for SampleCustomNode

@pytest.fixture
def sample_node():
    return SampleCustomNode("sample_id", {})

@pytest.mark.asyncio
async def test_sample_node_execute(sample_node):
    inputs = {"input_data": "test"}
    result = await sample_node.execute(inputs)
    assert result == {"output_data": "test_custom_processed"}

@pytest.mark.asyncio
async def test_sample_node_missing_input(sample_node):
    with pytest.raises(ValueError):
        await sample_node.execute({})

# Tests for WebSocketNode

@pytest.fixture
def ws_node():
    return WebSocketNode("ws_id", {})

@pytest.mark.asyncio
@patch("websockets.connect")
async def test_ws_node_start(mock_connect, ws_node):
    messages = [json.dumps({"data": "test"})]
    mock_connect.return_value = MockWS(messages)

    inputs = {"symbols": [AssetSymbol("TEST", AssetClass.CRYPTO)]}
    gen = ws_node.start(inputs)
    output = await anext(gen)
    assert "ohlcv" in output  # Placeholder assert

    await gen.aclose()

def test_ws_node_stop(ws_node):
    ws_node.stop()  # Check doesn't raise

# Additional tests for WebSocketNode

@pytest.mark.asyncio
@patch("websockets.connect")
async def test_ws_node_multiple_symbols(mock_connect, ws_node):
    messages = [json.dumps({"symbol": "TEST", "data": "test_data"})]
    mock_ws = MockWS(messages)
    mock_connect.return_value = mock_ws

    inputs = {"symbols": [AssetSymbol("TEST", AssetClass.CRYPTO), AssetSymbol("OTHER", AssetClass.CRYPTO)]}
    gen = ws_node.start(inputs)
    output = await anext(gen)
    assert "ohlcv" in output
    assert mock_ws.send.call_args[0][0] == json.dumps({"subscribe": ["TEST", "OTHER"]})

    await gen.aclose()

@pytest.mark.asyncio
@patch("websockets.connect")
async def test_ws_node_no_symbols(mock_connect, ws_node):
    mock_connect.return_value = MockWS([])
    gen = ws_node.start({})
    with pytest.raises(StopAsyncIteration):
        await anext(gen)

@pytest.mark.asyncio
@patch("websockets.connect")
async def test_ws_node_error_handling(mock_connect, ws_node):
    async def failing_recv():
        raise Exception("Connection failed")
    
    mock_ws = AsyncMock()
    mock_ws.__aenter__.return_value = mock_ws
    mock_ws.recv = failing_recv
    mock_ws.send = AsyncMock()
    mock_connect.return_value = mock_ws

    inputs = {"symbols": [AssetSymbol("TEST", AssetClass.CRYPTO)]}
    gen = ws_node.start(inputs)
    with pytest.raises(Exception):
        await anext(gen)

    await gen.aclose()
