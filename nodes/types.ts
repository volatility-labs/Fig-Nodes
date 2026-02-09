// Consolidated node types: Market domain + LLM domain

import { z } from 'zod';
import { registerType } from '@sosa/core';

// ============================================================
// Market Types
// ============================================================

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

// ============ OHLCVBundle Serialization ============

/** JSON-safe representation of an OHLCVBundle entry */
export interface SerializedBundleEntry {
  symbol: AssetSymbolData;
  bars: OHLCVBar[];
}

/** JSON-safe representation of an OHLCVBundle */
export type SerializedOHLCVBundle = Record<string, SerializedBundleEntry>;

/** Convert Map<AssetSymbol, OHLCVBar[]> to a plain object for JSON */
export function serializeOHLCVBundle(bundle: OHLCVBundle): SerializedOHLCVBundle {
  const result: SerializedOHLCVBundle = {};
  for (const [symbol, bars] of bundle) {
    result[symbol.key] = { symbol: symbol.toDict() as unknown as AssetSymbolData, bars };
  }
  return result;
}

/** Reconstruct Map<AssetSymbol, OHLCVBar[]> from a plain object */
export function deserializeOHLCVBundle(raw: SerializedOHLCVBundle): OHLCVBundle {
  const bundle: OHLCVBundle = new Map();
  for (const entry of Object.values(raw)) {
    const s = entry.symbol;
    const symbol = new AssetSymbol(
      s.ticker,
      s.assetClass,
      s.quoteCurrency,
      s.instrumentType,
      s.metadata,
    );
    bundle.set(symbol, entry.bars);
  }
  return bundle;
}

// ============ Register market port types ============

registerType('AssetSymbol');
registerType('AssetSymbolList');
registerType('OHLCVBundle');
registerType('IndicatorDict');
registerType('IndicatorValue');
registerType('IndicatorResult');
registerType('IndicatorResultList');
registerType('AnyList');
registerType('ConfigDict');

// ============================================================
// LLM Types
// ============================================================

// ============ Zod Schemas ============

export const LLMToolFunctionSchema = z.object({
  name: z.string(),
  description: z.string().nullable().optional(),
  parameters: z.record(z.unknown()).default({}),
}).passthrough();

export const LLMToolSpecSchema = z.object({
  type: z.literal('function').default('function'),
  function: LLMToolFunctionSchema,
}).passthrough();

export const LLMToolCallFunctionSchema = z.object({
  name: z.string().default(''),
  arguments: z.record(z.unknown()).default({}),
}).passthrough();

export const LLMToolCallSchema = z.object({
  id: z.string().default(''),
  function: LLMToolCallFunctionSchema.default({ name: '', arguments: {} }),
}).passthrough();

export const LLMChatMessageSchema = z.object({
  role: z.enum(['system', 'user', 'assistant', 'tool']),
  content: z.union([z.string(), z.record(z.unknown())]).default(''),
  thinking: z.string().nullable().optional(),
  images: z.array(z.string()).nullable().optional(),
  tool_calls: z.array(LLMToolCallSchema).nullable().optional(),
  tool_name: z.string().nullable().optional(),
  tool_call_id: z.string().nullable().optional(),
}).passthrough();

export const LLMChatMetricsSchema = z.object({
  total_duration: z.number().nullable().optional(),
  load_duration: z.number().nullable().optional(),
  prompt_eval_count: z.number().nullable().optional(),
  prompt_eval_duration: z.number().nullable().optional(),
  eval_count: z.number().nullable().optional(),
  eval_duration: z.number().nullable().optional(),
  error: z.string().nullable().optional(),
  seed: z.number().nullable().optional(),
  temperature: z.number().nullable().optional(),
  parse_error: z.string().nullable().optional(),
}).passthrough();

export const LLMToolHistoryItemSchema = z.object({
  call: z.union([LLMToolCallSchema, z.record(z.unknown())]),
  result: z.record(z.unknown()).default({}),
}).passthrough();

export const LLMThinkingHistoryItemSchema = z.object({
  thinking: z.string(),
  iteration: z.number().default(0),
}).passthrough();

// ============ Inferred Types ============

export type LLMToolFunction = z.infer<typeof LLMToolFunctionSchema>;
export type LLMToolSpec = z.infer<typeof LLMToolSpecSchema>;
export type LLMToolCallFunction = z.infer<typeof LLMToolCallFunctionSchema>;
export type LLMToolCall = z.infer<typeof LLMToolCallSchema>;
export type LLMChatMessage = z.infer<typeof LLMChatMessageSchema>;
export type LLMChatMetrics = z.infer<typeof LLMChatMetricsSchema>;
export type LLMToolHistoryItem = z.infer<typeof LLMToolHistoryItemSchema>;
export type LLMThinkingHistoryItem = z.infer<typeof LLMThinkingHistoryItemSchema>;

// ============ LLM Type Aliases ============

export type LLMChatMessageList = LLMChatMessage[];
export type LLMToolSpecList = LLMToolSpec[];
export type LLMToolHistory = LLMToolHistoryItem[];
export type LLMThinkingHistory = LLMThinkingHistoryItem[];

// ============ Validation Helpers ============

export function validateLLMToolSpec(obj: unknown): LLMToolSpec | null {
  const result = LLMToolSpecSchema.safeParse(obj);
  return result.success ? result.data : null;
}

export function validateLLMChatMessage(obj: unknown): LLMChatMessage | null {
  const result = LLMChatMessageSchema.safeParse(obj);
  return result.success ? result.data : null;
}

// ============ Register LLM port types ============

registerType('LLMChatMessage');
registerType('LLMChatMessageList');
registerType('LLMToolSpec');
registerType('LLMToolSpecList');
registerType('LLMChatMetrics');
registerType('LLMToolHistory');
registerType('LLMThinkingHistory');
registerType('LLMToolHistoryItem');
registerType('LLMThinkingHistoryItem');
