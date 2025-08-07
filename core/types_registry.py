from typing import List, Dict, Any, Type, Optional
import pandas as pd
from datetime import datetime
from dataclasses import dataclass, field
from enum import Enum, auto

class AssetClass(Enum):
    CRYPTO = auto()
    STOCK = auto()

@dataclass(frozen=True)
class AssetSymbol:
    ticker: str
    asset_class: AssetClass
    quote_currency: Optional[str] = None
    exchange: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __str__(self) -> str:
        if self.asset_class == AssetClass.CRYPTO and self.quote_currency:
            return f"{self.ticker.upper()}{self.quote_currency.upper()}"
        return self.ticker.upper()

    @staticmethod
    def from_string(s: str, asset_class: AssetClass, exchange: Optional[str] = None, metadata: Dict[str, Any] = None) -> "AssetSymbol":
        if asset_class == AssetClass.CRYPTO:
            if "USDT" in s.upper():
                ticker, quote = s.upper().split("USDT")
                return AssetSymbol(ticker, asset_class, quote_currency="USDT", exchange=exchange, metadata=metadata or {})
            else:
                return AssetSymbol(s.upper(), asset_class, exchange=exchange, metadata=metadata or {})
        return AssetSymbol(s.upper(), asset_class, exchange=exchange, metadata=metadata or {})

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
    "TradeSignal": Dict[str, Any],
    "TradeResult": Dict[str, Any],
}

def get_type(type_name: str) -> Type:
    if type_name not in TYPE_REGISTRY:
        raise ValueError(f"Unknown type: {type_name}")
    return TYPE_REGISTRY[type_name]

def register_type(type_name: str, type_obj: Type):
    if type_name in TYPE_REGISTRY:
        raise ValueError(f"Type {type_name} already registered")
    TYPE_REGISTRY[type_name] = type_obj

def register_asset_class(name: str) -> AssetClass:
    # Dynamically add to Enum (note: Enums are immutable, so this creates a new member)
    setattr(AssetClass, name.upper(), auto())
    return getattr(AssetClass, name.upper()) 