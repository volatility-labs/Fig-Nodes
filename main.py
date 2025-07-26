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

    # Fetch universes and find the intersection
    hyperliquid_symbols = await get_hyperliquid_universe()
    binance_symbols = await data_provider.get_tradable_universe()

    if not hyperliquid_symbols:
        logger.error("Could not fetch symbols from Hyperliquid. Exiting.")
        return
    if not binance_symbols:
        logger.warning("Could not fetch symbols from Binance. Proceeding with Hyperliquid-only symbols.")
        symbols_to_trade = list(hyperliquid_symbols)
    else:
        symbols_to_trade = list(hyperliquid_symbols.intersection(binance_symbols))

    logger.info(f"Found {len(hyperliquid_symbols)} symbols on Hyperliquid.")
    logger.info(f"Found {len(binance_symbols)} USDT pairs on Binance.")
    logger.info(f"Trading universe consists of {len(symbols_to_trade)} common symbols.")

    # Exclude known problematic tickers
    _EXCLUDED_TICKERS = ['MAV', 'FTT', 'SOPH', 'AI', 'ILV', 'OM', 'SCR', 'RDNT', 'S', 'CAKE', 'USTC', 'AR', 'BNT', 'WCT', 'BIO']
    symbols_to_trade = [s for s in symbols_to_trade if s not in _EXCLUDED_TICKERS]
    logger.info(f"Final trading universe after exclusions: {len(symbols_to_trade)} symbols.")

    # Initialize new services
    indicators_service = IndicatorsService()
    scoring_service = ScoringService(indicators_service)
    trading_service = TradingService()

    data_service = None

    try:
        symbols_to_trade = ['BTC', 'ETH', 'SOL', 'XRP', 'DOGE', 'ADA']  # Temporary for testing

        logger.info(f"Test mode: Using symbols {symbols_to_trade}")
        logger.info(f"Prewarm: Last 600 bars per timeframe/symbol, Timeframes: 4 per symbol, Total fetch tasks: {len(symbols_to_trade) * 4}")
        logger.info("Note: Actual fetches are simulated (logged intents only) to avoid rate limits.")

        data_service = DataService(data_provider, symbols=symbols_to_trade)
        data_service.scoring_service = scoring_service  # Add reference to data_service

        await data_service.start_continuous_updates()  # Start websocket before prewarming to capture real-time data

        await data_service.prewarm_data()

        await data_service.fill_gaps()  # Fill any potential gaps after prewarming

        # Verify pre-warming and check for gaps
        timeframes = ['1m', '5m', '15m', '1h']
        for symbol in symbols_to_trade:
            for tf in timeframes:
                df = data_service.get_data(symbol, tf)
                if df is not None and not df.empty:
                    logger.info(f"Data for {symbol} on {tf}: {len(df)} klines, from {df.index.min()} to {df.index.max()}")
                    # Check for gaps
                    diffs = df.index.to_series().diff().dropna()
                    expected_diff = pd.Timedelta(tf.replace('m', 'T').replace('h', 'H'))  # e.g., '1m' -> 1 minute
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

        while True:
            # Periodic trading check (every 60 seconds)
            top_tickers = scoring_service.get_top_tradable(4)
            logger.info(f"Top tickers for trading: {top_tickers}")
            for ticker in top_tickers:
                trading_service.execute_trade(ticker['symbol'], 'buy', ticker['score'])  # Example side; replace 'buy' with logic to determine side
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