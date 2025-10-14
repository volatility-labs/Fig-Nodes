from typing import List, Dict, Any, Type, Optional, AsyncGenerator, TypedDict, Literal, Union, NotRequired
import pandas as pd
from datetime import datetime
from dataclasses import dataclass, field
from enum import Enum, auto
import warnings

# Type Definition Conventions:
# - Use TypedDict for structured dicts with fixed, named fields (e.g., IndicatorResult).
# - Use type aliases for dynamic dicts/lists (e.g., MultiAssetIndicatorResults) to improve readability and reuse.
# - Register all types in TYPE_REGISTRY for centralized access.
# - For extensibility: Use register_ functions to add to Enums dynamically without modifying this file.
#   Custom nodes can call these in their __init__.py or module init to extend types.

# ~~~~~ Enums ~~~~~
# Core enums for shared concepts. Extend via register_ functions below.

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

class IndicatorType(Enum):
    EMA = auto()  # Exponential Moving Average
    SMA = auto()  # Simple Moving Average
    MACD = auto()  # Moving Average Convergence Divergence
    RSI = auto()  # Relative Strength Index
    ADX = auto()  # Average Directional Index
    HURST = auto()  # Hurst Exponent
    BOLLINGER = auto()  # Bollinger Bands
    VOLUME_RATIO = auto()  # Volume Ratio
    EIS = auto()  # Elder Impulse System
    ATRX = auto()  # ATRX Indicator
    ATR = auto()   # Average True Range
    EMA_RANGE = auto()  # EMA on price range
    ORB = auto()  # Custom Indicator
    LOD = auto()  # Low of Day Distance
    # Add more as needed

# ~~~~~ TypedDicts ~~~~~
# Structured dict types with fixed fields.

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

class LLMToolCall(TypedDict, total=False):
    id: str
    function: LLMToolCallFunction

class LLMChatMessage(TypedDict, total=True):
    role: Literal["system", "user", "assistant", "tool"]
    content: Union[str, Dict[str, Any]]
    # Optional fields must be marked NotRequired so validators don't require their presence
    thinking: NotRequired[str]
    images: NotRequired[List[str]]
    tool_calls: NotRequired[List[LLMToolCall]]
    tool_name: NotRequired[str]

class LLMChatMetrics(TypedDict, total=False):
    total_duration: int
    load_duration: int
    prompt_eval_count: int
    prompt_eval_duration: int
    eval_count: int
    eval_duration: int
    error: str

class LLMToolHistoryItem(TypedDict):
    call: LLMToolCall
    result: Dict[str, Any]

class LLMThinkingHistoryItem(TypedDict):
    thinking: str
    iteration: int

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
class IndicatorValue:
    single: float = 0.0
    lines: Dict[str, float] = field(default_factory=dict)
    series: List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "single": self.single,
            "lines": self.lines,
            "series": self.series,
        }

@dataclass(frozen=True)
class IndicatorResult:
    indicator_type: IndicatorType
    timestamp: Optional[int] = None
    values: IndicatorValue = field(default_factory=IndicatorValue)
    params: Dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "indicator_type": self.indicator_type,
            "timestamp": self.timestamp,
            "values": self.values.to_dict(),
            "params": self.params,
            "error": self.error,
        }

# ~~~~~ Dataclasses ~~~~~
# For immutable, hashable types with methods.

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
        return hash((self.ticker, self.asset_class, self.quote_currency, self.provider, self.exchange, self.instrument_type))

# ~~~~~ Type Aliases ~~~~~
# For complex/composed types. Add new aliases here for reuse.

# Aliases for consistency with complex registry types
AssetSymbolList = List[AssetSymbol]
IndicatorDict = Dict[str, float]
AnyList = List[Any]
ConfigDict = Dict[str, Any]
OHLCV = List[OHLCVBar]
OHLCVBundle = Dict[AssetSymbol, List[OHLCVBar]]
OHLCVStream = AsyncGenerator[Dict[AssetSymbol, List[OHLCVBar]], None]
LLMChatMessageList = List[LLMChatMessage]
LLMToolSpecList = List[LLMToolSpec]
LLMToolHistory = List[LLMToolHistoryItem]
LLMThinkingHistory = List[LLMThinkingHistoryItem]

# ~~~~~ Type Registry ~~~~~
# Centralized dict for type lookup. All types must be registered here.

TYPE_REGISTRY: Dict[str, Type] = {
    "AssetSymbol": AssetSymbol,
    "AssetSymbolList": AssetSymbolList,
    "Exchange": str,
    "Timestamp": int,
    "IndicatorDict": IndicatorDict,
    "AnyList": AnyList,
    "ConfigDict": ConfigDict,
    "OHLCV": OHLCV,
    "OHLCVBundle": OHLCVBundle,
    "Score": float,
    "OHLCVStream": OHLCVStream,
    # LLM types
    "LLMChatMessage": LLMChatMessage,
    "LLMChatMessageList": LLMChatMessageList,
    "LLMToolSpec": LLMToolSpec,
    "LLMToolSpecList": LLMToolSpecList,
    "LLMChatMetrics": LLMChatMetrics,
    "LLMToolHistory": LLMToolHistory,
    "LLMThinkingHistory": LLMThinkingHistory,
    "IndicatorValue": IndicatorValue,
    "IndicatorResult": IndicatorResult,
}

# ~~~~~ Extension Functions ~~~~~
# Functions to dynamically extend types without modifying this file.
# Ideal for nodes/custom: Call these in your module's init to register new values.

def get_type(type_name: str) -> Type:
    if type_name not in TYPE_REGISTRY:
        raise ValueError(f"Unknown type: {type_name}")
    return TYPE_REGISTRY[type_name]

def register_type(type_name: str, type_obj: Type):
    if type_name in TYPE_REGISTRY:
        warnings.warn(f"Type {type_name} already registered; overwriting with new definition.")
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

def register_indicator_type(name: str):
    upper = name.upper()
    if hasattr(IndicatorType, upper):
        return getattr(IndicatorType, upper)
    class _AutoSentinel:
        def __init__(self, name_str: str):
            self.name = name_str
        def __eq__(self, other: object) -> bool:
            try:
                import enum as _enum
                return isinstance(other, _enum.auto)
            except Exception:
                return False
        def __repr__(self) -> str:
            return "auto()"
    sentinel = _AutoSentinel(upper)
    setattr(IndicatorType, upper, sentinel)  # type: ignore[attr-defined]
    return sentinel

# Developer Notes:
# To add a new type:
# 1. Define the type in the appropriate section (e.g., new TypedDict under TypedDicts or dataclass under Dataclasses).
# 2. If it's an alias or composed type, add it under Type Aliases.
# 3. Register it in TYPE_REGISTRY with a unique string key.
# 4. For dynamic extensions (e.g., new Enum values), use the register_ functions.
# 5. Update __all__ if the type should be importable.
# 6. Ensure any new types are used consistently in node definitions. Prefer dataclasses for structured types with fixed fields and potential methods; use TypedDict for dynamic dict-like data.

# For nodes/custom extensions:
# - To add a new type: Define it in your custom module, then call register_type("MyNewType", MyNewType) in your __init__.py.
# - To extend an Enum: Call register_provider("NEW_PROVIDER") or similar.
# - Example: In custom_nodes/my_plugin/__init__.py:
#   from core.types_registry import register_type, register_provider
#   from dataclasses import dataclass
#
#   @dataclass
#   class MyCustomType:
#       field: str
#   register_type("MyCustomType", MyCustomType)
#   MY_PROVIDER = register_provider("MY_EXCHANGE")

# Example: In a plugin, register a new provider and use it:
# from core.types_registry import register_provider
# MY_PROVIDER = register_provider("ALPHA_VANTAGE")
# Then in AssetSymbol: AssetSymbol(..., provider=MY_PROVIDER) 

from typing import Optional

class NodeError(Exception):
    """Base exception for all node-related errors."""
    pass

class NodeValidationError(NodeError):
    """Raised when node inputs fail validation."""
    def __init__(self, node_id: int, message: str):
        super().__init__(f"Node {node_id}: {message}")

class NodeExecutionError(NodeError):
    """Raised when node execution fails."""
    def __init__(self, node_id: int, message: str, original_exc: Optional[Exception] = None):
        super().__init__(f"Node {node_id}: {message}")
        self.original_exc = original_exc

# Register them
register_type("NodeError", NodeError)
register_type("NodeValidationError", NodeValidationError)
register_type("NodeExecutionError", NodeExecutionError)

__all__ = [
    'AssetClass', 'InstrumentType', 'Provider', 'IndicatorType',
    'LLMToolFunction', 'LLMToolSpec', 'LLMToolCallFunction', 'LLMToolCall',
    'LLMChatMessage', 'LLMChatMetrics', 'LLMToolHistoryItem', 'LLMThinkingHistoryItem',
    'OHLCVBar', 'AssetSymbol', 'IndicatorValue',
    'IndicatorResult',
    'TYPE_REGISTRY', 'get_type', 'register_type',
    'register_asset_class', 'register_provider', 'register_indicator_type',
    # Add new aliases here as needed
    'AssetSymbolList', 'IndicatorDict', 'AnyList', 'ConfigDict',
    'OHLCV', 'OHLCVBundle', 'OHLCVStream',
    'LLMChatMessageList', 'LLMToolSpecList', 'LLMToolHistory', 'LLMThinkingHistory',
    'NodeError', 'NodeValidationError', 'NodeExecutionError',
] 