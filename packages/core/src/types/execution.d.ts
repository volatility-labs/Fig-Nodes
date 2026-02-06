import { ExecutionOutcome, ProgressState } from './domain';
export interface ExecutionResult {
    outcome: ExecutionOutcome;
    results: Record<number, Record<string, unknown>> | null;
    error: string | null;
    cancelledBy: string | null;
}
export declare const ExecutionResultFactory: {
    success(results: Record<number, Record<string, unknown>>): ExecutionResult;
    cancelled(by?: string): ExecutionResult;
    error(errorMsg: string): ExecutionResult;
    isSuccess(result: ExecutionResult): boolean;
    isCancelled(result: ExecutionResult): boolean;
};
export interface ProgressEvent {
    node_id: number;
    state: ProgressState;
    progress?: number;
    text?: string;
    meta?: Record<string, unknown>;
}
export type ProgressCallback = (event: ProgressEvent) => void;
export type ResultCallback = (nodeId: number, output: Record<string, unknown>) => void;
export type NodeConstructor = new (id: number, params: Record<string, unknown>, graphContext?: Record<string, unknown>) => unknown;
export type NodeRegistry = Record<string, NodeConstructor>;
export declare function serializeForApi(obj: unknown): unknown;
