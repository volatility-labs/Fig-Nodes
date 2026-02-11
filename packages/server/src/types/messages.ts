// Server-side message validation (Zod), builders, and parsers.
// Canonical message types are defined in @sosa/core — this file
// adds runtime validation and convenience builders for server use only.

import { z } from 'zod';
import {
  ExecutionState,
  ProgressState,
  type ClientMessage,
  type ServerStatusMessage,
  type ServerErrorMessage,
  type ServerStoppedMessage,
  type ServerDataMessage,
  type ServerProgressMessage,
  type ServerQueuePositionMessage,
  type ServerSessionMessage,
  type ServerPongMessage,
} from '@sosa/core';

// Re-export core message types (single source of truth)
export type {
  ClientMessage,
  ClientConnectMessage,
  ClientGraphMessage,
  ClientStopMessage,
  ClientPingMessage,
  ServerMessage,
  ServerStatusMessage,
  ServerErrorMessage,
  ServerStoppedMessage,
  ServerDataMessage,
  ServerProgressMessage,
  ServerQueuePositionMessage,
  ServerSessionMessage,
  ServerPongMessage,
  ExecutionResults,
} from '@sosa/core';

export { ExecutionState } from '@sosa/core';

// ============ Zod Schemas (server-side runtime validation) ============

const ClientConnectMessageSchema = z.object({
  type: z.literal('connect'),
  session_id: z.string().uuid().optional(),
});

const ClientGraphMessageSchema = z.object({
  type: z.literal('graph'),
  graph_data: z.record(z.unknown()), // Graph — validated separately via validateGraph()
});

const ClientStopMessageSchema = z.object({
  type: z.literal('stop'),
});

const ClientPingMessageSchema = z.object({
  type: z.literal('ping'),
});

const ClientMessageSchema = z.discriminatedUnion('type', [
  ClientConnectMessageSchema,
  ClientGraphMessageSchema,
  ClientStopMessageSchema,
  ClientPingMessageSchema,
]);

// ============ Message Parsing ============

/**
 * Parse a raw message into a typed client message.
 * Returns null if the message is invalid.
 */
export function parseClientMessage(data: unknown): ClientMessage | null {
  const result = ClientMessageSchema.safeParse(data);
  return result.success ? (result.data as unknown as ClientMessage) : null;
}

/**
 * Try to parse as connect message first, then graph, then stop, then ping.
 * This ordering prevents false positives (legacy pattern).
 */
export function parseClientMessageOrdered(data: unknown): ClientMessage | null {
  const connectResult = ClientConnectMessageSchema.safeParse(data);
  if (connectResult.success) return connectResult.data as ClientMessage;

  const graphResult = ClientGraphMessageSchema.safeParse(data);
  if (graphResult.success) return graphResult.data as unknown as ClientMessage;

  const stopResult = ClientStopMessageSchema.safeParse(data);
  if (stopResult.success) return stopResult.data as ClientMessage;

  const pingResult = ClientPingMessageSchema.safeParse(data);
  if (pingResult.success) return pingResult.data as ClientMessage;

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
  state: ProgressState,
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
