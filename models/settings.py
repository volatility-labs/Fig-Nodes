from dataclasses import dataclass
from decimal import Decimal

@dataclass
class Kline:
    """
    Represents a single k-line (candlestick).
    """
    timestamp: int
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: Decimal

@dataclass
class BotSettings:
    """
    Typed data class for bot settings.
    """
    binance_api_key: str
    binance_api_secret: str
    hyperliquid_api_key: str
    hyperliquid_api_secret: str
    log_level: str
