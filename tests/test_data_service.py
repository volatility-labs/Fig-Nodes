import pytest
import asyncio
import pandas as pd
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch, MagicMock

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from hl_bot_v2.services.data_service import DataService
from hl_bot_v2.data_provider.data_provider import BinanceDataProvider
import websockets

# ---------------------------------------------------------------------------
# Fixtures to accelerate tests (remove built-in 0.5-second sleeps in production
# code and prevent runaway websocket loops while preserving coroutine awaits).
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def fast_sleep(monkeypatch):
    # Remove this fixture
    pass

@pytest.fixture
def mock_provider():
    provider = MagicMock(spec=BinanceDataProvider)
    provider.get_klines_df = AsyncMock(return_value=pd.DataFrame({
        'open': [100.0],
        'high': [101.0],
        'low': [99.0],
        'close': [100.5],
        'volume': [1000.0]
    }, index=[pd.Timestamp.now(tz='UTC') - timedelta(hours=1)]))
    
    async def mock_stream(streams):
        yield {'data': {
            'e': 'kline',
            'k': {
                's': 'BTCUSDT',
                'i': '1h',
                't': int((datetime.now(timezone.utc) - timedelta(minutes=1)).timestamp() * 1000),
                'o': '102.0',
                'h': '103.0',
                'l': '101.0',
                'c': '102.5',
                'v': '500.0',
                'x': True
            }
        }}
        await asyncio.sleep(0.01)
        yield {'data': {
            'e': 'kline',
            'k': {
                's': 'ETHUSDT',
                'i': '1m',
                't': int(datetime.now(timezone.utc).timestamp() * 1000),
                'o': '2000.0',
                'h': '2005.0',
                'l': '1995.0',
                'c': '2002.0',
                'v': '200.0',
                'x': True
            }
        }}
        await asyncio.sleep(0.01)
        while True:
            await asyncio.sleep(1)  # Simulate ongoing stream
    provider.stream_klines = mock_stream
    return provider

@pytest.mark.asyncio
async def test_prewarm_data(mock_provider):
    symbols = ['BTC', 'ETH']
    service = DataService(mock_provider, symbols, prewarm_days=1)
    service.rate_limit_sleep = 0
    await service.prewarm_data()
    
    for symbol in symbols:
        for tf in ['1m', '5m', '15m', '1h']:
            data = service.get_data(symbol, tf)
            assert data is not None
            assert isinstance(data, pd.DataFrame)
            assert len(data) == 1
            assert 'close' in data.columns
            assert data['close'].iloc[0] == 100.5

@pytest.mark.asyncio
async def test_prewarm_data_bar_count(mock_provider):
    symbols = ['BTC']
    # Adjust mock to return 600 bars
    mock_df = pd.DataFrame({
        'open': [100.0] * 600,
        'high': [101.0] * 600,
        'low': [99.0] * 600,
        'close': [100.5] * 600,
        'volume': [1000.0] * 600
    }, index=pd.date_range(end=pd.Timestamp.now(tz='UTC'), periods=600, freq='min'))
    mock_provider.get_klines_df = AsyncMock(return_value=mock_df)
    
    service = DataService(mock_provider, symbols)
    service.rate_limit_sleep = 0
    await service.prewarm_data()
    
    for tf in ['1m', '5m', '15m', '1h']:
        data = service.get_data('BTC', tf)
        assert len(data) == 600

@pytest.mark.asyncio
async def test_continuous_updates_ingestion(mock_provider):
    symbols = ['BTC', 'ETH']
    service = DataService(mock_provider, symbols)
    service.rate_limit_sleep = 0
    service.reconnect_delay = 0
    await service.prewarm_data()
    service.scoring_service = MagicMock()
    
    # Start updates and simulate ingestion
    await service.start_continuous_updates()
    
    # Allow time for mock messages to process
    await asyncio.sleep(0.05)
    
    # Check BTC 1h update
    btc_data = service.get_data('BTC', '1h')
    assert len(btc_data) == 2  # Prewarm + 1 update
    assert btc_data['close'].iloc[-1] == 102.5
    
    # Check ETH 1m update
    eth_data = service.get_data('ETH', '1m')
    assert len(eth_data) == 2  # Prewarm + 1 update
    assert eth_data['close'].iloc[-1] == 2002.0
    
    # Test cache trimming (simulate exceeding 600 bars)
    large_df = pd.DataFrame({'close': range(601)}, index=pd.date_range(start='2023-01-01', periods=601, freq='h', tz='UTC'))
    service.data_cache['BTC']['1h'] = large_df
    new_df = pd.DataFrame({'close': [601.0]}, index=[pd.Timestamp.now(tz='UTC')])
    service._update_cache('BTC', '1h', new_df)
    assert len(service.get_data('BTC', '1h')) == 600
    assert service.get_data('BTC', '1h')['close'].iloc[-1] == 601.0
    
    # Test error message handling
    error_msg = {'data': {'e': 'error', 'error': 'Test error'}}
    with patch('hl_bot_v2.services.data_service.logger.error') as mock_log:
        await service._kline_handler(error_msg['data'])
        mock_log.assert_called_with("Websocket error: {'e': 'error', 'error': 'Test error'}")

    # Clean up websocket task to avoid background loops
    await service.close()

@pytest.mark.asyncio
async def test_get_data_empty_cache():
    service = DataService(MagicMock(), [])
    assert service.get_data('NONEXISTENT', '1h') is None 

@pytest.mark.asyncio
async def test_fill_gaps(mock_provider):
    symbols = ['BTC']
    service = DataService(mock_provider, symbols)
    service.rate_limit_sleep = 0
    # Mock prewarm to have some data with gaps
    df_with_gap = pd.DataFrame({
        'close': [100, 102],
    }, index=pd.date_range(start='2023-01-01', periods=2, freq='h', tz='UTC'))
    service.data_cache['BTC'] = {'1h': df_with_gap}
    
    await service.fill_gaps()
    filled = service.get_data('BTC', '1h')
    assert len(filled) == 3  # Mocked fetch adds one row

@pytest.mark.asyncio
async def test_get_data_edge_cases(mock_provider):
    service = DataService(mock_provider, [])
    assert service.get_data('INVALID', '1h') is None
    service.data_cache['BTC'] = {'1h': pd.DataFrame()}
    assert service.get_data('BTC', '1h').empty 

@pytest.mark.asyncio
async def test_websocket_reconnection(mock_provider):
    symbols = ['BTC']
    service = DataService(mock_provider, symbols)
    service.reconnect_delay = 0
    service.scoring_service = MagicMock()
    
    # Mock stream with closure
    class MockStreamWithClose:
        def __init__(self):
            self.called = 0

        async def __call__(self, streams):
            if self.called == 0:
                yield {'data': {
                    'e': 'kline',
                    'k': {
                        's': 'BTCUSDT',
                        'i': '1h',
                        't': int((datetime.now(timezone.utc) - timedelta(minutes=1)).timestamp() * 1000),
                        'o': '102.0',
                        'h': '103.0',
                        'l': '101.0',
                        'c': '102.5',
                        'v': '500.0',
                        'x': True
                    }
                }}
                await asyncio.sleep(0.01)
                self.called += 1
                raise websockets.ConnectionClosed(1000, "Test close")
            else:
                yield {'data': {
                    'e': 'kline',
                    'k': {
                        's': 'BTCUSDT',
                        'i': '1h',
                        't': int(datetime.now(timezone.utc).timestamp() * 1000),
                        'o': '103.0',
                        'h': '104.0',
                        'l': '102.0',
                        'c': '103.5',
                        'v': '600.0',
                        'x': True
                    }
                }}
                await asyncio.sleep(0.01)
                while True:
                    await asyncio.sleep(1)  # Simulate ongoing stream after reconnection

    mock_provider.stream_klines = MockStreamWithClose()
    
    await service.start_continuous_updates()
    await asyncio.sleep(0.1)  # Allow for processing
    
    # Check if data was processed before close
    assert len(service.get_data('BTC', '1h')) > 0
    
    # Simulate reconnection (check logs or attempts)
    with patch('hl_bot_v2.services.data_service.logger.warning') as mock_warn:
        await asyncio.sleep(0.1)  # Wait for reconnection attempt
        mock_warn.assert_called_with("Websocket connection closed. Reconnecting...")

    # Verify data after reconnection
    assert len(service.get_data('BTC', '1h')) >= 1

    await service.close()

# Add another test for ping timeout
@pytest.mark.asyncio
async def test_websocket_ping_pong(mock_provider):
    symbols = ['BTC']
    service = DataService(mock_provider, symbols)
    service.reconnect_delay = 0
    service.scoring_service = MagicMock()
    
    # Mock stream that times out
    async def mock_stream_timeout(streams):
        # Simulate short inactivity period
        await asyncio.sleep(0.1)  # Short delay instead of 600 for test speed
        yield {'data': {
            'e': 'kline',
            'k': {
                's': 'BTCUSDT',
                'i': '1h',
                't': int((datetime.now(timezone.utc) - timedelta(minutes=1)).timestamp() * 1000),
                'o': '102.0',
                'h': '103.0',
                'l': '101.0',
                'c': '102.5',
                'v': '500.0',
                'x': True
            }
        }}
        await asyncio.sleep(0.01)
        while True:
            await asyncio.sleep(1)  # Simulate ongoing stream
    
    mock_provider.stream_klines = mock_stream_timeout
    
    await service.start_continuous_updates()
    await asyncio.sleep(0.2)  # Allow for processing
    
    # Verify data after simulated inactivity
    data = service.get_data('BTC', '1h')
    assert data is not None
    assert len(data) == 1
    
    await service.close() 