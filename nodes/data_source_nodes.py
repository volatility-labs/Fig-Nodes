from typing import Dict, Any, List
import pandas as pd
from data_provider.data_provider import BinanceDataProvider
from services.data_service import DataService
from .base_node import BaseNode
from core.types_registry import get_type, AssetSymbol, AssetClass
from abc import ABC, abstractmethod

class DataServiceNode(BaseNode):
    """
    Initializes and manages the DataService for the graph.
    This node should be one of the first nodes in the graph.
    """
    inputs = {}
    outputs = {"data_service": DataService}
    default_params = {"prewarm_days": 30, "symbols": get_type("AssetSymbolList")}
    
    def __init__(self, node_id: str, params: Dict[str, Any]):
        super().__init__(node_id, params)
        self.data_service: DataService = None

    async def execute(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        if not self.data_service:
            # TODO: Reimplement DataService after services removal
            self.data_service = None  # Placeholder

        return {"data_service": self.data_service}

class KlinesNode(BaseNode):
    """
    Fetches K-line data for a symbol from the DataService.
    """
    inputs = {"data_service": DataService}
    outputs = {"klines_df": pd.DataFrame}
    default_params = {"symbol": get_type("AssetSymbol"), "timeframe": "1h"}
    required_asset_class = AssetClass.CRYPTO
    
    def __init__(self, node_id: str, params: Dict[str, Any]):
        super().__init__(node_id, params)

    async def execute(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        data_service: DataService = inputs.get("data_service")
        if not data_service:
            raise ValueError("DataService not provided to KlinesNode")
            
        symbol: AssetSymbol = self.params.get("symbol")
        timeframe = self.params.get("timeframe")
        
        klines_df = data_service.get_data(str(symbol), timeframe)
        
        return {"klines_df": klines_df} 

class UniverseNode(BaseNode, ABC):
    inputs = {"filter_symbols": get_type("AssetSymbolList")}
    outputs = {"symbols": get_type("AssetSymbolList")}
    optional_inputs = ["filter_symbols"]

    async def execute(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        symbols = await self._fetch_symbols()
        filter_symbols = inputs.get("filter_symbols", [])
        if filter_symbols:
            filter_set = {str(s) for s in filter_symbols}
            symbols = [s for s in symbols if str(s) in filter_set]
        return {"symbols": symbols}
    
    @abstractmethod
    async def _fetch_symbols(self) -> List[AssetSymbol]:
        pass 