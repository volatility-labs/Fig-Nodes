// Lifecycle plugin for startup/shutdown hooks
import type { FastifyPluginAsync } from 'fastify';
import fp from 'fastify-plugin';
import type { NodeRegistry } from '@fig-node/core';
import { ExecutionQueue } from '../queue/execution-queue';
import { executionWorker } from '../queue/worker';
import { ConnectionRegistry } from '../session/connection-registry';

declare module 'fastify' {
  interface FastifyInstance {
    executionQueue: ExecutionQueue;
    connectionRegistry: ConnectionRegistry;
  }
}

export interface LifecyclePluginOptions {
  registry: NodeRegistry;
}

/**
 * Lifecycle plugin - initializes queue, connection registry, and execution worker.
 * Handles graceful shutdown.
 */
const lifecyclePlugin: FastifyPluginAsync<LifecyclePluginOptions> = async (fastify, options) => {
  // Create instances
  const executionQueue = new ExecutionQueue();
  const connectionRegistry = new ConnectionRegistry();

  // Decorate fastify with instances
  fastify.decorate('executionQueue', executionQueue);
  fastify.decorate('connectionRegistry', connectionRegistry);

  // Worker promise - will be started on ready
  let workerPromise: Promise<void> | null = null;

  // Start worker when server is ready
  fastify.addHook('onReady', async () => {
    fastify.log.info('Starting execution worker');
    workerPromise = executionWorker(executionQueue, options.registry, fastify.log);

    // Don't await - worker runs in background
    workerPromise.catch((error) => {
      fastify.log.error({ error }, 'Execution worker error');
    });
  });

  // Graceful shutdown
  fastify.addHook('onClose', async () => {
    fastify.log.info('Shutting down execution queue');

    // Shutdown queue (cancels all jobs and wakes worker)
    executionQueue.shutdown();

    // Wait for worker to finish (with timeout)
    if (workerPromise) {
      const timeoutPromise = new Promise<void>((resolve) => {
        setTimeout(() => {
          fastify.log.warn('Worker shutdown timeout');
          resolve();
        }, 5000);
      });

      await Promise.race([workerPromise, timeoutPromise]);
    }

    fastify.log.info('Execution queue shutdown complete');
  });
};

export const lifecycle = fp(lifecyclePlugin, {
  name: 'fig-node-lifecycle',
  fastify: '5.x',
});
