from typing import Dict, Any, List
import requests
import logging
from nodes.base_node import BaseNode
import time

logger = logging.getLogger(__name__)

class UniverseNode(BaseNode):
    @property
    def inputs(self) -> List[str]:
        return []

    @property
    def outputs(self) -> List[str]:
        return ['universe']

    def execute(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        attempts = 0
        max_attempts = 5
        backoff = 1
        while attempts < max_attempts:
            response = requests.get('https://fapi.binance.com/fapi/v1/exchangeInfo')
            if response.status_code == 200:
                info = response.json()
                universe = {
                    sym['baseAsset'].upper()
                    for sym in info['symbols']
                    if sym.get('quoteAsset') == 'USDT' and sym.get('contractType') == 'PERPETUAL' and sym.get('status') == 'TRADING'
                }
                return {'universe': universe}
            elif response.status_code == 429:
                logger.warning(f'Rate limit hit for exchange info. Retrying after {backoff} seconds...')
                time.sleep(backoff)
                backoff *= 2
            else:
                logger.error(f'Failed to fetch exchange info: HTTP {response.status_code} - {response.text}')
                return {'universe': set()}
            attempts += 1
        logger.error('Max attempts reached for exchange info. Giving up.')
        return {'universe': set()} 