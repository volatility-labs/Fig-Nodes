from typing import List, Dict, Any, Type, Optional, AsyncGenerator
import pandas as pd
from datetime import datetime
from dataclasses import dataclass, field
from enum import Enum, auto

class AssetClass:
    CRYPTO = "CRYPTO"
    STOCKS = "STOCKS"

class InstrumentType(Enum):
    SPOT = auto()
    PERPETUAL = auto()
    FUTURE = auto()
    OPTION = auto()

class Exchange(Enum):
    """Enum for supported exchanges. Can be extended dynamically using register_exchange."""
    BINANCE = auto()
    POLYGON = auto()

@dataclass(frozen=True)
class AssetSymbol:
    ticker: str
    asset_class: str
    quote_currency: Optional[str] = None
    exchange: Optional[Exchange] = None
    instrument_type: InstrumentType = InstrumentType.SPOT
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __str__(self) -> str:
        if self.asset_class == AssetClass.CRYPTO and self.quote_currency:
            return f"{self.ticker.upper()}{self.quote_currency.upper()}"
        return self.ticker.upper()

    @staticmethod
    def from_string(s: str, asset_class: str, exchange: Optional[Exchange] = None, metadata: Dict[str, Any] = None) -> "AssetSymbol":
        if asset_class == AssetClass.CRYPTO:
            if "USDT" in s.upper():
                ticker, quote = s.upper().split("USDT")
                return AssetSymbol(ticker, asset_class, quote_currency="USDT", exchange=exchange, metadata=metadata or {})
            else:
                return AssetSymbol(s.upper(), asset_class, exchange=exchange, metadata=metadata or {})
        return AssetSymbol(s.upper(), asset_class, exchange=exchange, metadata=metadata or {})
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "ticker": self.ticker,
            "asset_class": self.asset_class,
            "quote_currency": self.quote_currency,
            "exchange": self.exchange.name if self.exchange else None,
            "instrument_type": self.instrument_type.name,
            "metadata": self.metadata
        }

TYPE_REGISTRY: Dict[str, Type] = {
    "AssetSymbol": AssetSymbol,
    "AssetSymbolList": List[AssetSymbol],
    "Exchange": str,
    "Timestamp": int,
    "IndicatorDict": Dict[str, float],
    "AnyList": List[Any],
    "ConfigDict": Dict[str, Any],
    "OHLCV": pd.DataFrame,
    "OHLCVBundle": Dict[AssetSymbol, pd.DataFrame],
    "Score": float,
    "OHLCVStream": AsyncGenerator[Dict[AssetSymbol, pd.DataFrame], None],
}

def get_type(type_name: str) -> Type:
    if type_name not in TYPE_REGISTRY:
        raise ValueError(f"Unknown type: {type_name}")
    return TYPE_REGISTRY[type_name]

def register_type(type_name: str, type_obj: Type):
    if type_name in TYPE_REGISTRY:
        raise ValueError(f"Type {type_name} already registered")
    TYPE_REGISTRY[type_name] = type_obj

def register_asset_class(name: str) -> str:
    upper = name.upper()
    if not hasattr(AssetClass, upper):
        setattr(AssetClass, upper, upper)
    return getattr(AssetClass, upper) 

def register_exchange(name: str) -> Exchange:
    """Registers a new exchange dynamically to the Exchange Enum."""
    upper = name.upper()
    if not hasattr(Exchange, upper):
        setattr(Exchange, upper, auto())
    return getattr(Exchange, upper)

# Developer Notes:
# To add a new type:
# 1. Define the type (class, dataclass, Enum, etc.) in this file.
# 2. Register it in TYPE_REGISTRY with a unique string key.
#    Example: TYPE_REGISTRY["MyNewType"] = MyNewType
# 3. If it's a complex type (e.g., List[MyType]), use typing constructs.
# 4. For dynamic extensions (like AssetClass or Exchange), use the register_ functions.
# 5. Update get_type if custom lookup is needed.
# 6. Ensure any new types are importable and used consistently in node definitions. 