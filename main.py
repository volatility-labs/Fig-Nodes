import logging
import asyncio
from dotenv import load_dotenv
import os
import sys

import pandas as pd

from hyperliquid.info import Info
from hyperliquid.utils.constants import MAINNET_API_URL

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from hl_bot_v2.data_provider.data_provider import BinanceDataProvider
from hl_bot_v2.services.data_service import DataService
from hl_bot_v2.indicators.indicators_service import IndicatorsService
from hl_bot_v2.services.scoring_service import ScoringService
from hl_bot_v2.services.trading_service import TradingService
from ui.graph_executor import GraphExecutor
from ui.server import NODE_REGISTRY  # Reuse registry from server
from nodes.data_provider_nodes import BinanceDataProviderNode
from ui.node_registry import NODE_REGISTRY


async def get_hyperliquid_universe() -> set[str]:
    """Fetches the universe of tradable assets from Hyperliquid."""
    try:
        info = Info(MAINNET_API_URL)
        universe = info.meta().get("universe", [])
        return {asset.get("name", "").upper() for asset in universe}
    except Exception as e:
        logging.getLogger(__name__).error(f"Failed to fetch Hyperliquid universe: {e}")
        return set()


async def main():
    """
    Main entry point for the Hyperliquid V2 trading bot.
    """
    load_dotenv()
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    logger = logging.getLogger(__name__)

    logger.info("Starting Hyperliquid V2 Trading Bot...")

    data_provider = BinanceDataProvider()
    symbols = NODE_REGISTRY['UniverseNode']('temp').execute({})['universe']
    data_service = DataService(data_provider, list(symbols))

    # Initialize new services
    indicators_service = IndicatorsService()
    scoring_service = ScoringService(indicators_service)
    trading_service = TradingService()

    data_service.scoring_service = scoring_service  # Add reference to data_service

    await data_service.start_continuous_updates()  # Start websocket before prewarming to capture real-time data

    await data_service.prewarm_data()

    await data_service.fill_gaps()  # Fill any potential gaps after prewarming

    # Verify pre-warming and check for gaps
    timeframes = ['1m', '5m', '15m', '1h']
    for symbol in symbols:
        for tf in timeframes:
            df = data_service.get_data(symbol, tf)
            if df is not None and not df.empty:
                logger.info(f"Data for {symbol} on {tf}: {len(df)} klines, from {df.index.min()} to {df.index.max()}")
                # Check for gaps
                diffs = df.index.to_series().diff().dropna()
                expected_diff = pd.Timedelta(tf.replace('m', 'min'))  # e.g., '1m' -> 1 minute
                gaps = diffs[diffs > expected_diff]
                if not gaps.empty:
                    logger.warning(f"Gaps detected for {symbol} on {tf}: {len(gaps)} instances")
                    for gap_start, gap_size in gaps.items():
                        logger.warning(f"Gap from {gap_start - gap_size} to {gap_start} (size: {gap_size})")
                else:
                    logger.info(f"No gaps detected for {symbol} on {tf}")
            else:
                logger.warning(f"No data for {symbol} on {tf}")

    logger.info("Bot is running with real-time data updates. Press Ctrl+C to stop.")

    try:
        while True:
            # Periodic trading check (every 60 seconds)
            # top_tickers = scoring_service.get_top_tradable(4)
            # logger.info(f"Top tickers for trading: {top_tickers}")
            # for ticker in top_tickers:
            #     trading_service.execute_trade(ticker['symbol'], 'buy', ticker['score'])  # Example side; replace 'buy' with logic to determine side

            # Example graph: Simple chain for one symbol (expand to full workflow)
            example_graph = {
                'nodes': {
                    'data_service': {'type': 'DefaultDataServiceNode', 'params': {'prewarm_days': 30}},
                    'data': {'type': 'BinanceDataProviderNode', 'params': {'symbol': 'BTC', 'timeframe': '1h'}},
                    'indicators': {'type': 'DefaultIndicatorsNode', 'params': {'timeframe': '1h'}},
                    'scoring': {'type': 'DefaultScoringNode'},
                    'trading': {'type': 'DefaultTradingNode', 'params': {'side': 'buy'}}
                },
                'connections': [
                    {'from': 'data_service', 'to': 'data', 'output': 'result', 'input': 'data_service'},
                    {'from': 'data', 'to': 'indicators', 'output': 'data', 'input': 'data'},
                    {'from': 'indicators', 'to': 'scoring', 'output': 'indicators', 'input': 'indicators'},
                    {'from': 'scoring', 'to': 'trading', 'output': 'score', 'input': 'score'}
                ]
            }
            executor = GraphExecutor(example_graph, NODE_REGISTRY)
            # Inject services
            for node_id, node in executor.nodes.items():
                if node_id == 'data':
                    # Assuming data node can take data_service output; adjust as per design
                    pass
                if isinstance(node, BinanceDataProviderNode):
                    node.set_data_service(data_service)
            results = executor.execute()
            logger.info(f'Graph execution results: {results}')

            await asyncio.sleep(60)  # Check every minute
    except asyncio.CancelledError:
        logger.info("Main task cancelled.")
    except Exception as e:
        logger.error(f"An error occurred during bot execution: {e}", exc_info=True)
    finally:
        if data_service:
            await data_service.close()
        if data_provider:
            await data_provider.close()
        logger.info("Bot has been shut down.")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logging.getLogger().info("Bot stopped by user.") 