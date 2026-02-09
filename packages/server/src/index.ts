// @sosa/server - Fastify-based HTTP and WebSocket server
import 'dotenv/config';
import path from 'path';
import { fileURLToPath } from 'url';
import Fastify from 'fastify';
import cors from '@fastify/cors';
import websocket from '@fastify/websocket';
import type { NodeRegistry } from '@sosa/core';
import { getNodeRegistry, validateNodeDefinitions } from '@sosa/core/node-runtime';
import { graphRoutes } from './routes/graph.js';
import { graphToolRoutes } from './routes/graph-tools.js';
import { logRoutes } from './routes/logs.js';
import { websocketHandler } from './websocket/handler.js';
import { lifecycle } from './plugins/lifecycle.js';

// ESM equivalent of __dirname
const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

// Re-export types and utilities for external use
export * from './types/index.js';
export * from './queue/index.js';
export * from './session/index.js';
export * from './websocket/index.js';
export * from './plugins/index.js';

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

  // Initialize sosa core - load all nodes from directories
  const registry = await getNodeRegistry([
    path.resolve(__dirname, '../../../nodes'),         // built-in node packs
    path.resolve(__dirname, '../../../custom_nodes'),   // user extensions
  ]);

  // Validate all node definitions against the type registry
  const typeErrors = validateNodeDefinitions(registry);
  if (typeErrors.length > 0) {
    console.error('Invalid port types in node definitions:');
    typeErrors.forEach(e => console.error(`  ${e}`));
    process.exit(1);
  }

  // Decorate fastify instance with registry
  app.decorate('registry', registry);

  // Register lifecycle plugin (creates queue, connection registry, starts worker)
  await app.register(lifecycle, { registry });

  // Register REST routes
  await app.register(graphRoutes, { prefix: '/api' });
  await app.register(graphToolRoutes, { prefix: '/api/v1/graph' });
  await app.register(logRoutes, { prefix: '/api/v1' });

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
