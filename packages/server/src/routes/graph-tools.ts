// routes/graph-tools.ts
// LLM Tool API endpoints for graph manipulation
// These endpoints allow LLMs to read and modify the graph via function-calling.

import type { FastifyPluginAsync } from 'fastify';
import {
  type GraphDocument,
  type NodeRegistry,
  validateGraphDocument,
  GRAPH_TOOLS,
  applyAddNode,
  applyRemoveNode,
  applyConnect,
  applyDisconnect,
  applySetParam,
  createEmptyDocument,
  hasCycles,
  GraphDocumentExecutor,
} from '@fig-node/core';
import { getCredentialStore } from '../credentials/env-credential-store';

// In-memory graph document state (one graph per server for now)
let currentDocument: GraphDocument = createEmptyDocument();

// Listeners for graph updates (WebSocket push)
type GraphUpdateListener = (doc: GraphDocument) => void;
const listeners = new Set<GraphUpdateListener>();

export function setCurrentDocument(doc: GraphDocument): void {
  currentDocument = doc;
  notifyListeners();
}

export function getCurrentDocument(): GraphDocument {
  return currentDocument;
}

export function onGraphUpdate(listener: GraphUpdateListener): () => void {
  listeners.add(listener);
  return () => { listeners.delete(listener); };
}

function notifyListeners(): void {
  for (const listener of listeners) {
    try { listener(currentDocument); } catch { /* ignore */ }
  }
}

function getNodeMetadata(NodeClass: unknown): Record<string, unknown> {
  const cls = NodeClass as Record<string, unknown>;
  const hasOwnParamsMeta = Object.hasOwn(cls, 'paramsMeta') && (cls.paramsMeta as unknown[])?.length > 0;
  const hasOwnParamsMeta_ = Object.hasOwn(cls, 'params_meta') && (cls.params_meta as unknown[])?.length > 0;
  const params = hasOwnParamsMeta ? cls.paramsMeta : (hasOwnParamsMeta_ ? cls.params_meta : []);

  const hasOwnDefaultParams = Object.hasOwn(cls, 'defaultParams') && Object.keys((cls.defaultParams as Record<string, unknown>) || {}).length > 0;
  const hasOwnDefaultParams_ = Object.hasOwn(cls, 'default_params') && Object.keys((cls.default_params as Record<string, unknown>) || {}).length > 0;
  const defaultParams = hasOwnDefaultParams ? cls.defaultParams : (hasOwnDefaultParams_ ? cls.default_params : {});

  return {
    inputs: cls.inputs ?? {},
    outputs: cls.outputs ?? {},
    params,
    defaultParams,
    category: cls.CATEGORY ?? 'base',
    requiredKeys: cls.required_keys ?? [],
    description: cls.__doc ?? '',
    uiConfig: cls.uiConfig ?? {},
  };
}

export const graphToolRoutes: FastifyPluginAsync = async (fastify) => {
  // GET /api/v1/graph/tools/get_graph — return current graph + available node types
  fastify.get('/tools/get_graph', async () => {
    const nodeTypes: Record<string, unknown> = {};
    for (const [name, NodeClass] of Object.entries(fastify.registry)) {
      nodeTypes[name] = getNodeMetadata(NodeClass);
    }

    return {
      document: currentDocument,
      nodeTypes,
      tools: GRAPH_TOOLS,
    };
  });

  // POST /api/v1/graph/tools/add_node
  fastify.post('/tools/add_node', async (request, reply) => {
    const body = request.body as { id: string; type: string; params?: Record<string, unknown>; title?: string; position?: [number, number] };

    if (!body.id || !body.type) {
      return reply.status(400).send({ error: 'id and type are required' });
    }

    // Validate node type exists
    if (!(body.type in fastify.registry)) {
      return reply.status(400).send({ error: `Unknown node type: ${body.type}` });
    }

    try {
      currentDocument = applyAddNode(currentDocument, body);
      notifyListeners();
      return { ok: true, document: currentDocument };
    } catch (e) {
      return reply.status(400).send({ error: (e as Error).message });
    }
  });

  // POST /api/v1/graph/tools/remove_node
  fastify.post('/tools/remove_node', async (request, reply) => {
    const body = request.body as { id: string };

    if (!body.id) {
      return reply.status(400).send({ error: 'id is required' });
    }

    try {
      currentDocument = applyRemoveNode(currentDocument, body);
      notifyListeners();
      return { ok: true, document: currentDocument };
    } catch (e) {
      return reply.status(400).send({ error: (e as Error).message });
    }
  });

  // POST /api/v1/graph/tools/connect
  fastify.post('/tools/connect', async (request, reply) => {
    const body = request.body as { from: string; to: string };

    if (!body.from || !body.to) {
      return reply.status(400).send({ error: 'from and to are required' });
    }

    try {
      const newDoc = applyConnect(currentDocument, body);

      // Check for cycles
      if (hasCycles(newDoc)) {
        return reply.status(400).send({ error: 'Connection would create a cycle' });
      }

      currentDocument = newDoc;
      notifyListeners();
      return { ok: true, document: currentDocument };
    } catch (e) {
      return reply.status(400).send({ error: (e as Error).message });
    }
  });

  // POST /api/v1/graph/tools/disconnect
  fastify.post('/tools/disconnect', async (request, reply) => {
    const body = request.body as { from: string; to: string };

    if (!body.from || !body.to) {
      return reply.status(400).send({ error: 'from and to are required' });
    }

    try {
      currentDocument = applyDisconnect(currentDocument, body);
      notifyListeners();
      return { ok: true, document: currentDocument };
    } catch (e) {
      return reply.status(400).send({ error: (e as Error).message });
    }
  });

  // POST /api/v1/graph/tools/set_param
  fastify.post('/tools/set_param', async (request, reply) => {
    const body = request.body as { node_id: string; key: string; value: unknown };

    if (!body.node_id || !body.key) {
      return reply.status(400).send({ error: 'node_id and key are required' });
    }

    try {
      currentDocument = applySetParam(currentDocument, body);
      notifyListeners();
      return { ok: true, document: currentDocument };
    } catch (e) {
      return reply.status(400).send({ error: (e as Error).message });
    }
  });

  // POST /api/v1/graph/tools/validate
  fastify.post('/tools/validate', async () => {
    const result = validateGraphDocument(currentDocument, fastify.registry as NodeRegistry);
    const cycles = hasCycles(currentDocument);

    return {
      valid: result.valid && !cycles,
      errors: result.errors,
      hasCycles: cycles,
    };
  });

  // POST /api/v1/graph/tools/load
  fastify.post('/tools/load', async (request, reply) => {
    const body = request.body as { document: unknown };

    if (!body.document) {
      return reply.status(400).send({ error: 'document is required' });
    }

    const result = validateGraphDocument(body.document);
    if (!result.valid) {
      return reply.status(400).send({
        error: 'Invalid graph document',
        details: result.errors,
      });
    }

    currentDocument = body.document as GraphDocument;
    notifyListeners();
    return { ok: true, document: currentDocument };
  });

  // POST /api/v1/graph/tools/execute — execute the current graph document directly
  fastify.post('/tools/execute', async (_request, reply) => {
    const result = validateGraphDocument(currentDocument, fastify.registry as NodeRegistry);
    if (!result.valid) {
      return reply.status(400).send({
        error: 'Graph validation failed',
        details: result.errors,
      });
    }

    if (hasCycles(currentDocument)) {
      return reply.status(400).send({ error: 'Graph contains cycles' });
    }

    try {
      const executor = new GraphDocumentExecutor(
        currentDocument,
        fastify.registry as NodeRegistry,
        getCredentialStore(),
      );
      const results = await executor.execute();
      return { ok: true, results };
    } catch (e) {
      return reply.status(500).send({ error: (e as Error).message });
    }
  });

  // GET /api/v1/graph/tools/schema — return JSON Schema for function-calling
  fastify.get('/tools/schema', async () => {
    return { tools: GRAPH_TOOLS };
  });
};
