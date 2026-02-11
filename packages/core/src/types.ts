// src/types.ts
// All core type definitions: execution, credentials, ports, params, node UI, node schema, messages

import type { Graph } from './graph.js';

// ============ Execution Enums ============

export enum ProgressState {
  START = 'start',
  UPDATE = 'update',
  DONE = 'done',
  ERROR = 'error',
  STOPPED = 'stopped',
}

export enum ExecutionState {
  QUEUED = 'queued',
  RUNNING = 'running',
  FINISHED = 'finished',
  ERROR = 'error',
  CANCELLED = 'cancelled',
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

// ============ Execution Result ============

export interface ExecutionResult {
  outcome: ExecutionOutcome;
  results: Record<string, Record<string, unknown>> | null;
  error: string | null;
  cancelledBy: string | null;
}

// ============ Progress Types ============

export interface ProgressEvent {
  node_id: string;
  state: ProgressState;
  progress?: number;
  text?: string;
  meta?: Record<string, unknown>;
}

export type ProgressCallback = (event: ProgressEvent) => void;
export type ResultCallback = (nodeId: string, output: Record<string, unknown>) => void;

// ============ Node Registry Type ============

export type NodeConstructor = new (
  nodeId: string,
  params: Record<string, unknown>,
  graphContext?: Record<string, unknown>
) => unknown;

export type NodeRegistry = Record<string, NodeConstructor>;

// ============ Serialization Helper ============

export function serializeForApi(obj: unknown, seen?: WeakSet<object>): unknown {
  if (obj === null || obj === undefined) {
    return obj;
  }
  if (typeof obj !== 'object') {
    return obj;
  }

  // Circular reference protection
  if (!seen) seen = new WeakSet();
  if (seen.has(obj)) return '[Circular]';
  seen.add(obj);

  if (Array.isArray(obj)) {
    return obj.map((item) => serializeForApi(item, seen));
  }
  // Handle Map objects — convert to plain object with serialized keys
  if (obj instanceof Map) {
    const result: Record<string, unknown> = {};
    for (const [key, value] of obj) {
      const serializedKey = typeof key === 'object' && key !== null && 'key' in key
        ? String(key.key)
        : String(key);
      result[serializedKey] = serializeForApi(value, seen);
    }
    return result;
  }
  // Duck-type toDict() instead of instanceof AssetSymbol
  if ('toDict' in obj && typeof (obj as Record<string, unknown>).toDict === 'function') {
    return (obj as { toDict(): Record<string, unknown> }).toDict();
  }
  const result: Record<string, unknown> = {};
  for (const [key, value] of Object.entries(obj)) {
    result[key] = serializeForApi(value, seen);
  }
  return result;
}

// ============ Credentials ============

/**
 * Read-only interface for accessing credentials (API keys, tokens, etc.).
 */
export interface CredentialProvider {
  get(key: string): string | undefined;
  has(key: string): boolean;
}

/**
 * Key used to inject the CredentialProvider into graphContext.
 */
export const CREDENTIAL_PROVIDER_KEY = '__credentialProvider__';

// ============ Port and Param Types ============

export type ParamScalar = string | number | boolean;
export type ParamValue = ParamScalar | null | ParamScalar[] | Record<string, unknown>;
export type ParamType =
  | 'text'
  | 'textarea'
  | 'number'
  | 'integer'
  | 'int'
  | 'float'
  | 'combo'
  | 'boolean'
  | 'fileupload';

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

export interface PortSpec {
  type: PortType;
  multi?: boolean;
  optional?: boolean;
}

/** All known port types. Single source of truth for port type validation and OpenAPI schemas. */
export const PORT_TYPES = [
  // Primitives
  'any',
  'string',
  'number',
  'boolean',
  'object',
  'array',
  'exec',
  // Generic
  'Exchange',
  'Timestamp',
  'Score',
  // Market domain
  'AssetSymbol',
  'AssetSymbolList',
  'OHLCVBundle',
  'IndicatorDict',
  'IndicatorValue',
  'IndicatorResult',
  'IndicatorResultList',
  'AnyList',
  'ConfigDict',
  // LLM domain
  'LLMChatMessage',
  'LLMChatMessageList',
  'LLMToolSpec',
  'LLMToolSpecList',
  'LLMChatMetrics',
  'LLMToolHistory',
  'LLMThinkingHistory',
  'LLMToolHistoryItem',
  'LLMThinkingHistoryItem',
] as const;

/** Union of all valid port type names. */
export type PortType = (typeof PORT_TYPES)[number];

/** Runtime set for O(1) validation lookups. */
const _validTypes: ReadonlySet<string> = new Set<string>(PORT_TYPES);

/** Shorthand aliases resolved to canonical PortType names. */
export const TYPE_ALIASES: Readonly<Record<string, PortType>> = {
  str: 'string',
  int: 'number',
  float: 'number',
  bool: 'boolean',
  list: 'array',
  dict: 'object',
};

/** Check if a type name (or alias) is a valid port type. */
export function isValidPortType(name: string): name is PortType {
  const resolved = TYPE_ALIASES[name] ?? name;
  return _validTypes.has(resolved);
}

/** A named port: PortSpec + the port name. Used in NodeDefinition and NodeSchema. */
export interface PortDef extends PortSpec {
  name: string;
}

/** Convenience factory: `port('ohlcv_bundle', 'OHLCVBundle', { multi: true })` -> PortDef */
export function port(name: string, type: PortType, opts?: { multi?: boolean; optional?: boolean }): PortDef {
  const spec: PortDef = { name, type };
  if (opts?.multi) spec.multi = true;
  if (opts?.optional) spec.optional = true;
  return spec;
}

/** Shorthand factory for exec (control-flow) ports. */
export function execPort(name: string): PortDef {
  return { name, type: 'exec' };
}

export const EXEC_SOCKET_TYPE = 'exec';

export function isExecPort(spec: PortSpec): boolean {
  return spec.type === EXEC_SOCKET_TYPE;
}

export type NodeInputs = PortDef[];
export type NodeOutputs = PortDef[];

// ============ Node Error Types ============

export class NodeError extends Error {
  constructor(message: string) {
    super(message);
    this.name = 'NodeError';
  }
}

export class NodeValidationError extends NodeError {
  constructor(nodeId: string, message: string) {
    super(`Node ${nodeId}: ${message}`);
    this.name = 'NodeValidationError';
  }
}

export class NodeExecutionError extends NodeError {
  originalError?: Error;

  constructor(nodeId: string, message: string, originalError?: Error) {
    super(`Node ${nodeId}: ${message}`);
    this.name = 'NodeExecutionError';
    this.originalError = originalError;
  }
}

// ============ Output Display Types ============

export type OutputDisplayType =
  | 'text-display'
  | 'text-display-dom'
  | 'image-gallery'
  | 'image-viewer'
  | 'chart-preview'
  | 'note-display'
  | 'none';

export interface OutputDisplayConfig {
  type: OutputDisplayType;
  bind?: string;
  options?: OutputDisplayOptions;
}

export interface OutputDisplayOptions {
  // Common
  placeholder?: string;

  // text-display
  scrollable?: boolean;
  copyButton?: boolean;
  formats?: ('auto' | 'json' | 'plain' | 'markdown')[];
  defaultFormat?: 'auto' | 'json' | 'plain' | 'markdown';
  streaming?: boolean;

  // image-gallery
  autoResize?: boolean;
  preserveAspectRatio?: boolean;
  gridLayout?: 'auto' | { cols: number; rows: number };
  emptyText?: string;

  // image-viewer
  zoomable?: boolean;
  pannable?: boolean;
  infiniteScroll?: boolean;
  minZoom?: number;
  maxZoom?: number;

  // chart-preview
  chartType?: 'candlestick' | 'line';
  modalEnabled?: boolean;
  symbolSelector?: boolean;

  // note-display
  uniformColor?: string;
  orderLocked?: number;
  titleEditable?: boolean;
}

// ============ Result Display Types ============

export type ResultDisplayMode = 'none' | 'json' | 'text' | 'summary' | 'custom';

export interface NodeAction {
  id: string;
  label: string;
  icon?: string;
  tooltip?: string;
}

// ============ Body Widget Types ============

export type BodyWidgetType =
  | 'text'
  | 'textarea'
  | 'code'
  | 'json'
  | 'image'
  | 'chart'
  | 'table'
  | 'progress'
  | 'status'
  | 'combo'
  | 'number'
  | 'integer'
  | 'int'
  | 'float'
  | 'boolean'
  | 'custom';

export interface DataSource {
  endpoint: string;
  method?: 'GET' | 'POST';
  params?: Record<string, string>;
  headers?: Record<string, string>;
  refreshInterval?: number;
  transform?: string;
  targetParam?: string;
  valueField?: string;
  fallback?: unknown[];
}

interface BodyWidgetBase {
  id: string;
  label?: string;
  bind?: string;
  dataSource?: DataSource;
  showIf?: string;
}

interface TextWidgetOptions {
  placeholder?: string;
}

interface ComboWidgetOptions {
  options?: Array<string | number | boolean>;
}

interface NumberWidgetOptions {
  min?: number;
  max?: number;
  step?: number;
  unit?: string;
}

type BodyWidgetOptionsByType = {
  text: TextWidgetOptions;
  textarea: TextWidgetOptions;
  code: TextWidgetOptions;
  json: TextWidgetOptions;
  combo: ComboWidgetOptions;
  number: NumberWidgetOptions;
  integer: NumberWidgetOptions;
  int: NumberWidgetOptions;
  float: NumberWidgetOptions;
  boolean: Record<string, never>;
  progress: Record<string, never>;
  status: Record<string, never>;
  image: Record<string, never>;
  chart: Record<string, never>;
  table: Record<string, never>;
  custom: Record<string, unknown>;
};

type BodyWidgetOfType<T extends BodyWidgetType> = BodyWidgetBase & {
  type: T;
  options?: BodyWidgetOptionsByType[T];
};

export type BodyWidget = {
  [T in BodyWidgetType]: BodyWidgetOfType<T>;
}[BodyWidgetType];

// ============ Node UI Configuration ============

export interface NodeUIConfig {
  color?: string;
  bgcolor?: string;
  outputDisplay?: OutputDisplayConfig;
  body?: BodyWidget[];
  resultDisplay?: ResultDisplayMode;
  actions?: NodeAction[];
  dataSources?: Record<string, DataSource>;
}

// ============ Node Schema (shared API contract) ============

/** Metadata about a node type, returned by GET /api/v1/nodes. */
export interface NodeSchema {
  inputs: NodeInputs;
  outputs: NodeOutputs;
  params: ParamMeta[];
  category: NodeCategory;
  requiredKeys: string[];
  description: string;
  uiConfig: NodeUIConfig;
}

/** Map of node class names to their schema. */
export type NodeSchemaMap = Record<string, NodeSchema>;

// ============ WebSocket Message Types ============

export type ExecutionResults = Record<string, Record<string, unknown>>;

// ---- Client → Server Messages ----

export interface ClientGraphMessage {
  type: 'graph';
  graph_data: Graph;
}

export interface ClientStopMessage {
  type: 'stop';
}

export interface ClientConnectMessage {
  type: 'connect';
  session_id?: string;
}

export interface ClientPingMessage {
  type: 'ping';
}

export type ClientMessage =
  | ClientGraphMessage
  | ClientStopMessage
  | ClientConnectMessage
  | ClientPingMessage;

// ---- Server → Client Messages ----

export interface ServerStatusMessage {
  type: 'status';
  state: ExecutionState;
  message: string;
  job_id: number;
}

export interface ServerErrorMessage {
  type: 'error';
  message: string;
  code?: 'MISSING_API_KEYS' | 'VALIDATION_ERROR' | 'EXECUTION_ERROR' | null;
  missing_keys?: string[];
  job_id?: number;
}

export interface ServerStoppedMessage {
  type: 'stopped';
  message: string;
  job_id?: number;
}

export interface ServerDataMessage {
  type: 'data';
  results: ExecutionResults;
  job_id: number;
}

export interface ServerProgressMessage {
  type: 'progress';
  node_id: string;
  progress?: number;
  text?: string;
  state: ProgressState;
  meta?: Record<string, unknown>;
  job_id: number;
}

export interface ServerQueuePositionMessage {
  type: 'queue_position';
  position: number;
  job_id: number;
}

export interface ServerSessionMessage {
  type: 'session';
  session_id: string;
}

export interface ServerPongMessage {
  type: 'pong';
}

export type ServerMessage =
  | ServerStatusMessage
  | ServerErrorMessage
  | ServerStoppedMessage
  | ServerDataMessage
  | ServerProgressMessage
  | ServerQueuePositionMessage
  | ServerSessionMessage
  | ServerPongMessage;

// ---- Type Guards ----

export function isErrorMessage(msg: ServerMessage): msg is ServerErrorMessage {
  return msg.type === 'error';
}

export function isStatusMessage(msg: ServerMessage): msg is ServerStatusMessage {
  return msg.type === 'status';
}

export function isStoppedMessage(msg: ServerMessage): msg is ServerStoppedMessage {
  return msg.type === 'stopped';
}

export function isDataMessage(msg: ServerMessage): msg is ServerDataMessage {
  return msg.type === 'data';
}

export function isProgressMessage(msg: ServerMessage): msg is ServerProgressMessage {
  return msg.type === 'progress';
}

export function isQueuePositionMessage(msg: ServerMessage): msg is ServerQueuePositionMessage {
  return msg.type === 'queue_position';
}

export function isSessionMessage(msg: ServerMessage): msg is ServerSessionMessage {
  return msg.type === 'session';
}
