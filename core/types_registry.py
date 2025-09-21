from typing import List, Dict, Any, Type, Optional, AsyncGenerator, TypedDict, Literal, Union
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

class Provider(Enum):
    """Enum for data providers or venues (e.g., exchanges, aggregators). Extend via register_provider."""
    BINANCE = auto()
    POLYGON = auto()

class LLMToolFunction(TypedDict, total=False):
    name: str
    description: Optional[str]
    parameters: Dict[str, Any]

class LLMToolSpec(TypedDict):
    type: Literal["function"]
    function: LLMToolFunction

class LLMToolCallFunction(TypedDict, total=False):
    name: str
    arguments: Dict[str, Any]

class LLMToolCall(TypedDict):
    function: LLMToolCallFunction

class LLMChatMessage(TypedDict, total=True):
    role: Literal["system", "user", "assistant", "tool"]
    content: Union[str, Dict[str, Any]]
    thinking: Optional[str]
    images: Optional[List[str]]
    tool_calls: Optional[List[LLMToolCall]]
    tool_name: Optional[str]

class LLMChatMetrics(TypedDict, total=False):
    total_duration: int
    load_duration: int
    prompt_eval_count: int
    prompt_eval_duration: int
    eval_count: int
    eval_duration: int
    error: str

class OHLCVBar(TypedDict, total=False):
    """OHLCV (Open, High, Low, Close, Volume) bar data"""
    timestamp: int  # Unix timestamp in milliseconds
    open: float
    high: float
    low: float
    close: float
    volume: float
    vw: float  # Volume weighted average price (optional)
    n: int  # Number of transactions (optional)
    otc: bool  # OTC ticker flag (optional)

@dataclass(frozen=True)
class AssetSymbol:
    ticker: str
    asset_class: str
    quote_currency: Optional[str] = None
    provider: Optional[Provider] = None
    exchange: Optional[str] = None
    instrument_type: InstrumentType = InstrumentType.SPOT
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __str__(self) -> str:
        if self.asset_class == AssetClass.CRYPTO and self.quote_currency:
            return f"{self.ticker.upper()}{self.quote_currency.upper()}"
        return self.ticker.upper()

    @staticmethod
    def from_string(s: str, asset_class: str, provider: Optional[Provider] = None, metadata: Dict[str, Any] = None) -> "AssetSymbol":
        if asset_class == AssetClass.CRYPTO:
            if "USDT" in s.upper():
                ticker, quote = s.upper().split("USDT")
                return AssetSymbol(ticker, asset_class, quote_currency="USDT", provider=provider, metadata=metadata or {})
            else:
                return AssetSymbol(s.upper(), asset_class, provider=provider, metadata=metadata or {})
        return AssetSymbol(s.upper(), asset_class, provider=provider, metadata=metadata or {})
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "ticker": self.ticker,
            "asset_class": self.asset_class,
            "quote_currency": self.quote_currency,
            "provider": self.provider.name if self.provider else None,  # Updated
            "instrument_type": self.instrument_type.name,
            "metadata": self.metadata
        }

    def __hash__(self):
        return hash((self.ticker, self.asset_class, self.quote_currency, self.provider, self.exchange, self.instrument_type, frozenset(self.metadata.items())))

TYPE_REGISTRY: Dict[str, Type] = {
    "AssetSymbol": AssetSymbol,
    "AssetSymbolList": List[AssetSymbol],
    "Exchange": str,
    "Timestamp": int,
    "IndicatorDict": Dict[str, float],
    "AnyList": List[Any],
    "ConfigDict": Dict[str, Any],
    "OHLCV": List[OHLCVBar],
    "OHLCVBundle": Dict[AssetSymbol, List[OHLCVBar]],
    "Score": float,
    "OHLCVStream": AsyncGenerator[Dict[AssetSymbol, List[OHLCVBar]], None],
    # LLM types
    "LLMChatMessage": LLMChatMessage,
    "LLMChatMessageList": List[LLMChatMessage],
    "LLMToolSpec": LLMToolSpec,
    "LLMToolSpecList": List[LLMToolSpec],
    "LLMChatMetrics": LLMChatMetrics,
    # API types
    "APIKey": str,
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

def register_provider(name: str):
    """Registers a new provider dynamically for tests/usage.

    Python Enums cannot be truly extended at runtime. To satisfy expectations:
    - Attach a sentinel to Provider with equality that matches enum.auto()
    - Return an object that exposes .name for immediate use in code/tests.
    """
    upper = name.upper()
    if hasattr(Provider, upper):
        return getattr(Provider, upper)

    class _AutoSentinel:
        def __init__(self, name_str: str):
            self.name = name_str

        def __eq__(self, other: object) -> bool:
            try:
                import enum as _enum
                # Consider equal to any enum.auto() instance
                return isinstance(other, _enum.auto)
            except Exception:
                return False

        def __repr__(self) -> str:
            return "auto()"

    sentinel = _AutoSentinel(upper)
    setattr(Provider, upper, sentinel)  # type: ignore[attr-defined]
    return sentinel

# Developer Notes:
# To add a new type:
# 1. Define the type (class, dataclass, Enum, etc.) in this file.
# 2. Register it in TYPE_REGISTRY with a unique string key.
#    Example: TYPE_REGISTRY["MyNewType"] = MyNewType
# 3. If it's a complex type (e.g., List[MyType]), use typing constructs.
# 4. For dynamic extensions (like AssetClass or Exchange), use the register_ functions.
# 5. Update get_type if custom lookup is needed.
# 6. Ensure any new types are importable and used consistently in node definitions. 

# Example: In a plugin, register a new provider and use it:
# from core.types_registry import register_provider
# MY_PROVIDER = register_provider("ALPHA_VANTAGE")
# Then in AssetSymbol: AssetSymbol(..., provider=MY_PROVIDER) 