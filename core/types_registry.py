from collections.abc import AsyncGenerator, Callable
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import TYPE_CHECKING, Any, Literal, NotRequired, Required, TypeAlias, TypedDict

# Type checking only import for circular dependency avoidance
if TYPE_CHECKING:
    pass


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
    ATR = auto()  # Average True Range
    EMA_RANGE = auto()  # EMA on price range
    ORB = auto()  # Custom Indicator
    LOD = auto()  # Low of Day Distance
    VBP = auto()  # Volume Profile


# Progress/lifecycle enums for node execution
class ProgressState(str, Enum):
    START = "start"
    UPDATE = "update"
    DONE = "done"
    ERROR = "error"
    STOPPED = "stopped"


# Structured dict types with fixed fields
class LLMToolFunction(TypedDict, total=False):
    name: str
    description: str | None
    parameters: dict[str, Any]


class LLMToolSpec(TypedDict):
    type: Literal["function"]
    function: LLMToolFunction


class LLMToolCallFunction(TypedDict, total=False):
    name: str
    arguments: dict[str, Any]


class LLMToolCall(TypedDict, total=False):
    id: str
    function: LLMToolCallFunction


class LLMChatMessage(TypedDict, total=True):
    role: Literal["system", "user", "assistant", "tool"]
    content: str | dict[str, Any]
    thinking: NotRequired[str]
    images: NotRequired[list[str]]
    tool_calls: NotRequired[list[LLMToolCall]]
    tool_name: NotRequired[str]
    tool_call_id: NotRequired[str]


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
    result: dict[str, Any]


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


# Base node based types
# Scalar and value types accepted for parameter defaults/options
ParamScalar = str | int | float | bool
ParamValue = ParamScalar | None | list[ParamScalar] | dict[str, Any]

# UI param type tags used by the frontend
ParamType = Literal["text", "textarea", "number", "integer", "int", "float", "combo"]


class ParamMeta(TypedDict, total=False):
    name: Required[str]
    type: NotRequired[ParamType]
    default: NotRequired[ParamValue]
    options: NotRequired[list[ParamScalar]]
    min: NotRequired[float]
    max: NotRequired[float]
    step: NotRequired[float]
    precision: NotRequired[int]
    label: NotRequired[str]
    unit: NotRequired[str]
    description: NotRequired[str]


DefaultParams: TypeAlias = dict[str, ParamValue]
NodeInputs: TypeAlias = dict[str, Any]
NodeOutputs: TypeAlias = dict[str, Any]

# Type alias for the node registry
NodeRegistry: TypeAlias = dict[str, type[Any]]


class NodeCategory(str, Enum):
    IO = "io"
    LLM = "llm"
    MARKET = "market"
    BASE = "base"
    CORE = "core"


@dataclass(frozen=True)
class IndicatorValue:
    single: float = 0.0
    lines: dict[str, float] = field(default_factory=dict)
    series: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "single": self.single,
            "lines": self.lines,
            "series": self.series,
        }


@dataclass(frozen=True)
class IndicatorResult:
    indicator_type: IndicatorType
    timestamp: int | None = None
    values: IndicatorValue = field(default_factory=IndicatorValue)
    params: dict[str, Any] = field(default_factory=dict)
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
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
    quote_currency: str | None = None
    instrument_type: InstrumentType = InstrumentType.SPOT
    metadata: dict[str, Any] = field(default_factory=dict)

    def __str__(self) -> str:
        if self.asset_class == AssetClass.CRYPTO and self.quote_currency:
            return f"{self.ticker.upper()}{self.quote_currency.upper()}"
        return self.ticker.upper()

    @staticmethod
    def from_string(
        s: str, asset_class: AssetClass, metadata: dict[str, Any] | None = None
    ) -> "AssetSymbol":
        if asset_class == AssetClass.CRYPTO:
            if "USDT" in s.upper():
                ticker, _quote = s.upper().split("USDT")
                return AssetSymbol(
                    ticker, asset_class, quote_currency="USDT", metadata=metadata or {}
                )
            else:
                return AssetSymbol(s.upper(), asset_class, metadata=metadata or {})
        return AssetSymbol(s.upper(), asset_class, metadata=metadata or {})

    def to_dict(self) -> dict[str, Any]:
        return {
            "ticker": self.ticker,
            "asset_class": self.asset_class.name,
            "quote_currency": self.quote_currency,
            "instrument_type": self.instrument_type.name,
            "metadata": self.metadata,
        }

    def __hash__(self):
        return hash((self.ticker, self.asset_class, self.quote_currency, self.instrument_type))


# Types for the graph serialisation from LiteGraph.asSerialisable().
class SerialisedLink(TypedDict, total=False):
    """Object-based link used by LiteGraph.asSerialisable()."""

    id: Required[int]
    origin_id: Required[int]
    origin_slot: Required[int]
    target_id: Required[int]
    target_slot: Required[int]
    type: Required[Any]
    parentId: NotRequired[int]


class SerialisedNodeInput(TypedDict, total=False):
    name: str
    type: Any
    linkIds: NotRequired[list[int]]


class SerialisedNodeOutput(TypedDict, total=False):
    name: str
    type: Any
    linkIds: NotRequired[list[int]]


class SerialisedNode(TypedDict, total=False):
    id: Required[int]
    type: Required[str]
    title: NotRequired[str]
    pos: NotRequired[list[float]]
    size: NotRequired[list[float]]
    flags: NotRequired[dict[str, Any]]
    order: NotRequired[int]
    mode: NotRequired[int]
    inputs: NotRequired[list[SerialisedNodeInput]]
    outputs: NotRequired[list[SerialisedNodeOutput]]
    properties: NotRequired[dict[str, Any]]
    shape: NotRequired[Any]
    boxcolor: NotRequired[str]
    color: NotRequired[str]
    bgcolor: NotRequired[str]
    showAdvanced: NotRequired[bool]
    widgets_values: NotRequired[list[Any]]


class SerialisedGraphState(TypedDict, total=True):
    lastNodeId: int
    lastLinkId: int
    lastGroupId: int
    lastRerouteId: int


# Main graph serialisation type that transcribes from the LiteGraph.asSerialisable() schema.
class SerialisableGraph(TypedDict, total=False):
    id: str
    revision: int
    version: int  # 0 | 1
    state: SerialisedGraphState
    nodes: list[SerialisedNode]
    links: NotRequired[list[SerialisedLink]]
    floatingLinks: NotRequired[list[SerialisedLink]]
    reroutes: NotRequired[list[dict[str, Any]]]
    groups: NotRequired[list[dict[str, Any]]]
    extra: NotRequired[dict[str, Any]]
    definitions: NotRequired[dict[str, Any]]


# Type aliases for complex/composed types
AssetSymbolList: TypeAlias = list[AssetSymbol]
IndicatorDict: TypeAlias = dict[str, float]
AnyList: TypeAlias = list[Any]
ConfigDict: TypeAlias = dict[str, Any]
OHLCV: TypeAlias = list[OHLCVBar]
OHLCVBundle: TypeAlias = dict[AssetSymbol, list[OHLCVBar]]
OHLCVStream: TypeAlias = AsyncGenerator[dict[AssetSymbol, list[OHLCVBar]], None]
LLMChatMessageList: TypeAlias = list[LLMChatMessage]
LLMToolSpecList: TypeAlias = list[LLMToolSpec]
LLMToolHistory: TypeAlias = list[LLMToolHistoryItem]
LLMThinkingHistory: TypeAlias = list[LLMThinkingHistoryItem]


# Structured progress event contract for execution reporting
class ProgressEvent(TypedDict, total=False):
    node_id: int
    state: ProgressState
    progress: float
    text: str
    meta: dict[str, Any]


ProgressCallback = Callable[[ProgressEvent], None]

TYPE_REGISTRY: dict[str, type[Any]] = {
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
def get_type(type_name: str) -> type[Any]:
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

    def __init__(self, node_id: int, message: str, original_exc: Exception | None = None):
        super().__init__(f"Node {node_id}: {message}")
        self.original_exc = original_exc


__all__ = [
    "AssetClass",
    "InstrumentType",
    "Provider",
    "IndicatorType",
    "LLMToolFunction",
    "LLMToolSpec",
    "LLMToolCallFunction",
    "LLMToolCall",
    "LLMChatMessage",
    "LLMChatMetrics",
    "LLMToolHistoryItem",
    "LLMThinkingHistoryItem",
    "OHLCVBar",
    "AssetSymbol",
    "IndicatorValue",
    "IndicatorResult",
    "AssetSymbolList",
    "IndicatorDict",
    "AnyList",
    "ConfigDict",
    "OHLCV",
    "OHLCVBundle",
    "OHLCVStream",
    "LLMChatMessageList",
    "LLMToolSpecList",
    "LLMToolHistory",
    "LLMThinkingHistory",
    "TYPE_REGISTRY",
    "get_type",
    "NodeError",
    "NodeValidationError",
    "NodeExecutionError",
    "ProgressState",
    "ProgressEvent",
    "ProgressCallback",
]
