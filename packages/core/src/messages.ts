// src/messages.ts
// Shared WebSocket message types for client ↔ server communication.
// Server uses Zod schemas for runtime validation; these plain interfaces
// are the shared contract consumed by both sides.

import type { Graph } from './graph.js';
import type { ExecutionState, ProgressState } from './types.js';

// ============ Execution Results ============

export type ExecutionResults = Record<string, Record<string, unknown>>;

// ============ Client → Server Messages ============

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

// ============ Server → Client Messages ============

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

// ============ Type Guards ============

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
