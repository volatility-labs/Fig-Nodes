
import pytest
import asyncio
from unittest.mock import patch, AsyncMock, MagicMock

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from hl_bot_v2.main import get_hyperliquid_universe, main

from datetime import datetime, timezone
import pandas as pd
import websockets
from websockets.exceptions import ConnectionClosed

@pytest.mark.asyncio
async def test_get_hyperliquid_universe():
    with patch('hl_bot_v2.main.Info') as mock_info:
        mock_info.return_value.meta.return_value = {'universe': [{'name': 'BTC'}, {'name': 'ETH'}]}
        universe = await get_hyperliquid_universe()
        assert universe == {'BTC', 'ETH'}

@pytest.mark.asyncio
async def test_main():
    with patch('hl_bot_v2.main.get_hyperliquid_universe', new=AsyncMock(return_value={'BTC', 'ETH'})) as mock_universe, \
         patch('hl_bot_v2.main.BinanceDataProvider') as mock_provider, \
         patch('hl_bot_v2.main.DataService') as mock_data, \
         patch('hl_bot_v2.main.asyncio.sleep', new=AsyncMock(side_effect=asyncio.CancelledError)) as mock_sleep:
        mock_provider.return_value.get_tradable_universe = AsyncMock(return_value={'BTC', 'ETH'})
        mock_provider.return_value.close = AsyncMock()
        mock_data.return_value.start_continuous_updates = AsyncMock()
        mock_data.return_value.prewarm_data = AsyncMock()
        mock_data.return_value.fill_gaps = AsyncMock()
        mock_data.return_value.get_data.return_value = None
        mock_data.return_value.close = AsyncMock()
        await main()
        mock_universe.assert_called_once() 

@pytest.mark.asyncio
async def test_main_websocket_reconnection():
    original_sleep = asyncio.sleep
    with patch('hl_bot_v2.main.get_hyperliquid_universe', new=AsyncMock(return_value={'BTC'})) as mock_universe, \
         patch('hl_bot_v2.main.BinanceDataProvider') as mock_provider, \
         patch('hl_bot_v2.main.asyncio.sleep') as mock_sleep, \
         patch('hl_bot_v2.services.data_service.asyncio.sleep') as mock_data_sleep:

        mock_provider.return_value.get_tradable_universe = AsyncMock(return_value={'BTC'})
        mock_provider.return_value.close = AsyncMock()
        mock_provider.return_value.get_klines_df = AsyncMock(return_value=pd.DataFrame({
            'open': [100.0],
            'high': [101.0],
            'low': [99.0],
            'close': [100.5],
            'volume': [1000.0]
        }, index=[pd.Timestamp.now(tz='UTC')]))

        async def mock_stream(*args):
            yield {'data': {}}
            await original_sleep(0.2)
            raise ConnectionClosed(1000, "Test disconnect")

        mock_provider.return_value.stream_klines = mock_stream

        async def instant_sleep(delay):
            await original_sleep(0)

        mock_sleep.side_effect = instant_sleep
        mock_data_sleep.side_effect = instant_sleep

        with patch('hl_bot_v2.main.ScoringService') as mock_scoring, \
             patch('hl_bot_v2.main.TradingService') as mock_trading, \
             patch('hl_bot_v2.services.data_service.logger') as mock_logger:

            mock_scoring.return_value.get_top_tradable = MagicMock(return_value=[])

            main_task = asyncio.create_task(main())
            await original_sleep(0.5)
            main_task.cancel()
            try:
                await main_task
            except asyncio.CancelledError:
                pass

            mock_logger.warning.assert_called_with("Websocket connection closed. Reconnecting...")

        mock_universe.assert_called_once() 