import logging
import asyncio
from dotenv import load_dotenv
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from core.graph_executor import GraphExecutor
from core.node_registry import NODE_REGISTRY

async def main():
    """
    Main entry point for the Hyperliquid V2 trading bot.
    """
    load_dotenv()
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    logger = logging.getLogger(__name__)

    logger.info("Starting Hyperliquid V2 Trading Bot...")

    # Define the trading logic as a graph
    trading_graph = {
        'nodes': [
            {'id': 1, 'type': 'DataServiceNode', 'properties': {'prewarm_days': 30}},
            {'id': 2, 'type': 'UniverseNode', 'properties': {}},
            {'id': 3, 'type': 'ForEachNode', 'properties': {}},
            {'id': 4, 'type': 'KlinesNode', 'properties': {'timeframe': '1h'}},
            {'id': 5, 'type': 'IndicatorsBundleNode', 'properties': {'timeframe': '1h'}},
            {'id': 6, 'type': 'ScoreNode', 'properties': {}},
            {'id': 7, 'type': 'TradeExecutionNode', 'properties': {'side': 'buy'}}
        ],
        'links': [
            # Connect DataService to KlinesNode
            [1, 1, 0, 4, 0, 'data_service'],
            # Connect UniverseNode to ForEachNode
            [2, 2, 0, 3, 0, 'list'],
            # Inside the loop: connect item (symbol) to KlinesNode
            [3, 3, 0, 4, 1, 'symbol'],
            # Connect KlinesNode to IndicatorsBundleNode
            [4, 4, 0, 5, 0, 'klines_df'],
            # Connect IndicatorsBundleNode to ScoreNode
            [5, 5, 0, 6, 0, 'indicators'],
            # Connect ScoreNode to TradeExecutionNode
            [6, 6, 0, 7, 1, 'score'],
            # Also connect the item (symbol) to the TradeExecutionNode
            [7, 3, 0, 7, 0, 'symbol'],
        ]
    }

    executor = GraphExecutor(trading_graph, NODE_REGISTRY)

    logger.info("Bot is running. Press Ctrl+C to stop.")

    try:
        while True:
            logger.info("Executing trading graph...")
            results = await executor.execute()
            logger.info(f'Graph execution results: {results}')
            
            await asyncio.sleep(60)  # Run graph every minute
            
    except asyncio.CancelledError:
        logger.info("Main task cancelled.")
    except Exception as e:
        logger.error(f"An error occurred during bot execution: {e}", exc_info=True)
    finally:
        # In a real application, you'd want to gracefully close services.
        # This might involve a special "shutdown" node or logic here.
        logger.info("Bot has been shut down.")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logging.getLogger().info("Bot stopped by user.") 