from datetime import datetime, timezone
from decimal import Decimal
from typing import List, Tuple, Optional, AsyncGenerator
import logging
import asyncio
import json
import websockets
from decimal import Decimal
from datetime import datetime, timezone
import requests
import pandas as pd

logger = logging.getLogger(__name__)

class BinanceDataProvider:
    """
    Provides historical and real-time market data from Binance.
    """

    _INTERVALS = {
        ("minute", 1): "1m",
        ("minute", 5): "5m",
        ("minute", 15): "15m",
        ("hour", 1): "1h",
        ("hour", 4): "4h",
        ("day", 1): "1d",
        ("week", 1): "1w",
    }

    def __init__(self):
        pass

    async def fetch_klines(
        self,
        symbol: str,
        timespan: str,
        multiplier: int = 1,
        limit: int = 1000,
        start: Optional[datetime] = None,
        end: Optional[datetime] = None,
    ) -> List[Tuple[int, Decimal, Decimal, Decimal, Decimal, Decimal]]:
        """
        Fetches historical k-line (candlestick) data for a symbol.

        Args:
            symbol: The trading symbol (e.g., 'BTC').
            timespan: The timespan for each k-line ('minute', 'hour', 'day', 'week').
            multiplier: The multiplier for the timespan (e.g., 5 for 5 minutes).
            limit: The number of k-lines to fetch (default 1000, max 1500).
            start: Optional start datetime for the data range.
            end: Optional end datetime for the data range.

        Returns:
            A list of tuples, each representing a k-line with
            (timestamp_ms, open, high, low, close, volume).
        """
        pair = f"{symbol.upper()}USDT"
        interval_key = (timespan, multiplier)
        if interval_key not in self._INTERVALS:
            raise ValueError(f"Unsupported interval: {timespan} x{multiplier}")
        
        interval = self._INTERVALS[interval_key]
        
        params = {
            'symbol': pair,
            'interval': interval,
            'limit': min(limit, 1500)
        }
        if start and end:
            params['startTime'] = int(start.replace(tzinfo=timezone.utc).timestamp() * 1000)
            params['endTime'] = int(end.replace(tzinfo=timezone.utc).timestamp() * 1000)
            all_klines = []
            start_ms = params['startTime']
            end_ms = params['endTime']
            while start_ms < end_ms:
                current_params = params.copy()
                current_params['startTime'] = start_ms
                attempts = 0
                max_attempts = 5
                backoff = 1
                while attempts < max_attempts:
                    response = await asyncio.to_thread(
                        requests.get,
                        'https://fapi.binance.com/fapi/v1/klines',
                        params=current_params
                    )
                    if response.status_code == 200:
                        klines_data = response.json()
                        if isinstance(klines_data, list):
                            for kline in klines_data:
                                all_klines.append(
                                    (
                                        int(kline[0]),
                                        Decimal(str(kline[1])),
                                        Decimal(str(kline[2])),
                                        Decimal(str(kline[3])),
                                        Decimal(str(kline[4])),
                                        Decimal(str(kline[5])),
                                    )
                                )
                            if klines_data:
                                last_kline_ts = klines_data[-1][0]
                                start_ms = last_kline_ts + 1
                            else:
                                break
                            break
                        else:
                            logger.error(f"Unexpected response format for {pair}: {klines_data}")
                            return []
                    elif response.status_code == 429:
                        logger.warning(f"Rate limit hit for {pair}. Retrying after {backoff} seconds...")
                        await asyncio.sleep(backoff)
                        backoff *= 2
                    else:
                        logger.error(f"Failed to fetch klines for {pair}: HTTP {response.status_code} - {response.text}")
                        return []
                    attempts += 1
                else:
                    logger.error(f"Max attempts reached for {pair}. Giving up.")
                    return []
                await asyncio.sleep(0.5)
            if all_klines:
                return all_klines
            else:
                logger.warning(f"No klines data retrieved for {pair} in the specified range.")
                return []
        else:
            # Fetch most recent klines with limit
            attempts = 0
            max_attempts = 5
            backoff = 1
            while attempts < max_attempts:
                response = await asyncio.to_thread(
                    requests.get,
                    'https://fapi.binance.com/fapi/v1/klines',
                    params=params
                )
                if response.status_code == 200:
                    klines_data = response.json()
                    if isinstance(klines_data, list):
                        all_klines = [
                            (
                                int(kline[0]),
                                Decimal(str(kline[1])),
                                Decimal(str(kline[2])),
                                Decimal(str(kline[3])),
                                Decimal(str(kline[4])),
                                Decimal(str(kline[5])),
                            ) for kline in klines_data
                        ]
                        return all_klines
                    else:
                        logger.error(f"Unexpected response format for {pair}: {klines_data}")
                        return []
                elif response.status_code == 429:
                    logger.warning(f"Rate limit hit for {pair}. Retrying after {backoff} seconds...")
                    await asyncio.sleep(backoff)
                    backoff *= 2
                else:
                    logger.error(f"Failed to fetch klines for {pair}: HTTP {response.status_code} - {response.text}")
                    return []
                attempts += 1
            else:
                logger.error(f"Max attempts reached for {pair}. Giving up.")
                return []
        
        return all_klines
    
    async def get_klines_df(
        self,
        symbol: str,
        timespan: str,
        multiplier: int = 1,
        limit: int = 1000,
        start: Optional[datetime] = None,
        end: Optional[datetime] = None,
    ) -> Optional[pd.DataFrame]:
        """
        Fetches historical k-lines and returns them as a pandas DataFrame.
        """
        klines = await self.fetch_klines(symbol, timespan, multiplier, limit, start, end)
        if not klines:
            return None
        
        df = pd.DataFrame(klines, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms', utc=True)
        df.set_index('timestamp', inplace=True)
        return df

    async def get_tradable_universe(self) -> set[str]:
        """
        Fetches the set of baseAsset symbols that trade against USDT on Binance.

        Returns:
            A set of upper-cased base asset symbols.
        """
        try:
            attempts = 0
            max_attempts = 5
            backoff = 1
            while attempts < max_attempts:
                response = await asyncio.to_thread(requests.get, 'https://fapi.binance.com/fapi/v1/exchangeInfo')
                if response.status_code == 200:
                    info = response.json()
                    return {
                        sym["baseAsset"].upper()
                        for sym in info["symbols"]
                        if sym.get("quoteAsset") == "USDT" and sym.get("contractType") == "PERPETUAL" and sym.get("status") == "TRADING"
                    }
                elif response.status_code == 429:
                    logger.warning(f"Rate limit hit for exchange info. Retrying after {backoff} seconds...")
                    await asyncio.sleep(backoff)
                    backoff *= 2
                else:
                    logger.error(f"Failed to fetch exchange info: HTTP {response.status_code} - {response.text}")
                    return set()
                attempts += 1
            else:
                logger.error("Max attempts reached for exchange info. Giving up.")
                return set()
        except Exception as e:
            logger.error(f"Failed to fetch tradable universe from Binance: {e}")
            return set()

    async def stream_klines(self, streams: list[str]) -> AsyncGenerator[dict, None]:
        url = "wss://fstream.binance.com/stream"
        while True:  # Reconnection loop
            try:
                async with websockets.connect(url, ping_interval=180, ping_timeout=600) as ws:  # Ping every 3 min, timeout 10 min
                    subscribe_msg = {
                        "method": "SUBSCRIBE",
                        "params": streams,
                        "id": 1
                    }
                    await ws.send(json.dumps(subscribe_msg))
                    
                    while True:
                        try:
                            message = await asyncio.wait_for(ws.recv(), timeout=600)  # 10 min timeout
                            yield json.loads(message)
                        except asyncio.TimeoutError:
                            # Send unsolicited pong to keep connection alive
                            await ws.pong()
                        except websockets.ConnectionClosed:
                            logger.warning("Websocket connection closed. Reconnecting...")
                            break
            except Exception as e:
                logger.error(f"Websocket error: {e}. Reconnecting in 5 seconds...")
                await asyncio.sleep(5)

    async def close(self):
        logger.info('Binance client connection closed.') 