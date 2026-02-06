// src/types/execution.ts
// Execution result types, progress events, and callbacks

import { ExecutionOutcome, ProgressState, AssetSymbol } from './domain';

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

// ============ Node Registry Type ============

export type NodeConstructor = new (
  id: number,
  params: Record<string, unknown>,
  graphContext?: Record<string, unknown>
) => unknown;

export type NodeRegistry = Record<string, NodeConstructor>;

// ============ Serialization Helper ============

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
