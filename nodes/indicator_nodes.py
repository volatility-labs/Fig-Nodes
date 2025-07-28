from typing import Dict, Any
import pandas as pd
from services.indicators_service import IndicatorsService
from .base_node import BaseNode

class IndicatorsBundleNode(BaseNode):
    """
    Computes a bundle of indicators for the given k-line data.
    """
    inputs = {"klines_df": pd.DataFrame}
    outputs = {"indicators": Dict[str, Any]}
    default_params = {"timeframe": "1h"}

    def __init__(self, node_id: str, params: Dict[str, Any]):
        super().__init__(node_id, params)
        self.indicators_service = IndicatorsService()

    async def execute(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        klines_df: pd.DataFrame = inputs.get("klines_df")
        if klines_df is None or klines_df.empty:
            return {"indicators": {}}

        timeframe = self.params.get("timeframe")
        indicators = self.indicators_service.compute_indicators(klines_df, timeframe)
        
        return {"indicators": indicators} 