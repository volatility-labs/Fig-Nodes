// src/types/domain.ts
// Domain types: enums, core value types, and type aliases

// ============ Enums ============

export enum AssetClass {
  CRYPTO = 'CRYPTO',
  STOCKS = 'STOCKS',
}

export enum InstrumentType {
  SPOT = 'SPOT',
  PERPETUAL = 'PERPETUAL',
  FUTURE = 'FUTURE',
  OPTION = 'OPTION',
}

export enum Provider {
  BINANCE = 'BINANCE',
  POLYGON = 'POLYGON',
}

export enum IndicatorType {
  EMA = 'EMA',
  SMA = 'SMA',
  MACD = 'MACD',
  RSI = 'RSI',
  ADX = 'ADX',
  HURST = 'HURST',
  BOLLINGER = 'BOLLINGER',
  VOLUME_RATIO = 'VOLUME_RATIO',
  EIS = 'EIS',
  ATRX = 'ATRX',
  ATR = 'ATR',
  EMA_RANGE = 'EMA_RANGE',
  ORB = 'ORB',
  LOD = 'LOD',
  VBP = 'VBP',
  EVWMA = 'EVWMA',
  CCO = 'CCO',
}

export enum ProgressState {
  START = 'start',
  UPDATE = 'update',
  DONE = 'done',
  ERROR = 'error',
  STOPPED = 'stopped',
}

export enum ExecutionOutcome {
  SUCCESS = 'success',
  CANCELLED = 'cancelled',
  ERROR = 'error',
}

export enum NodeCategory {
  IO = 'io',
  LLM = 'llm',
  MARKET = 'market',
  BASE = 'base',
  CORE = 'core',
}

// ============ OHLCV Types ============

export interface OHLCVBar {
  timestamp: number; // Unix timestamp in milliseconds
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
}

// ============ Asset Symbol ============

export interface AssetSymbolData {
  ticker: string;
  assetClass: AssetClass;
  quoteCurrency?: string;
  instrumentType: InstrumentType;
  metadata: Record<string, unknown>;
}

export class AssetSymbol implements AssetSymbolData {
  readonly ticker: string;
  readonly assetClass: AssetClass;
  readonly quoteCurrency?: string;
  readonly instrumentType: InstrumentType;
  readonly metadata: Record<string, unknown>;

  constructor(
    ticker: string,
    assetClass: AssetClass,
    quoteCurrency?: string,
    instrumentType: InstrumentType = InstrumentType.SPOT,
    metadata: Record<string, unknown> = {}
  ) {
    this.ticker = ticker;
    this.assetClass = assetClass;
    this.quoteCurrency = quoteCurrency;
    this.instrumentType = instrumentType;
    this.metadata = metadata;
  }

  toString(): string {
    if (this.assetClass === AssetClass.CRYPTO && this.quoteCurrency) {
      return `${this.ticker.toUpperCase()}${this.quoteCurrency.toUpperCase()}`;
    }
    return this.ticker.toUpperCase();
  }

  static fromString(
    s: string,
    assetClass: AssetClass,
    metadata: Record<string, unknown> = {}
  ): AssetSymbol {
    if (assetClass === AssetClass.CRYPTO) {
      if (s.toUpperCase().includes('USDT')) {
        const ticker = s.toUpperCase().split('USDT')[0] ?? s.toUpperCase();
        return new AssetSymbol(ticker, assetClass, 'USDT', InstrumentType.SPOT, metadata);
      }
      return new AssetSymbol(s.toUpperCase(), assetClass, undefined, InstrumentType.SPOT, metadata);
    }
    return new AssetSymbol(s.toUpperCase(), assetClass, undefined, InstrumentType.SPOT, metadata);
  }

  toDict(): Record<string, unknown> {
    return {
      ticker: this.ticker,
      asset_class: this.assetClass,
      quote_currency: this.quoteCurrency,
      instrument_type: this.instrumentType,
      metadata: this.metadata,
    };
  }

  // For use as Map key - generates unique string identifier
  get key(): string {
    return `${this.ticker}:${this.assetClass}:${this.quoteCurrency ?? ''}:${this.instrumentType}`;
  }
}

// ============ Indicator Types ============

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

export function createIndicatorValue(
  options: CreateIndicatorValueOptions = {}
): IndicatorValue {
  return {
    single: options.single ?? 0.0,
    lines: options.lines ?? {},
    series: options.series ?? [],
  };
}

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

export function createIndicatorResult(
  options: CreateIndicatorResultOptions
): IndicatorResult {
  return {
    indicatorType: options.indicatorType,
    timestamp: options.timestamp ?? null,
    values: options.values ?? createIndicatorValue(),
    params: options.params ?? {},
    error: options.error ?? null,
  };
}

// ============ Domain Type Aliases ============

export type AssetSymbolList = AssetSymbol[];
export type IndicatorDict = Record<string, number>;
export type AnyList = unknown[];
export type ConfigDict = Record<string, unknown>;
export type OHLCVBundle = Map<AssetSymbol, OHLCVBar[]>;
