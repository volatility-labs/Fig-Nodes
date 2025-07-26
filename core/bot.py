import logging
import asyncio
from typing import Dict, Any

from ..services.data_service import DataService
# from ..services.trading_service import TradingService
# from ..models.settings import BotSettings

logger = logging.getLogger(__name__)

class TradingBot:
    """
    The core of the trading bot.
    Manages the main trading loop, strategy execution, and risk management.
    """

    def __init__(self, settings: Dict[str, Any], data_service: DataService):
        # self.settings = settings
        self.data_service = data_service
        # self.trading_service = trading_service
        self.is_running = False

    async def run(self):
        """
        The main event loop for the trading bot.
        """
        self.is_running = True
        logger.info("Trading bot is now running.")

        # Pre-warm data before starting the main loop
        await self.data_service.prewarm_data()

        # Start continuous data updates in the background
        update_task = asyncio.create_task(self.data_service.start_continuous_updates())

        try:
            while self.is_running:
                # 1. Get the latest data from the data service
                # 2. Apply trading strategy/indicators
                # 3. Make trading decisions
                # 4. Execute trades via the trading service
                # 5. Manage open positions and risk
                
                logger.debug("Main trading loop iteration.")
                
                # Example: Accessing data for a symbol
                btc_data = self.data_service.get_data("BTC", "1h")
                if btc_data is not None:
                    latest_price = btc_data['close'].iloc[-1]
                    logger.info(f"Latest BTC price from cache: {latest_price}")

                await asyncio.sleep(60) # Main loop interval

        except asyncio.CancelledError:
            logger.info("Trading loop cancelled.")
        finally:
            update_task.cancel()
            await self.shutdown()

    async def shutdown(self):
        """
        Gracefully shuts down the trading bot.
        """
        self.is_running = False
        logger.info("Shutting down trading bot...")
        await self.data_service.close()
        # await self.trading_service.close()
        logger.info("Trading bot shut down successfully.") 