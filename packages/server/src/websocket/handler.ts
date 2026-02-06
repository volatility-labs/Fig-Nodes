// WebSocket handler for real-time graph execution - Full protocol implementation
import type { FastifyPluginAsync } from 'fastify';
import type { WebSocket } from '@fastify/websocket';
import {
  type NodeRegistry,
  type SerialisableGraph,
  getRequiredKeysForGraph,
} from '@fig-node/core';
import { getCredentialStore } from '../credentials/env-credential-store';
import type { ExecutionQueue } from '../queue/execution-queue';
import type { ConnectionRegistry } from '../session/connection-registry';
import { establishSession } from '../session/connection-registry';
import type { ExecutionJob } from '../types/job';
import { JobState } from '../types/job';
import {
  parseClientMessageOrdered,
  type ClientConnectMessage,
  type ClientGraphMessage,
  type ClientStopMessage,
  buildStatusMessage,
  buildErrorMessage,
  buildStoppedMessage,
  buildPongMessage,
  ExecutionState,
} from '../types/messages';
import { wsSendSync, wsSendAsync, isWsConnected } from './send-utils';

declare module 'fastify' {
  interface FastifyInstance {
    registry: NodeRegistry;
    executionQueue: ExecutionQueue;
    connectionRegistry: ConnectionRegistry;
  }
}

/**
 * Handle graph execution message.
 * Validates API keys and enqueues the job.
 */
async function handleGraphMessage(
  websocket: WebSocket,
  message: ClientGraphMessage,
  sessionId: string,
  fastify: {
    registry: NodeRegistry;
    executionQueue: ExecutionQueue;
    connectionRegistry: ConnectionRegistry;
    log: { info: (msg: unknown, ...args: unknown[]) => void };
  }
): Promise<ExecutionJob | null> {
  const graphData = message.graph_data as SerialisableGraph;

  // Validate API keys
  const credentialStore = getCredentialStore();
  const requiredKeys = getRequiredKeysForGraph(graphData, fastify.registry);
  const missingKeys: string[] = [];

  for (const key of requiredKeys) {
    if (!credentialStore.get(key)) {
      missingKeys.push(key);
    }
  }

  if (missingKeys.length > 0) {
    await wsSendSync(
      websocket,
      buildErrorMessage(
        `Missing required API keys: ${missingKeys.join(', ')}`,
        'MISSING_API_KEYS',
        missingKeys
      )
    );
    return null;
  }

  // Enqueue the job
  const job = fastify.executionQueue.enqueue(websocket, graphData);

  // Track job in registry
  fastify.connectionRegistry.setJob(sessionId, job);

  fastify.log.info({ jobId: job.id, sessionId }, 'Job enqueued');

  // Send queued status
  await wsSendSync(
    websocket,
    buildStatusMessage(ExecutionState.QUEUED, 'Job queued for execution', job.id)
  );

  return job;
}

/**
 * Handle stop message.
 * Cancels the current job if one exists.
 */
async function handleStopMessage(
  websocket: WebSocket,
  _message: ClientStopMessage,
  sessionId: string,
  fastify: {
    executionQueue: ExecutionQueue;
    connectionRegistry: ConnectionRegistry;
    log: { info: (msg: unknown, ...args: unknown[]) => void };
  }
): Promise<void> {
  const job = fastify.connectionRegistry.getJob(sessionId);

  if (!job) {
    // No active job
    await wsSendSync(websocket, buildStoppedMessage('No active job to stop'));
    return;
  }

  if (job.state === JobState.CANCELLED || job.state === JobState.DONE) {
    // Already cancelling/done - wait for completion and send idempotent response
    await job.done.promise;
    await wsSendSync(websocket, buildStoppedMessage('Job already stopped', job.id));
    return;
  }

  fastify.log.info({ jobId: job.id, sessionId }, 'Stop requested');

  // Cancel the job
  fastify.executionQueue.cancelJob(job);

  // Wait for job to finish
  await job.done.promise;

  // Clear job from registry
  fastify.connectionRegistry.setJob(sessionId, null);

  // Send confirmation (the worker may have already sent a stopped message)
  if (isWsConnected(websocket)) {
    await wsSendSync(websocket, buildStoppedMessage('Job stopped', job.id));
  }
}

/**
 * WebSocket handler plugin - registers the /execute endpoint.
 */
export const websocketHandler: FastifyPluginAsync = async (fastify) => {
  fastify.get('/execute', { websocket: true }, async (socket: WebSocket) => {
    fastify.log.info('WebSocket client connected');

    let sessionId: string | null = null;

    try {
      // ============ Phase 1: Wait for connect message ============
      const connectPromise = new Promise<ClientConnectMessage>((resolve, reject) => {
        const timeout = setTimeout(() => {
          reject(new Error('Connect timeout - no connect message received'));
        }, 30000); // 30 second timeout

        const messageHandler = (rawMessage: Buffer) => {
          try {
            const data = JSON.parse(rawMessage.toString());
            const message = parseClientMessageOrdered(data);

            if (message && message.type === 'connect') {
              clearTimeout(timeout);
              socket.off('message', messageHandler);
              resolve(message);
            } else {
              // First message must be connect
              wsSendAsync(
                socket,
                buildErrorMessage('First message must be a connect message', 'VALIDATION_ERROR')
              );
            }
          } catch {
            wsSendAsync(socket, buildErrorMessage('Invalid JSON', 'VALIDATION_ERROR'));
          }
        };

        socket.on('message', messageHandler);
      });

      const connectMessage = await connectPromise;

      // Establish session
      sessionId = await establishSession(socket, fastify.connectionRegistry, connectMessage);
      fastify.log.info({ sessionId }, 'Session established');

      // ============ Phase 2: Message loop ============
      socket.on('message', async (rawMessage: Buffer) => {
        try {
          const data = JSON.parse(rawMessage.toString());
          const message = parseClientMessageOrdered(data);

          if (!message) {
            wsSendAsync(socket, buildErrorMessage('Invalid message format', 'VALIDATION_ERROR'));
            return;
          }

          switch (message.type) {
            case 'connect':
              // Re-connect message (session refresh)
              wsSendAsync(socket, buildErrorMessage('Already connected', 'VALIDATION_ERROR'));
              break;

            case 'graph':
              await handleGraphMessage(socket, message, sessionId!, {
                registry: fastify.registry,
                executionQueue: fastify.executionQueue,
                connectionRegistry: fastify.connectionRegistry,
                log: fastify.log,
              });
              break;

            case 'stop':
              await handleStopMessage(socket, message, sessionId!, {
                executionQueue: fastify.executionQueue,
                connectionRegistry: fastify.connectionRegistry,
                log: fastify.log,
              });
              break;

            case 'ping':
              wsSendAsync(socket, buildPongMessage());
              break;

            default:
              wsSendAsync(
                socket,
                buildErrorMessage(`Unknown message type: ${(message as { type: string }).type}`, 'VALIDATION_ERROR')
              );
          }
        } catch (error) {
          fastify.log.error({ error, sessionId }, 'Message handling error');
          wsSendAsync(
            socket,
            buildErrorMessage(
              error instanceof Error ? error.message : 'Unknown error',
              'EXECUTION_ERROR'
            )
          );
        }
      });

      // ============ Phase 3: Handle disconnect ============
      socket.on('close', () => {
        fastify.log.info({ sessionId }, 'WebSocket client disconnected');

        if (sessionId) {
          // Cancel any running job
          const job = fastify.connectionRegistry.getJob(sessionId);
          if (job && job.state !== JobState.DONE && job.state !== JobState.CANCELLED) {
            fastify.executionQueue.cancelJob(job);
          }

          // Unregister session
          fastify.connectionRegistry.unregister(sessionId, socket);
        }
      });

      socket.on('error', (error: Error) => {
        fastify.log.error({ error, sessionId }, 'WebSocket error');
      });
    } catch (error) {
      fastify.log.error({ error }, 'WebSocket connection error');

      // Try to send error message
      if (isWsConnected(socket)) {
        wsSendAsync(
          socket,
          buildErrorMessage(
            error instanceof Error ? error.message : 'Connection error',
            'EXECUTION_ERROR'
          )
        );
      }

      // Clean up
      if (sessionId) {
        fastify.connectionRegistry.unregister(sessionId, socket);
      }

      socket.close();
    }
  });
};
