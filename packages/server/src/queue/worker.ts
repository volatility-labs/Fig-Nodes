// Execution worker - processes jobs from the queue
import type { FastifyBaseLogger } from 'fastify';
import {
  GraphExecutor,
  type NodeRegistry,
  type ProgressEvent,
  NodeCategory,
  serializeForApi,
} from '@fig-node/core';
import type { ExecutionQueue } from './execution-queue.js';
import type { ExecutionJob } from '../types/job.js';
import { JobState } from '../types/job.js';
import {
  ExecutionState,
  buildStatusMessage,
  buildProgressMessage,
  buildDataMessage,
  buildErrorMessage,
  buildStoppedMessage,
} from '../types/messages.js';
import { wsSendAsync, wsSendSync, isWsConnected } from '../websocket/send-utils.js';
import { getCredentialStore } from '../credentials/env-credential-store.js';

const DISCONNECT_POLL_INTERVAL_MS = 500;
const EXECUTION_TIMEOUT_MS = 5 * 60 * 1000; // 5 minutes

/**
 * Monitor for cancellation or disconnection.
 * Returns the reason: 'user' (cancel), 'disconnect', or 'completed'.
 */
type StringExecutionResults = Record<string, Record<string, unknown>>;

async function monitorCancel(
  job: ExecutionJob,
  executionPromise: Promise<StringExecutionResults>
): Promise<{ reason: 'user' | 'disconnect' | 'completed'; results?: StringExecutionResults }> {
  // Create abort promise
  const cancelPromise = new Promise<{ reason: 'user' }>((resolve) => {
    job.cancelController.signal.addEventListener('abort', () => resolve({ reason: 'user' }), {
      once: true,
    });
  });

  // Create disconnect polling promise
  const disconnectPromise = new Promise<{ reason: 'disconnect' }>((resolve) => {
    const checkDisconnect = () => {
      if (!isWsConnected(job.websocket)) {
        resolve({ reason: 'disconnect' });
      } else if (job.state === JobState.RUNNING) {
        setTimeout(checkDisconnect, DISCONNECT_POLL_INTERVAL_MS);
      }
    };
    checkDisconnect();
  });

  // Create completion promise
  const completionPromise = executionPromise.then(
    (results) => ({ reason: 'completed' as const, results })
  );

  // Race all three
  return Promise.race([cancelPromise, disconnectPromise, completionPromise]);
}

/**
 * Create progress callback that sends updates to the client.
 * Guarded to handle disconnections gracefully.
 */
function createProgressCallback(
  job: ExecutionJob,
): (event: ProgressEvent) => void {
  return (event: ProgressEvent) => {
    if (!isWsConnected(job.websocket)) {
      return;
    }

    const message = buildProgressMessage(event.node_id, event.state, job.id, {
      progress: event.progress,
      text: event.text,
      meta: event.meta,
    });

    wsSendAsync(job.websocket, message);
  };
}

/**
 * Create result callback for immediate emission of IO node results.
 * IO category nodes emit their results immediately rather than waiting for batch completion.
 */
function createResultCallback(
  job: ExecutionJob,
  nodeRegistry: NodeRegistry,
  emittedNodeIds: Set<string>,
): (nodeId: string, output: Record<string, unknown>) => void {
  return (nodeId: string, output: Record<string, unknown>) => {
    if (!isWsConnected(job.websocket)) {
      return;
    }

    // Look up node type from the document
    const node = job.graphData.nodes[nodeId];
    if (!node) return;

    const NodeClass = nodeRegistry[node.type] as { definition?: { category?: string } } | undefined;
    const category = NodeClass?.definition?.category ?? 'base';

    // Only emit immediately for IO nodes
    if (category === NodeCategory.IO || category === 'io') {
      emittedNodeIds.add(nodeId);

      const serializedOutput = serializeForApi(output) as Record<string, unknown>;
      const message = buildDataMessage({ [nodeId]: serializedOutput }, job.id);
      wsSendAsync(job.websocket, message);
    }
  };
}

/**
 * Execution worker - continuously processes jobs from the queue.
 * This is the main loop that runs in the background.
 */
export async function executionWorker(
  queue: ExecutionQueue,
  nodeRegistry: NodeRegistry,
  logger: FastifyBaseLogger
): Promise<void> {
  logger.info('Execution worker started');

  while (!queue.isShuttingDown()) {
    let job: ExecutionJob | null = null;

    try {
      // Wait for next job
      job = await queue.getNext();

      if (!job) {
        // Queue is shutting down
        break;
      }

      logger.info({ jobId: job.id }, 'Starting job execution');

      // Check if client is still connected
      if (!isWsConnected(job.websocket)) {
        logger.info({ jobId: job.id }, 'Client disconnected before execution started');
        queue.markDone(job);
        continue;
      }

      // Send running status
      await wsSendSync(
        job.websocket,
        buildStatusMessage(ExecutionState.RUNNING, 'Execution started', job.id)
      );

      // Track which nodes have already emitted results (IO nodes)
      const emittedNodeIds = new Set<string>();

      // Create executor from Graph directly
      const executor = new GraphExecutor(job.graphData, nodeRegistry, getCredentialStore());

      // Set up callbacks
      executor.setProgressCallback(createProgressCallback(job));
      executor.setResultCallback(createResultCallback(job, nodeRegistry, emittedNodeIds));

      // Start execution with timeout
      const executionPromise = executor.execute();
      const timeoutPromise = new Promise<never>((_, reject) =>
        setTimeout(() => reject(new Error(`Execution timed out after ${EXECUTION_TIMEOUT_MS / 1000}s`)), EXECUTION_TIMEOUT_MS)
      );
      const timedExecution = Promise.race([executionPromise, timeoutPromise]);

      // Monitor for cancellation/disconnection
      const outcome = await monitorCancel(job, timedExecution);

      if (outcome.reason === 'user') {
        logger.info({ jobId: job.id }, 'Job cancelled by user');
        executor.forceStop('user');

        if (isWsConnected(job.websocket)) {
          await wsSendSync(
            job.websocket,
            buildStoppedMessage('Execution cancelled by user', job.id)
          );
        }
      } else if (outcome.reason === 'disconnect') {
        logger.info({ jobId: job.id }, 'Job cancelled due to disconnect');
        executor.forceStop('disconnect');
        // No message to send - client is gone
      } else {
        // Execution completed - get results
        const results = outcome.results!;

        if (!isWsConnected(job.websocket)) {
          logger.info({ jobId: job.id }, 'Client disconnected after execution');
          queue.markDone(job);
          continue;
        }

        // Filter out results that were already emitted (IO nodes)
        const finalResults: Record<string, Record<string, unknown>> = {};
        for (const [nodeId, outputs] of Object.entries(results)) {
          if (!emittedNodeIds.has(nodeId)) {
            finalResults[nodeId] = serializeForApi(outputs) as Record<string, unknown>;
          }
        }

        // Send final results if any
        if (Object.keys(finalResults).length > 0) {
          await wsSendSync(job.websocket, buildDataMessage(finalResults, job.id));
        }

        // Send finished status
        await wsSendSync(
          job.websocket,
          buildStatusMessage(ExecutionState.FINISHED, 'Execution completed', job.id)
        );
      }
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : 'Unknown error';
      logger.error({ jobId: job?.id, error: errorMessage }, 'Job execution error');

      if (job && isWsConnected(job.websocket)) {
        try {
          await wsSendSync(
            job.websocket,
            buildErrorMessage(errorMessage, 'EXECUTION_ERROR', undefined, job.id)
          );
          await wsSendSync(
            job.websocket,
            buildStatusMessage(ExecutionState.ERROR, errorMessage, job.id)
          );
        } catch {
          // Ignore send errors
        }
      }
    } finally {
      if (job) {
        queue.markDone(job);
        logger.info({ jobId: job.id }, 'Job completed');
      }
    }
  }

  logger.info('Execution worker stopped');
}
