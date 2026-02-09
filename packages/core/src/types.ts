// src/types.ts
// Execution result types, progress events, callbacks, credentials, and execution-related enums

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
  type: string;
  multi?: boolean;
  optional?: boolean;
}

export const EXEC_SOCKET_TYPE = 'exec';

export function isExecPort(spec: PortSpec): boolean {
  return spec.type === EXEC_SOCKET_TYPE;
}

export type NodeInputs = Record<string, PortSpec>;
export type NodeOutputs = Record<string, PortSpec>;

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

// ============ Re-exports from sibling modules ============

export type {
  OutputDisplayType,
  OutputDisplayConfig,
  OutputDisplayOptions,
  ResultDisplayMode,
  NodeAction,
  ResultFormatter,
  BodyWidgetType,
  DataSource,
  BodyWidget,
  BodyWidgetOptions,
  ResultWidget,
  SlotConfig,
  NodeUIConfig,
} from './node-ui.js';
