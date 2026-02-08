// WebSocket send utilities
import type { WebSocket } from '@fastify/websocket';
import type { ServerMessage } from '../types/messages.js';

// WebSocket ready states
const WS_OPEN = 1;

/**
 * Check if a WebSocket connection is open.
 */
export function isWsConnected(ws: WebSocket): boolean {
  return ws.readyState === WS_OPEN;
}

/**
 * Send a message asynchronously (fire-and-forget).
 * Swallows errors to prevent crashes in callbacks.
 */
export function wsSendAsync(ws: WebSocket, payload: ServerMessage): void {
  if (!isWsConnected(ws)) {
    return;
  }

  try {
    ws.send(JSON.stringify(payload));
  } catch {
    // Swallow errors - client may have disconnected
  }
}

/**
 * Send a message synchronously and wait for confirmation.
 * Returns a promise that resolves when the message is sent.
 */
export async function wsSendSync(ws: WebSocket, payload: ServerMessage): Promise<void> {
  if (!isWsConnected(ws)) {
    return;
  }

  return new Promise((resolve, reject) => {
    try {
      ws.send(JSON.stringify(payload), (error?: Error) => {
        if (error) {
          reject(error);
        } else {
          resolve();
        }
      });
    } catch (err) {
      reject(err);
    }
  });
}

/**
 * Send a raw JSON message.
 */
export function wsSendRaw(ws: WebSocket, data: unknown): void {
  if (!isWsConnected(ws)) {
    return;
  }

  try {
    ws.send(JSON.stringify(data));
  } catch {
    // Swallow errors
  }
}
