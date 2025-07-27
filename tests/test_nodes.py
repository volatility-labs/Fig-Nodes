import unittest
from unittest.mock import Mock, patch
import pandas as pd
from nodes.data_provider_nodes import BaseDataProviderNode, BinanceDataProviderNode
from nodes.indicators_nodes import BaseIndicatorsNode, DefaultIndicatorsNode
from nodes.scoring_nodes import BaseScoringNode, DefaultScoringNode
from nodes.trading_nodes import BaseTradingNode, DefaultTradingNode
from services.data_service import DataService
from indicators.indicators_service import IndicatorsService
from services.scoring_service import ScoringService
from services.trading_service import TradingService

class TestNodes(unittest.TestCase):

    def test_binance_data_provider_node(self):
        mock_service = Mock(spec=DataService)
        mock_df = pd.DataFrame({'close': [1, 2]})
        mock_service.get_data.return_value = mock_df
        node = BinanceDataProviderNode('test', {}, mock_service)
        result = node.execute({'symbol': 'BTC', 'timeframe': '1h'})
        self.assertEqual(result['data'], mock_df)

    def test_default_indicators_node(self):
        mock_service = Mock(spec=IndicatorsService)
        mock_indicators = {'hurst': 0.5}
        mock_service.compute_indicators.return_value = mock_indicators
        node = DefaultIndicatorsNode('test', {'timeframe': '1h'}, mock_service)
        mock_df = pd.DataFrame()
        result = node.execute({'data': mock_df})
        self.assertEqual(result['indicators'], mock_indicators)

    def test_default_scoring_node(self):
        mock_service = Mock(spec=ScoringService)
        mock_service.compute_score.return_value = 80.0
        node = DefaultScoringNode('test', {}, mock_service)
        mock_indicators = {'hurst': 0.5}
        result = node.execute({'indicators': mock_indicators})
        self.assertEqual(result['score'], 80.0)

    @patch('nodes.data_provider_nodes.BinanceDataProviderNode.get_klines_df')
    def test_binance_data_provider_node_without_service(self, mock_get_df):
        mock_df = pd.DataFrame({'close': [3, 4]})
        mock_get_df.return_value = mock_df
        node = BinanceDataProviderNode('test', {})
        result = node.execute({'symbol': 'BTC', 'timeframe': '1h'})
        self.assertEqual(result['data'], mock_df)
        mock_get_df.assert_called_with('BTC', 'hour', 1, limit=1000)

    def test_set_data_service(self):
        node = BinanceDataProviderNode('test', {})
        mock_service = Mock(spec=DataService)
        node.set_data_service(mock_service)
        self.assertEqual(node.data_service, mock_service)

    def test_default_trading_node(self):
        mock_service = Mock(spec=TradingService)
        node = DefaultTradingNode('test', {'side': 'buy'}, mock_service)
        result = node.execute({'symbol': 'BTC', 'score': 80.0})
        self.assertIn('trade_result', result)
        mock_service.execute_trade.assert_called_with('BTC', 'buy', 80.0)

if __name__ == '__main__':
    unittest.main() 