// WebSocket message schemas using Zod
import { z } from 'zod';
import { ExecutionState } from '@fig-node/core';

export { ExecutionState };

// ============ Client → Server Messages ============

/**
 * Connect message - establishes or resumes a session.
 */
export const ClientConnectMessageSchema = z.object({
  type: z.literal('connect'),
  session_id: z.string().uuid().optional(),
});

export type ClientConnectMessage = z.infer<typeof ClientConnectMessageSchema>;

/**
 * Graph execution message - submits a graph for execution.
 */
export const ClientGraphMessageSchema = z.object({
  type: z.literal('graph'),
  graph_data: z.record(z.unknown()), // Graph - validated separately
});

export type ClientGraphMessage = z.infer<typeof ClientGraphMessageSchema>;

/**
 * Stop message - cancels current execution.
 */
export const ClientStopMessageSchema = z.object({
  type: z.literal('stop'),
});

export type ClientStopMessage = z.infer<typeof ClientStopMessageSchema>;

/**
 * Ping message - keep-alive.
 */
export const ClientPingMessageSchema = z.object({
  type: z.literal('ping'),
});

export type ClientPingMessage = z.infer<typeof ClientPingMessageSchema>;

/**
 * Union of all client messages.
 */
export const ClientMessageSchema = z.discriminatedUnion('type', [
  ClientConnectMessageSchema,
  ClientGraphMessageSchema,
  ClientStopMessageSchema,
  ClientPingMessageSchema,
]);

export type ClientMessage = z.infer<typeof ClientMessageSchema>;

// ============ Server → Client Messages ============

/**
 * Session established message.
 */
export const ServerSessionMessageSchema = z.object({
  type: z.literal('session'),
  session_id: z.string().uuid(),
});

export type ServerSessionMessage = z.infer<typeof ServerSessionMessageSchema>;

/**
 * Status message - reports execution state changes.
 */
export const ServerStatusMessageSchema = z.object({
  type: z.literal('status'),
  state: z.nativeEnum(ExecutionState),
  message: z.string(),
  job_id: z.number(),
});

export type ServerStatusMessage = z.infer<typeof ServerStatusMessageSchema>;

/**
 * Error message - reports errors during execution.
 */
export const ServerErrorMessageSchema = z.object({
  type: z.literal('error'),
  message: z.string(),
  code: z.enum(['MISSING_API_KEYS', 'VALIDATION_ERROR', 'EXECUTION_ERROR']).nullable(),
  missing_keys: z.array(z.string()).optional(),
  job_id: z.number().optional(),
});

export type ServerErrorMessage = z.infer<typeof ServerErrorMessageSchema>;

/**
 * Stopped message - confirms job cancellation.
 */
export const ServerStoppedMessageSchema = z.object({
  type: z.literal('stopped'),
  message: z.string(),
  job_id: z.number().optional(),
});

export type ServerStoppedMessage = z.infer<typeof ServerStoppedMessageSchema>;

/**
 * Data message - sends execution results.
 */
export const ServerDataMessageSchema = z.object({
  type: z.literal('data'),
  results: z.record(z.record(z.unknown())), // Record<nodeId, Record<outputName, value>>
  job_id: z.number(),
});

export type ServerDataMessage = z.infer<typeof ServerDataMessageSchema>;

/**
 * Progress message - reports node execution progress.
 */
export const ServerProgressMessageSchema = z.object({
  type: z.literal('progress'),
  node_id: z.string(),
  progress: z.number().min(0).max(100).optional(),
  text: z.string().optional(),
  state: z.enum(['start', 'update', 'done', 'error', 'stopped']),
  meta: z.record(z.unknown()).optional(),
  job_id: z.number(),
});

export type ServerProgressMessage = z.infer<typeof ServerProgressMessageSchema>;

/**
 * Queue position message - reports position in execution queue.
 */
export const ServerQueuePositionMessageSchema = z.object({
  type: z.literal('queue_position'),
  position: z.number(),
  job_id: z.number(),
});

export type ServerQueuePositionMessage = z.infer<typeof ServerQueuePositionMessageSchema>;

/**
 * Pong message - keep-alive response.
 */
export const ServerPongMessageSchema = z.object({
  type: z.literal('pong'),
});

export type ServerPongMessage = z.infer<typeof ServerPongMessageSchema>;

/**
 * Union of all server messages.
 */
export type ServerMessage =
  | ServerSessionMessage
  | ServerStatusMessage
  | ServerErrorMessage
  | ServerStoppedMessage
  | ServerDataMessage
  | ServerProgressMessage
  | ServerQueuePositionMessage
  | ServerPongMessage;

// ============ Message Parsing ============

/**
 * Parse a raw message into a typed client message.
 * Returns null if the message is invalid.
 */
export function parseClientMessage(data: unknown): ClientMessage | null {
  const result = ClientMessageSchema.safeParse(data);
  return result.success ? result.data : null;
}

/**
 * Try to parse as connect message first, then graph, then stop.
 * This ordering prevents false positives (legacy pattern).
 */
export function parseClientMessageOrdered(data: unknown): ClientMessage | null {
  // Try connect first (has session_id field)
  const connectResult = ClientConnectMessageSchema.safeParse(data);
  if (connectResult.success) return connectResult.data;

  // Try graph (has graph_data field)
  const graphResult = ClientGraphMessageSchema.safeParse(data);
  if (graphResult.success) return graphResult.data;

  // Try stop (just type field)
  const stopResult = ClientStopMessageSchema.safeParse(data);
  if (stopResult.success) return stopResult.data;

  // Try ping
  const pingResult = ClientPingMessageSchema.safeParse(data);
  if (pingResult.success) return pingResult.data;

  return null;
}

// ============ Message Builders ============

export function buildSessionMessage(sessionId: string): ServerSessionMessage {
  return { type: 'session', session_id: sessionId };
}

export function buildStatusMessage(
  state: ExecutionState,
  message: string,
  jobId: number
): ServerStatusMessage {
  return { type: 'status', state, message, job_id: jobId };
}

export function buildErrorMessage(
  message: string,
  code: ServerErrorMessage['code'] = null,
  missingKeys?: string[],
  jobId?: number
): ServerErrorMessage {
  return {
    type: 'error',
    message,
    code,
    ...(missingKeys && { missing_keys: missingKeys }),
    ...(jobId !== undefined && { job_id: jobId }),
  };
}

export function buildStoppedMessage(message: string, jobId?: number): ServerStoppedMessage {
  return {
    type: 'stopped',
    message,
    ...(jobId !== undefined && { job_id: jobId }),
  };
}

export function buildDataMessage(
  results: Record<string, Record<string, unknown>>,
  jobId: number
): ServerDataMessage {
  return { type: 'data', results, job_id: jobId };
}

export function buildProgressMessage(
  nodeId: string,
  state: ServerProgressMessage['state'],
  jobId: number,
  options?: {
    progress?: number;
    text?: string;
    meta?: Record<string, unknown>;
  }
): ServerProgressMessage {
  return {
    type: 'progress',
    node_id: nodeId,
    state,
    job_id: jobId,
    ...options,
  };
}

export function buildQueuePositionMessage(
  position: number,
  jobId: number
): ServerQueuePositionMessage {
  return { type: 'queue_position', position, job_id: jobId };
}

export function buildPongMessage(): ServerPongMessage {
  return { type: 'pong' };
}
