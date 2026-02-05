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
export type ParamType = 'text' | 'textarea' | 'number' | 'integer' | 'int' | 'float' | 'combo' | 'boolean' | 'fileupload';

export interface ParamMeta {
  name: string;
  type?: ParamType;
  default?: ParamValue;
  options?: ParamScalar[] | Record<string, unknown>;
  min?: number;
  max?: number;
  step?: number;
  precision?: number;
  label?: string;
  unit?: string;
  description?: string;
}

// ============ Output Display Types (Option A: Separate from Input Widgets) ============

/**
 * Output display types for rendering execution results.
 * These are separate from input widgets (params_meta) and handle how
 * node outputs are visualized.
 */
export type OutputDisplayType =
  | 'text-display'      // Scrollable text with formatting, copy, streaming
  | 'image-gallery'     // Grid of images with aspect ratio preservation
  | 'image-viewer'      // Zoomable/pannable single or multi-image display
  | 'chart-preview'     // Mini candlestick/line chart with modal
  | 'note-display'      // Uniform colored note (no output, just display)
  | 'none';             // No output display

/**
 * Configuration for output display renderers.
 * Each display type has specific options.
 */
export interface OutputDisplayConfig {
  /** Display type */
  type: OutputDisplayType;

  /** Which result key to bind to (default: 'output' or first key) */
  bind?: string;

  /** Common options */
  options?: OutputDisplayOptions;
}

/**
 * Options for output display renderers.
 */
export interface OutputDisplayOptions {
  // ============ Common ============
  /** Placeholder text when no data */
  placeholder?: string;

  // ============ text-display ============
  /** Enable scrolling (default: true) */
  scrollable?: boolean;
  /** Show copy button (default: true) */
  copyButton?: boolean;
  /** Available formats for format selector */
  formats?: ('auto' | 'json' | 'plain' | 'markdown')[];
  /** Default format */
  defaultFormat?: 'auto' | 'json' | 'plain' | 'markdown';
  /** Support streaming updates */
  streaming?: boolean;

  // ============ image-gallery ============
  /** Auto-resize node to fit images */
  autoResize?: boolean;
  /** Preserve aspect ratio when displaying images */
  preserveAspectRatio?: boolean;
  /** Grid layout: 'auto' calculates based on image count */
  gridLayout?: 'auto' | { cols: number; rows: number };
  /** Text to show when no images */
  emptyText?: string;

  // ============ image-viewer ============
  /** Enable zoom with shift+scroll */
  zoomable?: boolean;
  /** Enable pan/scroll */
  pannable?: boolean;
  /** Enable infinite scroll for grid */
  infiniteScroll?: boolean;
  /** Minimum zoom level */
  minZoom?: number;
  /** Maximum zoom level */
  maxZoom?: number;

  // ============ chart-preview ============
  /** Chart type */
  chartType?: 'candlestick' | 'line';
  /** Enable click to open modal */
  modalEnabled?: boolean;
  /** Show symbol selector for multi-symbol data */
  symbolSelector?: boolean;

  // ============ note-display ============
  /** Uniform color for title and body */
  uniformColor?: string;
  /** Lock render order (negative = background) */
  orderLocked?: number;
  /** Enable double-click to edit title */
  titleEditable?: boolean;
}

// ============ Node UI Configuration (ComfyUI-style + Option B Extensions) ============

/**
 * Result display mode for nodes.
 * - 'none': Don't display results in node body
 * - 'json': Display raw JSON
 * - 'text': Display as plain text
 * - 'summary': Use result formatter template
 * - 'custom': Requires custom UI class
 */
export type ResultDisplayMode = 'none' | 'json' | 'text' | 'summary' | 'custom';

/**
 * Node action button configuration.
 * Actions are rendered as buttons in the node UI.
 */
export interface NodeAction {
  /** Unique identifier for the action */
  id: string;
  /** Display label for the button */
  label: string;
  /** Optional icon (emoji or icon name) */
  icon?: string;
  /** Optional tooltip */
  tooltip?: string;
}

/**
 * Result formatter configuration for summary display mode.
 */
export interface ResultFormatter {
  /** Template type */
  type: 'template' | 'fields';
  /** Template string with {{field}} placeholders */
  template?: string;
  /** Fields to display (for 'fields' type) */
  fields?: string[];
  /** Maximum lines to display */
  maxLines?: number;
}

// ============ Option B: Extended Node UI Types ============

/**
 * Widget types that can appear in node body.
 */
export type BodyWidgetType =
  | 'text'       // Simple text display
  | 'textarea'   // Multi-line text input
  | 'code'       // Code editor with syntax highlighting
  | 'json'       // JSON viewer/editor
  | 'image'      // Image display
  | 'chart'      // Simple chart (sparkline, bar, etc.)
  | 'table'      // Data table
  | 'progress'   // Progress bar
  | 'status'     // Status indicator
  | 'custom';    // Requires custom renderer

/**
 * Data source configuration for dynamic widget data.
 * Frontend fetches from backend API based on this config.
 */
export interface DataSource {
  /** API endpoint to fetch data from (relative to base URL) */
  endpoint: string;
  /** HTTP method */
  method?: 'GET' | 'POST';
  /** Query params to include (can reference node params with {{param}}) */
  params?: Record<string, string>;
  /** HTTP headers to include in the request */
  headers?: Record<string, string>;
  /** How often to refresh in ms (0 = never, -1 = on param change) */
  refreshInterval?: number;
  /** Transform the response data (JSONPath-like selector, e.g., 'data' or 'data[*].id') */
  transform?: string;
  /** Target combo widget param name to populate with fetched values */
  targetParam?: string;
  /** Field to extract from each item when transform returns an array of objects (e.g., 'id') */
  valueField?: string;
  /** Fallback values if fetch fails */
  fallback?: unknown[];
}

/**
 * Body widget configuration.
 * Widgets that appear in the node body beyond param widgets.
 */
export interface BodyWidget {
  /** Widget type */
  type: BodyWidgetType;
  /** Unique ID for this widget */
  id: string;
  /** Label (optional) */
  label?: string;
  /** Data binding - which output/input/param to display (e.g., 'params.min_rsi', 'result.count') */
  bind?: string;
  /** Dynamic data source (alternative to static binding) */
  dataSource?: DataSource;
  /** Widget-specific options */
  options?: BodyWidgetOptions;
  /** Condition for showing widget (simple expression, e.g., 'showChart === true') */
  showIf?: string;
}

/**
 * Widget-specific options for body widgets.
 * Different widget types use different subsets of these options.
 */
export interface BodyWidgetOptions {
  // Common options
  [key: string]: unknown;

  // Textarea-specific options
  /** Placeholder text for empty textarea */
  placeholder?: string;
  /** Hide widget when zoomed out (default: true) */
  hideOnZoom?: boolean;
  /** Zoom threshold below which to hide widget (default: 0.5) */
  zoomThreshold?: number;
  /** Enable/disable spellcheck (default: false) */
  spellcheck?: boolean;
  /** Number of visible rows (for sizing hints) */
  rows?: number;
  /** Make textarea read-only (default: false) */
  readonly?: boolean;

  // Fileupload-specific options
  /** Accepted file types (e.g., '.txt,.md,.json') */
  accept?: string;
  /** Maximum file size in bytes */
  maxSize?: number;

  // Chart/progress options
  /** Color for chart lines or progress bars */
  color?: string;
  /** Height for chart widgets */
  height?: number;

  // Table options
  /** Column configuration for table widgets */
  columns?: Array<{ key: string; label: string; width?: number }>;
  /** Maximum number of rows to display */
  maxRows?: number;

  // Text/JSON options
  /** Maximum number of lines to display */
  maxLines?: number;
  /** Template string with {{param}} placeholders */
  template?: string;
}

/**
 * Result widget configuration - how to display execution results.
 * More powerful than ResultFormatter, allows for structured result display.
 */
export interface ResultWidget {
  /** Display type */
  type: 'json' | 'text' | 'table' | 'image' | 'chart' | 'custom';
  /** Which output key to display (default: first output or 'result') */
  bind?: string;
  /** Maximum height before scrolling */
  maxHeight?: number;
  /** For table type: column configuration */
  columns?: Array<{ key: string; label: string; width?: number }>;
  /** For text type: formatting template with {{field}} placeholders */
  template?: string;
  /** For chart type: chart configuration */
  chartConfig?: Record<string, unknown>;
}

/**
 * Slot display configuration.
 */
export interface SlotConfig {
  /** Color for this slot */
  color?: string;
  /** Shape: 'circle' | 'square' | 'arrow' */
  shape?: string;
  /** Whether to show type label */
  showType?: boolean;
}

/**
 * Node UI configuration - defines how a node appears and behaves in the frontend.
 * This follows the ComfyUI pattern where UI is configured in backend node definitions.
 *
 * The frontend reads this configuration and renders the node accordingly,
 * eliminating the need for separate UI files for most nodes.
 *
 * Option B extensions add: body widgets, data sources, and enhanced result display.
 */
export interface NodeUIConfig {
  // === Basic layout ===
  /** Node dimensions [width, height] */
  size?: [number, number];

  /** Whether the node can be resized */
  resizable?: boolean;

  /** Whether the node can be collapsed */
  collapsable?: boolean;

  /** Custom node background color */
  color?: string;

  /** Custom node body background color */
  bgcolor?: string;

  // === Output Display (Option A) ===
  /**
   * Output display configuration.
   * Defines how execution results are rendered in the node body.
   * This is separate from input widgets (params_meta).
   */
  outputDisplay?: OutputDisplayConfig;

  // === Body widgets (Option B - legacy, prefer outputDisplay) ===
  /** Body widgets to display in the node (beyond param widgets) */
  body?: BodyWidget[];

  // === Result display ===
  /** Whether to display execution results in the node body */
  displayResults?: boolean;

  /** Result display mode (legacy, use resultWidget for more control) */
  resultDisplay?: ResultDisplayMode;

  /** Result formatter configuration (legacy, for 'summary' mode) */
  resultFormatter?: ResultFormatter;

  /** Enhanced result widget configuration (Option B) */
  resultWidget?: ResultWidget;

  // === Actions ===
  /** Action buttons to display in the node */
  actions?: NodeAction[];

  // === Slot customization (Option B) ===
  /** Input slot configurations (keyed by input name) */
  inputSlots?: Record<string, SlotConfig>;

  /** Output slot configurations (keyed by output name) */
  outputSlots?: Record<string, SlotConfig>;

  /** Input slot tooltips (keyed by input name) */
  inputTooltips?: Record<string, string>;

  /** Output slot tooltips (keyed by output name) */
  outputTooltips?: Record<string, string>;

  // === Data sources (Option B) ===
  /** Named data sources for dynamic widgets */
  dataSources?: Record<string, DataSource>;

  // === Fallback flag ===
  /**
   * Whether this node requires a custom UI class.
   * If true, the frontend will look for a corresponding *NodeUI.ts file.
   * If false (default), the node will be rendered using BaseCustomNode.
   */
  requiresCustomUI?: boolean;
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
export type OHLCVBundle = Map<AssetSymbol, OHLCVBar[]>; // Map uses AssetSymbol object as key
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

export const TYPE_REGISTRY = {
  // Primitives
  any: {} as unknown,
  string: '' as string,
  number: 0 as number,
  boolean: false as boolean,
  object: {} as object,
  array: [] as unknown[],
  // Domain types
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
} as const;

/** Valid type names for node inputs/outputs */
export type RegisteredTypeName = keyof typeof TYPE_REGISTRY;

/**
 * Returns the canonical type name string for use in node input/output definitions.
 * Provides compile-time validation that the type exists in TYPE_REGISTRY.
 */
export function getType<T extends RegisteredTypeName>(typeName: T): T {
  if (!(typeName in TYPE_REGISTRY)) {
    throw new Error(`Unknown type: ${typeName}`);
  }
  return typeName;
}
