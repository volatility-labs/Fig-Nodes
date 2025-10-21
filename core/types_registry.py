from typing import List, Dict, Any, Type, Optional, AsyncGenerator, TypedDict, Literal, Union, NotRequired
from dataclasses import dataclass, field
from enum import Enum, auto

# Core enums for shared concepts
class AssetClass(Enum):
    CRYPTO = auto()
    STOCKS = auto()

class InstrumentType(Enum):
    SPOT = auto()
    PERPETUAL = auto()
    FUTURE = auto()
    OPTION = auto()

class Provider(Enum):
    """Enum for data providers or venues (e.g., exchanges, aggregators)."""
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

# Structured dict types with fixed fields

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

class OHLCVBar(TypedDict, total=True):
    """OHLCV (Open, High, Low, Close, Volume) bar data"""
    timestamp: int  # Unix timestamp in milliseconds
    open: float
    high: float
    low: float
    close: float
    volume: float

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

# Immutable, hashable types with methods
@dataclass(frozen=True)
class AssetSymbol:
    ticker: str
    asset_class: AssetClass
    quote_currency: Optional[str] = None
    instrument_type: InstrumentType = InstrumentType.SPOT
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __str__(self) -> str:
        if self.asset_class == AssetClass.CRYPTO and self.quote_currency:
            return f"{self.ticker.upper()}{self.quote_currency.upper()}"
        return self.ticker.upper()

    @staticmethod
    def from_string(s: str, asset_class: AssetClass, metadata: Optional[Dict[str, Any]] = None) -> "AssetSymbol":
        if asset_class == AssetClass.CRYPTO:
            if "USDT" in s.upper():
                ticker, _quote = s.upper().split("USDT")
                return AssetSymbol(ticker, asset_class, quote_currency="USDT", metadata=metadata or {})
            else:
                return AssetSymbol(s.upper(), asset_class, metadata=metadata or {})
        return AssetSymbol(s.upper(), asset_class, metadata=metadata or {})
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "ticker": self.ticker,
            "asset_class": self.asset_class.name,
            "quote_currency": self.quote_currency,
            "instrument_type": self.instrument_type.name,
            "metadata": self.metadata
        }

    def __hash__(self):
        return hash((self.ticker, self.asset_class, self.quote_currency, self.instrument_type))

# Type aliases for complex/composed types
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

TYPE_REGISTRY: Dict[str, Type[Any]] = {
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

# Type registry functions
def get_type(type_name: str) -> Type[Any]:  
    """Get a type from the registry by name."""
    if type_name not in TYPE_REGISTRY:
        raise ValueError(f"Unknown type: {type_name}")
    return TYPE_REGISTRY[type_name]

# Node exceptions
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

# No dynamic registration; registry remains static in this package

__all__ = [
    # Enums
    'AssetClass', 'InstrumentType', 'Provider', 'IndicatorType',
    # TypedDicts
    'LLMToolFunction', 'LLMToolSpec', 'LLMToolCallFunction', 'LLMToolCall',
    'LLMChatMessage', 'LLMChatMetrics', 'LLMToolHistoryItem', 'LLMThinkingHistoryItem',
    'OHLCVBar',
    # Dataclasses
    'AssetSymbol', 'IndicatorValue', 'IndicatorResult',
    # Type aliases
    'AssetSymbolList', 'IndicatorDict', 'AnyList', 'ConfigDict',
    'OHLCV', 'OHLCVBundle', 'OHLCVStream',
    'LLMChatMessageList', 'LLMToolSpecList', 'LLMToolHistory', 'LLMThinkingHistory',
    # Registry functions
    'TYPE_REGISTRY', 'get_type',
    # Exceptions
    'NodeError', 'NodeValidationError', 'NodeExecutionError',
] 
