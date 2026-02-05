// @fig-node/server - Fastify-based HTTP and WebSocket server
import 'dotenv/config';
import Fastify from 'fastify';
import cors from '@fastify/cors';
import websocket from '@fastify/websocket';
import { getNodeRegistry, type NodeRegistry } from '@fig-node/core';
import { graphRoutes } from './routes/graph';
import { apiKeyRoutes } from './routes/api-keys';
import { websocketHandler } from './websocket/handler';
import { lifecycle } from './plugins/lifecycle';

// Re-export types and utilities for external use
export * from './types';
export * from './queue';
export * from './session';
export * from './websocket';
export * from './plugins';

const PORT = parseInt(process.env.PORT || '8000', 10);
const HOST = process.env.HOST || '0.0.0.0';

declare module 'fastify' {
  interface FastifyInstance {
    registry: NodeRegistry;
  }
}

async function createServer() {
  const app = Fastify({ logger: true });

  // Register plugins
  await app.register(cors, {
    origin: true,
    credentials: true,
  });
  await app.register(websocket);

  // Initialize fig-node core - load all nodes from directories
  const registry = await getNodeRegistry();

  // Decorate fastify instance with registry
  app.decorate('registry', registry);

  // Register lifecycle plugin (creates queue, connection registry, starts worker)
  await app.register(lifecycle, { registry });

  // Register REST routes
  await app.register(graphRoutes, { prefix: '/api' });
  await app.register(apiKeyRoutes, { prefix: '/api' });

  // Register WebSocket handler (now at /execute to match legacy)
  await app.register(websocketHandler);

  // Health check
  app.get('/health', async () => ({ status: 'ok' }));

  return app;
}

async function main() {
  const app = await createServer();

  try {
    await app.listen({ port: PORT, host: HOST });
    console.log(`Server running at http://${HOST}:${PORT}`);
  } catch (err) {
    app.log.error(err);
    process.exit(1);
  }
}

main();

export { createServer };
