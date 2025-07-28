
from typing import Dict, Any, List
from abc import ABC, abstractmethod
import pandas as pd
from nodes.base_node import BaseNode
from nodes.data_provider_nodes import BaseDataProviderNode
from services.data_service import DataService  # Assuming global access for initial implementation; to be made injectable later
from datetime import datetime, timezone
from decimal import Decimal
from typing import List, Tuple, Optional
import requests
import pandas as pd
import time
import logging

logger = logging.getLogger(__name__)

class BinanceDataProviderNode(BaseDataProviderNode):
    default_params = {'symbol': 'BTCUSDT', 'timeframe': '1m'}

    _INTERVALS = {
        ('minute', 1): '1m',
        ('minute', 5): '5m',
        ('minute', 15): '15m',
        ('hour', 1): '1h',
        ('hour', 4): '4h',
        ('day', 1): '1d',
        ('week', 1): '1w',
    }

    _REVERSE_INTERVALS = {v: k for k, v in _INTERVALS.items()}

    def __init__(self, id: str, params: Dict[str, Any] = None, data_service: DataService = None):
        super().__init__(id, params)
        self.data_service = data_service  # Inject or initialize as needed; for now, assume provided

    def set_data_service(self, data_service: DataService):
        self.data_service = data_service

    def parse_timeframe(self, timeframe: str) -> Tuple[str, int]:
        if timeframe in self._REVERSE_INTERVALS:
            return self._REVERSE_INTERVALS[timeframe]
        raise ValueError(f'Unsupported timeframe: {timeframe}')

    def fetch_klines(
        self,
        symbol: str,
        timespan: str,
        multiplier: int = 1,
        limit: int = 1000,
        start: Optional[datetime] = None,
        end: Optional[datetime] = None,
    ) -> List[Tuple[int, Decimal, Decimal, Decimal, Decimal, Decimal]]:
        pair = f'{symbol.upper()}USDT'
        interval_key = (timespan, multiplier)
        if interval_key not in self._INTERVALS:
            raise ValueError(f'Unsupported interval: {timespan} x{multiplier}')
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
                    response = requests.get('https://fapi.binance.com/fapi/v1/klines', params=current_params)
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
                            logger.error(f'Unexpected response format for {pair}: {klines_data}')
                            return []
                    elif response.status_code == 429:
                        logger.warning(f'Rate limit hit for {pair}. Retrying after {backoff} seconds...')
                        time.sleep(backoff)
                        backoff *= 2
                    else:
                        logger.error(f'Failed to fetch klines for {pair}: HTTP {response.status_code} - {response.text}')
                        return []
                    attempts += 1
                else:
                    logger.error(f'Max attempts reached for {pair}. Giving up.')
                    return []
                time.sleep(0.5)
            return all_klines
        else:
            attempts = 0
            max_attempts = 5
            backoff = 1
            while attempts < max_attempts:
                response = requests.get('https://fapi.binance.com/fapi/v1/klines', params=params)
                if response.status_code == 200:
                    klines_data = response.json()
                    if isinstance(klines_data, list):
                        return [
                            (
                                int(kline[0]),
                                Decimal(str(kline[1])),
                                Decimal(str(kline[2])),
                                Decimal(str(kline[3])),
                                Decimal(str(kline[4])),
                                Decimal(str(kline[5])),
                            ) for kline in klines_data
                        ]
                    else:
                        logger.error(f'Unexpected response format for {pair}: {klines_data}')
                        return []
                elif response.status_code == 429:
                    logger.warning(f'Rate limit hit for {pair}. Retrying after {backoff} seconds...')
                    time.sleep(backoff)
                    backoff *= 2
                else:
                    logger.error(f'Failed to fetch klines for {pair}: HTTP {response.status_code} - {response.text}')
                    return []
                attempts += 1
            logger.error(f'Max attempts reached for {pair}. Giving up.')
            return []

    def get_klines_df(
        self,
        symbol: str,
        timespan: str,
        multiplier: int = 1,
        limit: int = 1000,
        start: Optional[datetime] = None,
        end: Optional[datetime] = None,
    ) -> Optional[pd.DataFrame]:
        klines = self.fetch_klines(symbol, timespan, multiplier, limit, start, end)
        if not klines:
            return None
        df = pd.DataFrame(klines, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms', utc=True)
        df.set_index('timestamp', inplace=True)
        return df

    def fetch_data(self, symbol: str, timeframe: str) -> pd.DataFrame:
        df = None
        if self.data_service:
            df = self.data_service.get_data(symbol, timeframe)
        if df is None or df.empty:
            timespan, multiplier = self.parse_timeframe(timeframe)
            df = self.get_klines_df(symbol, timespan, multiplier, limit=1000)
            if df is None or df.empty:
                raise ValueError(f'Data not available for {symbol} on {timeframe}')
        return df 