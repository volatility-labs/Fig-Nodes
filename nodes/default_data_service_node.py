
import logging
from datetime import datetime, timedelta, timezone
from typing import Dict, Optional, List, Any
import pandas as pd
import asyncio
import json
import time
import websockets
from websockets.exceptions import ConnectionClosed

from data_provider.data_provider import BinanceDataProvider  # Default provider, configurable
from nodes.base_data_service_node import BaseDataServiceNode

logger = logging.getLogger(__name__)

class DefaultDataServiceNode(BaseDataServiceNode):
    def __init__(self, id: str, params: Dict[str, Any] = None):
        super().__init__(id, params)
        provider_type = params.get('provider_type', 'binance')
        self.data_provider = BinanceDataProvider() if provider_type == 'binance' else None  # Extensible
        self.prewarm_days = params.get('prewarm_days', 30)
        self.data_cache: Dict[str, Dict[str, pd.DataFrame]] = {}
        self.ws_tasks: List[asyncio.Task] = []
        self.semaphore = asyncio.Semaphore(10)
        self.rate_limit_sleep = 0.5
        self.reconnect_delay = 5

    def perform_action(self, symbols: List[str], timeframes: List[str], action: str) -> Dict[str, Any]:
        if action == 'prewarm':
            asyncio.run(self.prewarm_data(symbols, timeframes))
            return {'status': 'prewarmed'}
        elif action == 'get_data':
            results = {}
            for symbol in symbols:
                for tf in timeframes:
                    results[f'{symbol}_{tf}'] = self.get_data(symbol, tf)
            return results
        elif action == 'start_updates':
            asyncio.run(self.start_continuous_updates(symbols, timeframes))
            return {'status': 'updates_started'}
        else:
            raise ValueError(f"Unsupported action: {action}")

    # Ported methods from DataService, made modular
    async def prewarm_data(self, symbols: List[str], timeframes: List[str]):
        self.data_cache = {symbol: {} for symbol in symbols}
        for symbol in symbols:
            for tf in timeframes:
                timespan, multiplier = self.parse_timeframe(tf)  # Assume method exists or add
                await self.fetch_and_cache(symbol, timespan, multiplier)
                await asyncio.sleep(self.rate_limit_sleep)

    async def fetch_and_cache(
        self,
        symbol: str,
        timespan: str,
        multiplier: int = 1,
    ):
        async with self.semaphore:
            timeframe_str = self._get_timeframe_str(timespan, multiplier)  # Assume ported or add method
            interval_delta = self._get_interval_delta(timespan, multiplier)  # Assume ported
            approx_span = interval_delta * 600
            # ... (add logging as in original)
            df = self.data_provider.get_klines_df(symbol, timespan, multiplier, limit=600)  # Use provider
            if df is not None and not df.empty:
                self._update_cache(symbol, timeframe_str, df)  # Assume ported
                logger.info(f"Cached {len(df)} klines for {symbol} on {timeframe_str} timeframe.")
            else:
                logger.warning(f"No data fetched for {symbol} on {timeframe_str} timeframe.")

    def get_data(self, symbol: str, timeframe: str) -> Optional[pd.DataFrame]:
        return self.data_cache.get(symbol, {}).get(timeframe)

    # Add other ported methods like _update_cache, start_continuous_updates, etc., adapted for node context
    # For async, since execute is sync, run asyncio.run() inside perform_action for async actions 

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

    def _update_cache(self, symbol: str, timeframe: str, df: pd.DataFrame):
        if timeframe not in self.data_cache.get(symbol, {}):
            self.data_cache.setdefault(symbol, {})[timeframe] = df
        else:
            combined_df = pd.concat([self.data_cache[symbol][timeframe], df])
            combined_df = combined_df[~combined_df.index.duplicated(keep='last')].sort_index()
            if len(combined_df) > 600:
                combined_df = combined_df.iloc[-600:]
            self.data_cache[symbol][timeframe] = combined_df
        logger.debug(f"Updated cache for {symbol} on {timeframe}: now {len(self.data_cache[symbol][timeframe])} klines") 