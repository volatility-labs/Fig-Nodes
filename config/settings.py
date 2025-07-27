import os
from dotenv import load_dotenv
from dataclasses import dataclass
from decimal import Decimal

@dataclass
class Kline:
    timestamp: int
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: Decimal

@dataclass
class BotSettings:
    binance_api_key: str
    binance_api_secret: str
    hyperliquid_api_key: str
    hyperliquid_api_secret: str
    log_level: str

def load_settings() -> BotSettings:
    """
    Loads all bot settings from environment variables.
    """
    load_dotenv()
    
    return BotSettings(
        binance_api_key=os.getenv("BINANCE_API_KEY"),
        binance_api_secret=os.getenv("BINANCE_API_SECRET"),
        hyperliquid_api_key=os.getenv("HYPERLIQUID_API_KEY"),
        hyperliquid_api_secret=os.getenv("HYPERLIQUID_API_SECRET"),
        log_level=os.getenv("LOG_LEVEL", "INFO"),
    )
