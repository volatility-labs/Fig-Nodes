from typing import Dict, Any, List
from abc import ABC, abstractmethod
from nodes.base_node import BaseNode
from services.trading_service import TradingService

class BaseTradingNode(BaseNode, ABC):
    @property
    def inputs(self) -> List[str]:
        return ['symbol', 'score']

    @property
    def outputs(self) -> List[str]:
        return ['trade_result']

    @abstractmethod
    def execute_trade(self, symbol: str, score: float) -> Dict[str, Any]:
        """Abstract method to execute a trade based on symbol and score."""
        pass

    def execute(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        if not self.validate_inputs(inputs):
            raise ValueError(f"Missing inputs for node {self.id}: {self.inputs}")
        symbol = inputs['symbol']
        score = inputs['score']
        side = self.params.get('side', 'buy')  # Example param for side
        try:
            result = self.execute_trade(symbol, score)
            return {'trade_result': result}
        except Exception as e:
            raise RuntimeError(f"Error in {self.id} execution: {str(e)}") from e

class DefaultTradingNode(BaseTradingNode):
    default_params = {'side': 'buy'}

    def __init__(self, id: str, params: Dict[str, Any] = None, trading_service: TradingService = None):
        super().__init__(id, params)
        self.trading_service = trading_service or TradingService()  # Default instance

    def execute_trade(self, symbol: str, score: float) -> Dict[str, Any]:
        side = self.params.get('side', 'buy')
        self.trading_service.execute_trade(symbol, side, score)
        return {'status': 'executed', 'symbol': symbol, 'side': side, 'score': score} 