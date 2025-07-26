import os
from dotenv import load_dotenv

def load_settings():
    """
    Loads all bot settings from environment variables.
    """
    load_dotenv()
    
    return {
        "binance_api_key": os.getenv("BINANCE_API_KEY"),
        "binance_api_secret": os.getenv("BINANCE_API_SECRET"),
        "hyperliquid_api_key": os.getenv("HYPERLIQUID_API_KEY"),
        "hyperliquid_api_secret": os.getenv("HYPERLIQUID_API_SECRET"),
        "log_level": os.getenv("LOG_LEVEL", "INFO"),
    }
