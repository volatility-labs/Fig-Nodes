import logging

logger = logging.getLogger(__name__)

class TradingService:
    def __init__(self):
        pass

    def execute_trade(self, symbol: str, side: str, score: float):
        logger.info(f'Executing trade for {symbol}: Side={side}, Score={score}')