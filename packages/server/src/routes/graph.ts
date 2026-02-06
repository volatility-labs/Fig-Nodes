// Graph execution routes
import type { FastifyPluginAsync } from 'fastify';
import { GraphDocumentExecutor, type NodeRegistry, type GraphDocument } from '@fig-node/core';
import { getCredentialStore } from '../credentials/env-credential-store';

// Extend FastifyInstance to include our decorations
declare module 'fastify' {
  interface FastifyInstance {
    registry: NodeRegistry;
  }
}

/**
 * Helper to extract node metadata from a node class.
 * Handles both paramsMeta and params_meta naming conventions.
 */
function getNodeMetadata(NodeClass: any) {
  // Handle both paramsMeta and params_meta (legacy naming inconsistency)
  // Use Object.hasOwn to check if the subclass defines its own property,
  // avoiding inheritance of empty defaults from Base class
  const hasOwnParamsMeta = Object.hasOwn(NodeClass, 'paramsMeta') && NodeClass.paramsMeta?.length > 0;
  const hasOwnParamsMeta_ = Object.hasOwn(NodeClass, 'params_meta') && NodeClass.params_meta?.length > 0;
  const params = hasOwnParamsMeta ? NodeClass.paramsMeta : (hasOwnParamsMeta_ ? NodeClass.params_meta : []);

  const hasOwnDefaultParams = Object.hasOwn(NodeClass, 'defaultParams') && Object.keys(NodeClass.defaultParams || {}).length > 0;
  const hasOwnDefaultParams_ = Object.hasOwn(NodeClass, 'default_params') && Object.keys(NodeClass.default_params || {}).length > 0;
  const defaultParams = hasOwnDefaultParams ? NodeClass.defaultParams : (hasOwnDefaultParams_ ? NodeClass.default_params : {});

  return {
    inputs: NodeClass.inputs ?? {},
    outputs: NodeClass.outputs ?? {},
    params,
    defaultParams,
    category: NodeClass.CATEGORY ?? 'base',
    requiredKeys: NodeClass.required_keys ?? [],
    description: NodeClass.__doc ?? '',
    uiConfig: NodeClass.uiConfig ?? {},
  };
}

export const graphRoutes: FastifyPluginAsync = async (fastify) => {
  // Execute a GraphDocument
  fastify.post('/v1/graphs/execute', async (request, reply) => {
    const doc = request.body as GraphDocument;

    if (!doc || !doc.nodes || !doc.edges || doc.version !== 2) {
      return reply.status(400).send({
        error: 'Invalid GraphDocument',
        message: 'Request body must be a valid GraphDocument with version: 2',
      });
    }

    try {
      const executor = new GraphDocumentExecutor(doc, fastify.registry, getCredentialStore());
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

  // Get all nodes with full metadata
  fastify.get('/v1/nodes', async () => {
    const nodes: Record<string, ReturnType<typeof getNodeMetadata>> = {};

    for (const [name, NodeClass] of Object.entries(fastify.registry)) {
      nodes[name] = getNodeMetadata(NodeClass);
    }

    return { nodes };
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
