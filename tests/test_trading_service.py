
import logging
from unittest.mock import patch
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from hl_bot_v2.services.trading_service import TradingService

def test_execute_trade(caplog):
    caplog.set_level(logging.INFO)
    trading = TradingService()
    trading.execute_trade('BTC', 'buy', 85.0)
    assert "Executing trade for BTC: Side=buy, Score=85.0" in caplog.text 