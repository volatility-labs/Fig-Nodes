from typing import Dict, Any, List
import pandas as pd
from services.data_service import DataService
from data_provider.data_provider import BinanceDataProvider
from .base_node import BaseNode

class DataServiceNode(BaseNode):
    """
    Initializes and manages the DataService for the graph.
    This node should be one of the first nodes in the graph.
    """
    inputs = {}
    outputs = {"data_service": DataService}
    default_params = {"prewarm_days": 30, "symbols": []}
    
    def __init__(self, node_id: str, params: Dict[str, Any]):
        super().__init__(node_id, params)
        self.data_service: DataService = None

    async def execute(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        if not self.data_service:
            symbols = self.params.get("symbols")
            if not symbols:
                raise ValueError("No symbols provided for DataServiceNode")
            
            data_provider = BinanceDataProvider()
            self.data_service = DataService(
                data_provider,
                symbols,
                self.params.get("prewarm_days")
            )
            await self.data_service.prewarm_data()
            await self.data_service.fill_gaps()
            await self.data_service.start_continuous_updates()

        return {"data_service": self.data_service}

class KlinesNode(BaseNode):
    """
    Fetches K-line data for a symbol from the DataService.
    """
    inputs = {"data_service": DataService}
    outputs = {"klines_df": pd.DataFrame}
    default_params = {"symbol": "BTC", "timeframe": "1h"}
    
    def __init__(self, node_id: str, params: Dict[str, Any]):
        super().__init__(node_id, params)

    async def execute(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        data_service: DataService = inputs.get("data_service")
        if not data_service:
            raise ValueError("DataService not provided to KlinesNode")
            
        symbol = self.params.get("symbol")
        timeframe = self.params.get("timeframe")
        
        klines_df = data_service.get_data(symbol, timeframe)
        
        return {"klines_df": klines_df} 