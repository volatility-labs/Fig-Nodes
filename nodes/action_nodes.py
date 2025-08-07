from typing import Dict, Any
from services.trading_service import TradingService
from .base_node import BaseNode
from core.types_registry import get_type, AssetClass, AssetSymbol

# TODO: Implement action nodes 

class TradeExecutionNode(BaseNode):
    """
    Executes a trade based on the provided symbol, side, and score.
    """
    inputs = {"symbol": get_type("AssetSymbol"), "score": float}
    outputs = {"trade_result": Dict[str, Any]}
    default_params = {"side": "buy"}
    required_asset_class = AssetClass.CRYPTO

    def __init__(self, node_id: str, params: Dict[str, Any]):
        super().__init__(node_id, params)
        self.trading_service = TradingService()

    async def execute(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        symbol: AssetSymbol = inputs.get("symbol")
        score = inputs.get("score")
        side = self.params.get("side")

        if not all([symbol, score, side]):
            raise ValueError("Missing required inputs for TradeExecutionNode")

        trade_result = self.trading_service.execute_trade(str(symbol), side, score)
        
        return {"trade_result": trade_result} 