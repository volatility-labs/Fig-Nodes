import unittest
from unittest.mock import Mock
from ui.graph_executor import GraphExecutor
from ui.server import NODE_REGISTRY  # Assuming access

class TestGraphExecutor(unittest.TestCase):

    def test_simple_graph_execution(self):
        # Mock nodes
        class MockDataNode:
            def __init__(self, id, params):
                pass
            def execute(self, inputs):
                return {'data': 'mock_data'}

        class MockProcessNode:
            def __init__(self, id, params):
                pass
            def execute(self, inputs):
                return {'result': inputs['data'] + '_processed'}

        mock_registry = {
            'MockData': MockDataNode,
            'MockProcess': MockProcessNode
        }

        graph = {
            'nodes': {
                'data': {'type': 'MockData', 'params': {}},
                'process': {'type': 'MockProcess', 'params': {}}
            },
            'connections': [{'from': 'data', 'to': 'process'}]
        }

        executor = GraphExecutor(graph, mock_registry)
        results = executor.execute()
        self.assertIn('process', results)
        self.assertEqual(results['process']['result'], 'mock_data_processed')

if __name__ == '__main__':
    unittest.main() 