// backend/core/types.ts
// Translated from: core/types_registry.py

import { z } from 'zod';

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
        const [ticker] = s.toUpperCase().split('USDT');
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

export function createIndicatorValue(
  single = 0.0,
  lines: Record<string, number> = {},
  series: Array<Record<string, unknown>> = []
): IndicatorValue {
  return { single, lines, series };
}

export interface IndicatorResult {
  indicatorType: IndicatorType;
  timestamp: number | null;
  values: IndicatorValue;
  params: Record<string, unknown>;
  error: string | null;
}

export function createIndicatorResult(
  indicatorType: IndicatorType,
  timestamp: number | null = null,
  values: IndicatorValue = createIndicatorValue(),
  params: Record<string, unknown> = {},
  error: string | null = null
): IndicatorResult {
  return { indicatorType, timestamp, values, params, error };
}

// ============ Execution Result ============

export interface ExecutionResult {
  outcome: ExecutionOutcome;
  results: Record<number, Record<string, unknown>> | null;
  error: string | null;
  cancelledBy: string | null;
}

export const ExecutionResultFactory = {
  success(results: Record<number, Record<string, unknown>>): ExecutionResult {
    return { outcome: ExecutionOutcome.SUCCESS, results, error: null, cancelledBy: null };
  },
  cancelled(by = 'user'): ExecutionResult {
    return { outcome: ExecutionOutcome.CANCELLED, results: null, error: null, cancelledBy: by };
  },
  error(errorMsg: string): ExecutionResult {
    return { outcome: ExecutionOutcome.ERROR, results: null, error: errorMsg, cancelledBy: null };
  },
  isSuccess(result: ExecutionResult): boolean {
    return result.outcome === ExecutionOutcome.SUCCESS;
  },
  isCancelled(result: ExecutionResult): boolean {
    return result.outcome === ExecutionOutcome.CANCELLED;
  },
};

// ============ LLM Types (Zod Schemas for Runtime Validation) ============

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

// Inferred types from Zod schemas
export type LLMToolFunction = z.infer<typeof LLMToolFunctionSchema>;
export type LLMToolSpec = z.infer<typeof LLMToolSpecSchema>;
export type LLMToolCallFunction = z.infer<typeof LLMToolCallFunctionSchema>;
export type LLMToolCall = z.infer<typeof LLMToolCallSchema>;
export type LLMChatMessage = z.infer<typeof LLMChatMessageSchema>;
export type LLMChatMetrics = z.infer<typeof LLMChatMetricsSchema>;
export type LLMToolHistoryItem = z.infer<typeof LLMToolHistoryItemSchema>;
export type LLMThinkingHistoryItem = z.infer<typeof LLMThinkingHistoryItemSchema>;

// ============ Parameter Types ============

export type ParamScalar = string | number | boolean;
export type ParamValue = ParamScalar | null | ParamScalar[] | Record<string, unknown>;
export type ParamType = 'text' | 'textarea' | 'number' | 'integer' | 'int' | 'float' | 'combo' | 'boolean';

export interface ParamMeta {
  name: string;
  type?: ParamType;
  default?: ParamValue;
  options?: ParamScalar[];
  min?: number;
  max?: number;
  step?: number;
  precision?: number;
  label?: string;
  unit?: string;
  description?: string;
}

export type DefaultParams = Record<string, ParamValue>;
export type NodeInputs = Record<string, unknown>;
export type NodeOutputs = Record<string, unknown>;

// ============ Graph Serialization Types ============

export interface SerialisedLink {
  id: number;
  origin_id: number;
  origin_slot: number;
  target_id: number;
  target_slot: number;
  type: unknown;
  parentId?: number;
}

export interface SerialisedNodeInput {
  name: string;
  type: unknown;
  linkIds?: number[];
}

export interface SerialisedNodeOutput {
  name: string;
  type: unknown;
  linkIds?: number[];
}

export interface SerialisedNode {
  id: number;
  type: string;
  title?: string;
  pos?: number[];
  size?: number[];
  flags?: Record<string, unknown>;
  order?: number;
  mode?: number;
  inputs?: SerialisedNodeInput[];
  outputs?: SerialisedNodeOutput[];
  properties?: Record<string, unknown>;
  shape?: unknown;
  boxcolor?: string;
  color?: string;
  bgcolor?: string;
  showAdvanced?: boolean;
  widgets_values?: unknown[];
}

export interface SerialisedGraphState {
  lastNodeId: number;
  lastLinkId: number;
  lastGroupId: number;
  lastRerouteId: number;
}

export interface SerialisableGraph {
  id?: string;
  revision?: number;
  version?: number;
  state?: SerialisedGraphState;
  nodes?: SerialisedNode[];
  links?: SerialisedLink[];
  floatingLinks?: SerialisedLink[];
  reroutes?: Array<Record<string, unknown>>;
  groups?: Array<Record<string, unknown>>;
  extra?: Record<string, unknown>;
  definitions?: Record<string, unknown>;
}

// ============ Progress Types ============

export interface ProgressEvent {
  node_id: number;
  state: ProgressState;
  progress?: number;
  text?: string;
  meta?: Record<string, unknown>;
}

export type ProgressCallback = (event: ProgressEvent) => void;
export type ResultCallback = (nodeId: number, output: Record<string, unknown>) => void;

// ============ Type Aliases ============

export type AssetSymbolList = AssetSymbol[];
export type IndicatorDict = Record<string, number>;
export type AnyList = unknown[];
export type ConfigDict = Record<string, unknown>;
export type OHLCVBundle = Map<string, OHLCVBar[]>; // Map uses AssetSymbol.key as key
export type LLMChatMessageList = LLMChatMessage[];
export type LLMToolSpecList = LLMToolSpec[];
export type LLMToolHistory = LLMToolHistoryItem[];
export type LLMThinkingHistory = LLMThinkingHistoryItem[];

// ============ Node Registry Type ============

// Forward declaration - actual Base class defined in base-node.ts
export type NodeConstructor = new (
  id: number,
  params: Record<string, unknown>,
  graphContext?: Record<string, unknown>
) => unknown;

export type NodeRegistry = Record<string, NodeConstructor>;

// ============ Validation Helpers ============

export function validateLLMToolSpec(obj: unknown): LLMToolSpec | null {
  const result = LLMToolSpecSchema.safeParse(obj);
  return result.success ? result.data : null;
}

export function validateLLMChatMessage(obj: unknown): LLMChatMessage | null {
  const result = LLMChatMessageSchema.safeParse(obj);
  return result.success ? result.data : null;
}

export function serializeForApi(obj: unknown): unknown {
  if (obj === null || obj === undefined) {
    return obj;
  }
  if (Array.isArray(obj)) {
    return obj.map(serializeForApi);
  }
  if (obj instanceof AssetSymbol) {
    return obj.toDict();
  }
  if (typeof obj === 'object') {
    const result: Record<string, unknown> = {};
    for (const [key, value] of Object.entries(obj)) {
      result[key] = serializeForApi(value);
    }
    return result;
  }
  return obj;
}

// ============ Node Exceptions ============

export class NodeError extends Error {
  constructor(message: string) {
    super(message);
    this.name = 'NodeError';
  }
}

export class NodeValidationError extends NodeError {
  constructor(nodeId: number, message: string) {
    super(`Node ${nodeId}: ${message}`);
    this.name = 'NodeValidationError';
  }
}

export class NodeExecutionError extends NodeError {
  originalError?: Error;

  constructor(nodeId: number, message: string, originalError?: Error) {
    super(`Node ${nodeId}: ${message}`);
    this.name = 'NodeExecutionError';
    this.originalError = originalError;
  }
}

// ============ Type Registry ============

export const TYPE_REGISTRY: Record<string, unknown> = {
  AssetSymbol,
  AssetSymbolList: [] as AssetSymbolList,
  Exchange: '' as string,
  Timestamp: 0 as number,
  IndicatorDict: {} as IndicatorDict,
  AnyList: [] as AnyList,
  ConfigDict: {} as ConfigDict,
  OHLCVBundle: new Map() as OHLCVBundle,
  Score: 0 as number,
  LLMChatMessage: {} as LLMChatMessage,
  LLMChatMessageList: [] as LLMChatMessageList,
  LLMToolSpec: {} as LLMToolSpec,
  LLMToolSpecList: [] as LLMToolSpecList,
  LLMChatMetrics: {} as LLMChatMetrics,
  LLMToolHistory: [] as LLMToolHistory,
  LLMThinkingHistory: [] as LLMThinkingHistory,
  IndicatorValue: {} as IndicatorValue,
  IndicatorResult: {} as IndicatorResult,
};

export function getType(typeName: string): unknown {
  if (!(typeName in TYPE_REGISTRY)) {
    throw new Error(`Unknown type: ${typeName}`);
  }
  return TYPE_REGISTRY[typeName];
}
