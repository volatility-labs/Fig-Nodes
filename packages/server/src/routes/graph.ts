// Graph execution routes
import type { FastifyPluginAsync } from 'fastify';
import {
  GraphExecutor,
  type NodeRegistry,
  type Graph,
  validateGraph,
  hasCycles,
} from '@fig-node/core';
import { getCredentialStore } from '../credentials/env-credential-store.js';
import { getNodeMetadata } from './node-metadata-helper.js';

// Extend FastifyInstance to include our decorations
declare module 'fastify' {
  interface FastifyInstance {
    registry: NodeRegistry;
  }
}

export const graphRoutes: FastifyPluginAsync = async (fastify) => {
  // Execute a Graph
  fastify.post('/v1/graphs/execute', async (request, reply) => {
    const doc = request.body as Graph;

    const validation = validateGraph(doc, fastify.registry);
    if (!validation.valid) {
      return reply.status(400).send({
        error: 'Invalid Graph',
        details: validation.errors,
      });
    }

    if (hasCycles(doc)) {
      return reply.status(400).send({
        error: 'Invalid Graph',
        message: 'Graph contains cycles',
      });
    }

    try {
      const executor = new GraphExecutor(doc, fastify.registry, getCredentialStore());
      const result = await executor.execute();
      return result;
    } catch (error) {
      fastify.log.error(error);
      return reply.status(500).send({
        error: 'Graph execution failed',
        message: error instanceof Error ? error.message : 'Unknown error',
      });
    }
  });

  // Get all nodes with full metadata (cached since definitions are static)
  let cachedNodes: Record<string, ReturnType<typeof getNodeMetadata>> | null = null;

  fastify.get('/v1/nodes', async () => {
    if (!cachedNodes) {
      cachedNodes = {};
      for (const [name, NodeClass] of Object.entries(fastify.registry)) {
        cachedNodes[name] = getNodeMetadata(NodeClass);
      }
    }

    return { nodes: cachedNodes };
  });

  // Get individual node schema
  fastify.get('/nodes/:nodeType', async (request, reply) => {
    const { nodeType } = request.params as { nodeType: string };
    const NodeClass = fastify.registry[nodeType];

    if (!NodeClass) {
      reply.status(404).send({ error: `Node type not found: ${nodeType}` });
      return;
    }

    return {
      nodeType,
      ...getNodeMetadata(NodeClass),
    };
  });
};
