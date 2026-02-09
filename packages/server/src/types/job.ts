// Job and queue types for graph execution
import type { WebSocket } from '@fastify/websocket';
import type { Graph } from '@sosa/core';

/**
 * Job execution state.
 * Follows the legacy Python implementation's state machine.
 */
export enum JobState {
  PENDING = 'pending',
  RUNNING = 'running',
  CANCELLED = 'cancelled',
  DONE = 'done',
}

/**
 * Deferred promise utility - TypeScript equivalent of Python's asyncio.Event.
 * Creates a promise that can be resolved externally.
 */
export interface Deferred<T = void> {
  promise: Promise<T>;
  resolve: (value: T) => void;
  reject: (reason?: unknown) => void;
}

export function createDeferred<T = void>(): Deferred<T> {
  let resolve!: (value: T) => void;
  let reject!: (reason?: unknown) => void;
  const promise = new Promise<T>((res, rej) => {
    resolve = res;
    reject = rej;
  });
  return { promise, resolve, reject };
}

/**
 * Represents a single graph execution job in the queue.
 */
export interface ExecutionJob {
  /** Unique job identifier */
  id: number;

  /** WebSocket connection for this job */
  websocket: WebSocket;

  /** Graph document to execute */
  graphData: Graph;

  /** AbortController for cancellation signaling (replaces asyncio.Event) */
  cancelController: AbortController;

  /** Current job state */
  state: JobState;

  /** Deferred promise that resolves when job is done (replaces asyncio.Event) */
  done: Deferred<void>;
}

/**
 * Factory function to create a new ExecutionJob.
 */
export function createExecutionJob(
  id: number,
  websocket: WebSocket,
  graphData: Graph
): ExecutionJob {
  return {
    id,
    websocket,
    graphData,
    cancelController: new AbortController(),
    state: JobState.PENDING,
    done: createDeferred<void>(),
  };
}
