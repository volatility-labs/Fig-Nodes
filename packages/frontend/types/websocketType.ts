// websocketType.ts - Type definitions for WebSocket communication between frontend and backend
//
// NOTE: These types are manually maintained for now. In the future, consider generating them
// from the OpenAPI spec using: npm run generate-types
//
// The corresponding Pydantic schemas are defined in server/api/websocket_schemas.py

import type { SerialisableGraph } from '@fig-node/litegraph/dist/types/serialisation';
import type { ExecutionResults } from './resultTypes';

// ============================================================================
// SHARED ENUMS
// ============================================================================

export enum ExecutionState {
    QUEUED = "queued",
    RUNNING = "running",
    FINISHED = "finished",
    ERROR = "error",
    CANCELLED = "cancelled"
}

export enum ProgressState {
    START = "start",
    UPDATE = "update",
    DONE = "done",
    ERROR = "error",
    STOPPED = "stopped"
}

// ============================================================================
// CLIENT → SERVER MESSAGES
// ============================================================================

export interface ClientToServerGraphMessage {
    type: 'graph';
    graph_data: SerialisableGraph;
}

export interface ClientToServerStopMessage {
    type: 'stop';
}

export interface ClientToServerConnectMessage {
    type: 'connect';
    session_id?: string;
}

export type ClientToServerMessage = ClientToServerGraphMessage | ClientToServerStopMessage | ClientToServerConnectMessage;

// ============================================================================
// SERVER → CLIENT MESSAGES
// ============================================================================

export interface ServerToClientStatusMessage {
    type: 'status';
    state: ExecutionState;
    message: string;
    job_id: number;
}

export interface ServerToClientErrorMessage {
    type: 'error';
    message: string;
    code?: 'MISSING_API_KEYS';
    missing_keys?: string[];
    job_id?: number;
}

export interface ServerToClientStoppedMessage {
    type: 'stopped';
    message: string;
    job_id?: number;
}

export interface ServerToClientDataMessage {
    type: 'data';
    results: ExecutionResults;
    job_id: number;
}

export interface ServerToClientProgressMessage {
    type: 'progress';
    node_id?: number;
    progress?: number;
    text?: string;
    state?: ProgressState;
    meta?: Record<string, unknown>;
    job_id: number;
}

export interface ServerToClientQueuePositionMessage {
    type: 'queue_position';
    position: number;
    job_id: number;
}

export interface ServerToClientSessionMessage {
    type: 'session';
    session_id: string;
}

export type ServerToClientMessage =
    | ServerToClientStatusMessage
    | ServerToClientErrorMessage
    | ServerToClientStoppedMessage
    | ServerToClientDataMessage
    | ServerToClientProgressMessage
    | ServerToClientQueuePositionMessage
    | ServerToClientSessionMessage;

// ============================================================================
// TYPE GUARDS
// ============================================================================

export function isErrorMessage(msg: ServerToClientMessage): msg is ServerToClientErrorMessage {
    return msg.type === 'error';
}

export function isStatusMessage(msg: ServerToClientMessage): msg is ServerToClientStatusMessage {
    return msg.type === 'status';
}

export function isStoppedMessage(msg: ServerToClientMessage): msg is ServerToClientStoppedMessage {
    return msg.type === 'stopped';
}

export function isDataMessage(msg: ServerToClientMessage): msg is ServerToClientDataMessage {
    return msg.type === 'data';
}

export function isProgressMessage(msg: ServerToClientMessage): msg is ServerToClientProgressMessage {
    return msg.type === 'progress';
}

export function isQueuePositionMessage(msg: ServerToClientMessage): msg is ServerToClientQueuePositionMessage {
    return msg.type === 'queue_position';
}

export function isSessionMessage(msg: ServerToClientMessage): msg is ServerToClientSessionMessage {
    return msg.type === 'session';
}

