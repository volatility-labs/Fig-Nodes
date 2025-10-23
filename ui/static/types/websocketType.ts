// websocketType.ts - Type definitions for WebSocket communication between frontend and backend
//
// NOTE: These types are manually maintained for now. In the future, consider generating them
// from the OpenAPI spec using: npm run generate-types
//
// The corresponding Pydantic schemas are defined in ui/api/websocket_schemas.py

import type { SerialisableGraph } from '@comfyorg/litegraph/dist/types/serialisation';
import type { ExecutionResults } from './resultTypes';

// Progress state enum (matches backend ProgressState)
export type WebSocketProgressState = 'start' | 'update' | 'done' | 'error' | 'stopped';

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

export type ClientToServerMessage = ClientToServerGraphMessage | ClientToServerStopMessage;

// ============================================================================
// SERVER → CLIENT MESSAGES
// ============================================================================

export interface ServerToClientStatusMessage {
    type: 'status';
    message: string;
}

export interface ServerToClientErrorMessage {
    type: 'error';
    message: string;
    code?: 'MISSING_API_KEYS';
    missing_keys?: string[];
}

export interface ServerToClientStoppedMessage {
    type: 'stopped';
    message: string;
}

export interface ServerToClientDataMessage {
    type: 'data';
    results: ExecutionResults;
    stream?: boolean;
}

export interface ServerToClientProgressMessage {
    type: 'progress';
    node_id?: number;
    progress?: number;
    text?: string;
    state?: string;
    meta?: Record<string, unknown>;
}

export interface ServerToClientQueuePositionMessage {
    type: 'queue_position';
    position: number;
}

export type ServerToClientMessage =
    | ServerToClientStatusMessage
    | ServerToClientErrorMessage
    | ServerToClientStoppedMessage
    | ServerToClientDataMessage
    | ServerToClientProgressMessage
    | ServerToClientQueuePositionMessage;

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

