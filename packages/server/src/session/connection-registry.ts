// Connection registry for managing WebSocket sessions
import type { WebSocket } from '@fastify/websocket';
import { randomUUID } from 'crypto';
import type { ExecutionJob } from '../types/job.js';
import type { ClientConnectMessage, ServerSessionMessage } from '../types/messages.js';
import { buildSessionMessage } from '../types/messages.js';
import { wsSendSync, isWsConnected } from '../websocket/send-utils.js';

/**
 * ConnectionRegistry manages WebSocket sessions and their associated jobs.
 * Each session has at most one active WebSocket connection.
 *
 * TypeScript equivalent of the Python ConnectionRegistry class.
 */
export class ConnectionRegistry {
  /** Map of session_id → WebSocket */
  private sessions: Map<string, WebSocket> = new Map();

  /** Map of session_id → ExecutionJob (or null if no active job) */
  private sessionToJob: Map<string, ExecutionJob | null> = new Map();

  /**
   * Register a new WebSocket connection for a session.
   */
  register(sessionId: string, websocket: WebSocket): void {
    this.sessions.set(sessionId, websocket);
    if (!this.sessionToJob.has(sessionId)) {
      this.sessionToJob.set(sessionId, null);
    }
  }

  /**
   * Unregister a session. Includes race protection.
   * Only removes if the current WebSocket matches.
   */
  unregister(sessionId: string, websocket: WebSocket): void {
    const currentWs = this.sessions.get(sessionId);
    if (currentWs === websocket) {
      this.sessions.delete(sessionId);
    }
  }

  /**
   * Check if a session exists.
   */
  hasSession(sessionId: string): boolean {
    return this.sessions.has(sessionId) || this.sessionToJob.has(sessionId);
  }

  /**
   * Get the WebSocket for a session.
   */
  getWebsocket(sessionId: string): WebSocket | undefined {
    return this.sessions.get(sessionId);
  }

  /**
   * Set the active job for a session.
   */
  setJob(sessionId: string, job: ExecutionJob | null): void {
    this.sessionToJob.set(sessionId, job);
  }

  /**
   * Get the active job for a session.
   */
  getJob(sessionId: string): ExecutionJob | null | undefined {
    return this.sessionToJob.get(sessionId);
  }

  /**
   * Get all session IDs.
   */
  getAllSessionIds(): string[] {
    return Array.from(this.sessions.keys());
  }

  /**
   * Get the session ID for a WebSocket.
   */
  getSessionIdForWebsocket(websocket: WebSocket): string | undefined {
    for (const [sessionId, ws] of this.sessions.entries()) {
      if (ws === websocket) {
        return sessionId;
      }
    }
    return undefined;
  }
}

/**
 * Close an old WebSocket connection if it exists and is different from the new one.
 * Prevents duplicate connections for the same session.
 */
export function closeOldConnectionIfExists(
  registry: ConnectionRegistry,
  sessionId: string,
  newWebsocket: WebSocket
): void {
  const oldWs = registry.getWebsocket(sessionId);

  // Only close if:
  // 1. Old connection exists
  // 2. Old connection is different from new one
  // 3. Old connection is still open
  if (oldWs && oldWs !== newWebsocket && isWsConnected(oldWs)) {
    try {
      oldWs.close(1000, 'Session replaced by new connection');
    } catch {
      // Ignore close errors
    }
  }
}

/**
 * Establish a WebSocket session.
 * Handles both new sessions and reconnections.
 *
 * @returns The session ID and sends the session message to the client.
 */
export async function establishSession(
  websocket: WebSocket,
  registry: ConnectionRegistry,
  connectMessage: ClientConnectMessage
): Promise<string> {
  let sessionId: string;

  if (connectMessage.session_id && registry.hasSession(connectMessage.session_id)) {
    // Reconnection to existing session
    sessionId = connectMessage.session_id;

    // Close old connection if different
    closeOldConnectionIfExists(registry, sessionId, websocket);
  } else {
    // New session - generate UUID
    sessionId = connectMessage.session_id || randomUUID();
  }

  // Register the new connection
  registry.register(sessionId, websocket);

  // Rebind active job to the new WebSocket for resumed progress/results delivery.
  const activeJob = registry.getJob(sessionId);
  if (activeJob) {
    activeJob.websocket = websocket;
  }

  // Send session confirmation
  const sessionMessage: ServerSessionMessage = buildSessionMessage(sessionId);
  await wsSendSync(websocket, sessionMessage);

  return sessionId;
}
