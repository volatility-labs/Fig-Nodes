export declare enum AssetClass {
    CRYPTO = "CRYPTO",
    STOCKS = "STOCKS"
}
export declare enum InstrumentType {
    SPOT = "SPOT",
    PERPETUAL = "PERPETUAL",
    FUTURE = "FUTURE",
    OPTION = "OPTION"
}
export declare enum Provider {
    BINANCE = "BINANCE",
    POLYGON = "POLYGON"
}
export declare enum IndicatorType {
    EMA = "EMA",
    SMA = "SMA",
    MACD = "MACD",
    RSI = "RSI",
    ADX = "ADX",
    HURST = "HURST",
    BOLLINGER = "BOLLINGER",
    VOLUME_RATIO = "VOLUME_RATIO",
    EIS = "EIS",
    ATRX = "ATRX",
    ATR = "ATR",
    EMA_RANGE = "EMA_RANGE",
    ORB = "ORB",
    LOD = "LOD",
    VBP = "VBP",
    EVWMA = "EVWMA",
    CCO = "CCO"
}
export declare enum ProgressState {
    START = "start",
    UPDATE = "update",
    DONE = "done",
    ERROR = "error",
    STOPPED = "stopped"
}
export declare enum ExecutionOutcome {
    SUCCESS = "success",
    CANCELLED = "cancelled",
    ERROR = "error"
}
export declare enum NodeCategory {
    IO = "io",
    LLM = "llm",
    MARKET = "market",
    BASE = "base",
    CORE = "core"
}
export interface OHLCVBar {
    timestamp: number;
    open: number;
    high: number;
    low: number;
    close: number;
    volume: number;
}
export interface AssetSymbolData {
    ticker: string;
    assetClass: AssetClass;
    quoteCurrency?: string;
    instrumentType: InstrumentType;
    metadata: Record<string, unknown>;
}
export declare class AssetSymbol implements AssetSymbolData {
    readonly ticker: string;
    readonly assetClass: AssetClass;
    readonly quoteCurrency?: string;
    readonly instrumentType: InstrumentType;
    readonly metadata: Record<string, unknown>;
    constructor(ticker: string, assetClass: AssetClass, quoteCurrency?: string, instrumentType?: InstrumentType, metadata?: Record<string, unknown>);
    toString(): string;
    static fromString(s: string, assetClass: AssetClass, metadata?: Record<string, unknown>): AssetSymbol;
    toDict(): Record<string, unknown>;
    get key(): string;
}
export interface IndicatorValue {
    single: number;
    lines: Record<string, number>;
    series: Array<Record<string, unknown>>;
}
export interface CreateIndicatorValueOptions {
    single?: number;
    lines?: Record<string, number>;
    series?: Array<Record<string, unknown>>;
}
export declare function createIndicatorValue(options?: CreateIndicatorValueOptions): IndicatorValue;
export interface IndicatorResult {
    indicatorType: IndicatorType;
    timestamp: number | null;
    values: IndicatorValue;
    params: Record<string, unknown>;
    error: string | null;
}
export interface CreateIndicatorResultOptions {
    indicatorType: IndicatorType;
    timestamp?: number | null;
    values?: IndicatorValue;
    params?: Record<string, unknown>;
    error?: string | null;
}
export declare function createIndicatorResult(options: CreateIndicatorResultOptions): IndicatorResult;
export type AssetSymbolList = AssetSymbol[];
export type IndicatorDict = Record<string, number>;
export type AnyList = unknown[];
export type ConfigDict = Record<string, unknown>;
export type OHLCVBundle = Map<AssetSymbol, OHLCVBar[]>;
