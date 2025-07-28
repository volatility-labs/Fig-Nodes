from typing import Dict, Any
from services.trading_service import TradingService
from .base_node import BaseNode

# TODO: Implement action nodes 

class TradeExecutionNode(BaseNode):
    """
    Executes a trade based on the provided symbol, side, and score.
    """
    inputs = {"symbol": str, "score": float}
    outputs = {"trade_result": Dict[str, Any]}
    default_params = {"side": "buy"}

    def __init__(self, node_id: str, params: Dict[str, Any]):
        super().__init__(node_id, params)
        self.trading_service = TradingService()

    async def execute(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        symbol = inputs.get("symbol")
        score = inputs.get("score")
        side = self.params.get("side")

        if not all([symbol, score, side]):
            raise ValueError("Missing required inputs for TradeExecutionNode")

        # In a real implementation, this would return the result of the trade
        trade_result = self.trading_service.execute_trade(symbol, side, score)
        
        return {"trade_result": trade_result} 