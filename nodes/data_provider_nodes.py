from typing import Dict, Any, List
from abc import ABC, abstractmethod
import pandas as pd
from nodes.base_node import BaseNode
from datetime import datetime, timezone
from decimal import Decimal
from typing import List, Tuple, Optional
import requests
import pandas as pd
import time
import logging

logger = logging.getLogger(__name__)

class BaseDataProviderNode(BaseNode, ABC):
    @property
    def inputs(self) -> List[str]:
        return ['symbol', 'timeframe']

    @property
    def outputs(self) -> List[str]:
        return ['data']

    @abstractmethod
    def fetch_data(self, symbol: str, timeframe: str) -> pd.DataFrame:
        """Abstract method to fetch data for a symbol and timeframe."""
        pass

    def execute(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        if not self.validate_inputs(inputs):
            raise ValueError(f"Missing inputs for node {self.id}: {self.inputs}")
        symbol = inputs['symbol']
        timeframe = inputs['timeframe']
        try:
            data = self.fetch_data(symbol, timeframe)
            if data is None or data.empty:
                raise ValueError(f"No data fetched for {symbol} on {timeframe}")
            return {'data': data}
        except Exception as e:
            raise RuntimeError(f"Error in {self.id} execution: {str(e)}") from e 