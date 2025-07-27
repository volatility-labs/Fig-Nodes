import logging
from datetime import datetime, timedelta, timezone
from typing import Dict, Optional, List
import pandas as pd
import asyncio
import json
import time
import websockets
from websockets.exceptions import ConnectionClosed

from ..data_provider.data_provider import BinanceDataProvider

logger = logging.getLogger(__name__)

class DataService:
    """
    Manages historical data caching and continuous data updates for the bot.
    """

    def __init__(self, data_provider: BinanceDataProvider, symbols: list[str], prewarm_days: int = 30):
        self.data_provider = data_provider
        self.symbols = symbols
        self.prewarm_days = prewarm_days
        self.data_cache: Dict[str, Dict[str, pd.DataFrame]] = {symbol: {} for symbol in symbols}
        self.ws_tasks: List[asyncio.Task] = []
        self.semaphore = asyncio.Semaphore(10)  # Increased for more concurrency
        self.rate_limit_sleep = 0.5
        self.reconnect_delay = 5

    async def prewarm_data(self):
        """
        Fetches the last 600 historical klines for all symbols and timeframes to warm up the cache.
        """
        logger.info("Starting data pre-warming...")
        logger.info(f"Semaphore limit: {self.semaphore._value}, Symbols: {len(self.symbols)}, Timeframes per symbol: 4")
        
        for symbol in self.symbols:
            for timespan, multiplier in [("hour", 1), ("minute", 1), ("minute", 5), ("minute", 15)]:
                await self.fetch_and_cache(symbol, timespan, multiplier)
                await asyncio.sleep(self.rate_limit_sleep)
        
        logger.info("Data pre-warming completed.")

    async def fetch_and_cache(
        self,
        symbol: str,
        timespan: str,
        multiplier: int = 1,
    ):
        """
        Fetches the last 600 klines for a single symbol and timeframe and stores it in the cache.
        """
        async with self.semaphore:
            timeframe_str = self._get_timeframe_str(timespan, multiplier)
            interval_delta = self._get_interval_delta(timespan, multiplier)
            approx_span = interval_delta * 600
            approx_days = approx_span.days
            approx_hours = approx_span.seconds // 3600
            approx_minutes = (approx_span.seconds % 3600) // 60

            logger.info(f"Fetching last 600 klines for {symbol} on {timeframe_str}: "
                        f"Interval: {interval_delta}, "
                        f"Approximate span: {approx_days} days, {approx_hours} hours, {approx_minutes} minutes")

            df = await self.data_provider.get_klines_df(symbol, timespan, multiplier, limit=600)

            if df is not None and not df.empty:
                self._update_cache(symbol, timeframe_str, df)
                logger.info(f"Cached {len(df)} klines for {symbol} on {timeframe_str} timeframe.")
            else:
                logger.warning(f"No data fetched for {symbol} on {timeframe_str} timeframe.")

    def _update_cache(self, symbol: str, timeframe: str, df: pd.DataFrame):
        if timeframe not in self.data_cache[symbol]:
            self.data_cache[symbol][timeframe] = df
        else:
            combined_df = pd.concat([self.data_cache[symbol][timeframe], df])
            combined_df = combined_df[~combined_df.index.duplicated(keep='last')].sort_index()
            # Limit to last 600 bars (FIFO)
            if len(combined_df) > 600:
                combined_df = combined_df.iloc[-600:]
            self.data_cache[symbol][timeframe] = combined_df
        logger.debug(f"Updated cache for {symbol} on {timeframe}: now {len(self.data_cache[symbol][timeframe])} klines, from {self.data_cache[symbol][timeframe].index.min()} to {self.data_cache[symbol][timeframe].index.max()}")

    def get_data(self, symbol: str, timeframe: str) -> Optional[pd.DataFrame]:
        """
        Retrieves data for a symbol and timeframe from the cache.
        """
        return self.data_cache.get(symbol, {}).get(timeframe)

    def _get_timeframe_str(self, timespan: str, multiplier: int) -> str:
        span_map = {"minute": "m", "hour": "h", "day": "d", "week": "w"}
        return f"{multiplier}{span_map.get(timespan, '')}"

    def _get_interval_delta(self, timespan: str, multiplier: int) -> timedelta:
        if timespan == 'minute':
            return timedelta(minutes=multiplier)
        elif timespan == 'hour':
            return timedelta(hours=multiplier)
        elif timespan == 'day':
            return timedelta(days=multiplier)
        elif timespan == 'week':
            return timedelta(weeks=multiplier)
        else:
            raise ValueError(f"Unsupported timespan: {timespan}")

    async def _kline_handler(self, msg: Dict):
        """
        Handles incoming kline messages from the websocket.
        """
        if msg.get('e') == 'error':
            logger.error(f"Websocket error: {msg}")
            return
            
        kline = msg.get('k')
        if not kline:
            return
            
        symbol = kline['s'][:-4].upper() # Remove 'USDT' and uppercase
        
        if kline['x']: # Is kline closed?
            timeframe_str = kline['i']
            logger.info(f"Received closed kline for {symbol} on {timeframe_str} timeframe.")
            
            new_kline_df = pd.DataFrame([{
                'timestamp': pd.to_datetime(kline['t'], unit='ms', utc=True),
                'open': float(kline['o']),
                'high': float(kline['h']),
                'low': float(kline['l']),
                'close': float(kline['c']),
                'volume': float(kline['v'])
            }]).set_index('timestamp')

            self._update_cache(symbol, timeframe_str, new_kline_df)
            logger.debug(f"Updated cache for {symbol} on {timeframe_str} with new kline.")
            # Trigger scoring update
            df = self.get_data(symbol, timeframe_str)
            if df is not None:
                self.scoring_service.update_score(symbol, timeframe_str, df)

    async def start_continuous_updates(self):
        """
        Starts websocket connections to receive continuous k-line updates.
        """
        logger.info("Starting continuous data updates via websockets...")
        

        # Subscribe to all required timeframes for all symbols
        timeframes = ["1m", "5m", "15m", "1h"]
        self.ws_streams = [f"{symbol.lower()}usdt@kline_{tf}" for symbol in self.symbols for tf in timeframes]
        
        self.ws_tasks.append(asyncio.create_task(self._socket_listener()))

    async def _socket_listener(self):
        while True:
            socket = self.data_provider.stream_klines(self.ws_streams)
            try:
                async for msg in socket:
                    if 'data' in msg:
                        await self._kline_handler(msg['data'])
            except ConnectionClosed:
                # Specific websocket closure detected; reconnection will be handled in finally.
                pass
            except Exception as e:
                logger.error(f"Socket listener error: {e}. Attempting to restart stream...")
            finally:
                # Always log reconnection intent, regardless of how the stream ended.
                logger.warning("Websocket connection closed. Reconnecting...")
                if self.reconnect_delay:
                    await asyncio.sleep(self.reconnect_delay)

    async def fill_gaps(self):
        """
        Fills any potential gaps in the data cache after prewarming by fetching missing klines from the last cached timestamp to now.
        """
        tasks = []
        timeframes = [("minute", 1), ("minute", 5), ("minute", 15), ("hour", 1)]
        interval_deltas = {
            ("minute", 1): timedelta(minutes=1),
            ("minute", 5): timedelta(minutes=5),
            ("minute", 15): timedelta(minutes=15),
            ("hour", 1): timedelta(hours=1),
        }

        for symbol in self.symbols:
            for timespan, multiplier in timeframes:
                timeframe_str = self._get_timeframe_str(timespan, multiplier)
                df = self.get_data(symbol, timeframe_str)
                if df is None or df.empty:
                    logger.warning(f"No data in cache for {symbol} on {timeframe_str} before gap fill")
                    continue

                last_ts = df.index.max()
                now = datetime.now(timezone.utc)
                delta = interval_deltas[(timespan, multiplier)]
                buffer = timedelta(minutes=1)  # Safety buffer for timing

                if now - last_ts > delta + buffer:
                    gap_size = now - last_ts
                    logger.info(f"Gap detected for {symbol} on {timeframe_str}: from {last_ts} to {now} (size: {gap_size})")
                    tasks.append(self._fetch_gap(symbol, timespan, multiplier, last_ts + timedelta(milliseconds=1), now))
                else:
                    logger.debug(f"No significant gap for {symbol} on {timeframe_str} (last: {last_ts}, now: {now})")

        if tasks:
            for task in tasks:
                await task
                await asyncio.sleep(self.rate_limit_sleep)
            logger.info("Gap filling completed.")
        else:
            logger.info("No gaps to fill.")

    async def _fetch_gap(
        self,
        symbol: str,
        timespan: str,
        multiplier: int,
        start: datetime,
        end: datetime,
    ):
        timeframe_str = self._get_timeframe_str(timespan, multiplier)
        duration = end - start
        interval_delta = self._get_interval_delta(timespan, multiplier)
        expected_klines = int(duration / interval_delta) + 1
        max_per_call = 1500
        expected_chunks = (expected_klines + max_per_call - 1) // max_per_call

        logger.info(f"Filling gap for {symbol} on {timeframe_str}: "
                    f"From {start} to {end} (duration: {duration}), "
                    f"Interval: {interval_delta}, "
                    f"Expected klines: {expected_klines}, "
                    f"Expected API chunks: {expected_chunks}")

        df = await self.data_provider.get_klines_df(symbol, timespan, multiplier, limit=1500, start=start, end=end)

        if df is not None and not df.empty:
            self._update_cache(symbol, timeframe_str, df)
            logger.info(f"Filled {len(df)} missing klines for {symbol} on {timeframe_str}.")
        elif df is None:
            logger.warning(f"Failed to fetch gap data for {symbol} on {timeframe_str}.")
        else:
            logger.info(f"No missing data for {symbol} on {timeframe_str} in the specified range.")


    async def close(self):
        """Shuts down the data service and its provider."""
        for task in self.ws_tasks:
            task.cancel()
        if self.ws_tasks:
            await asyncio.gather(*self.ws_tasks, return_exceptions=True)
        
        await self.data_provider.close()
        logger.info("Data service shut down.") 