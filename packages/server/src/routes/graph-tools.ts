// routes/graph-tools.ts
// LLM Tool API endpoints for graph manipulation
// These endpoints allow LLMs to read and modify the graph via function-calling.

import type { FastifyPluginAsync } from 'fastify';
import {
  type Graph,
  type NodeRegistry,
  validateGraph,
  GRAPH_TOOLS,
  applyAddNode,
  applyRemoveNode,
  applyConnect,
  applyDisconnect,
  applySetParam,
  createEmptyDocument,
  hasCycles,
  GraphExecutor,
} from '@sosa/core';
import { getCredentialStore } from '../credentials/env-credential-store.js';
import { getNodeMetadata } from './node-metadata-helper.js';

// In-memory graph document state (one graph per server for now)
let currentDocument: Graph = createEmptyDocument();

// Listeners for graph updates (WebSocket push)
type GraphUpdateListener = (doc: Graph) => void;
const listeners = new Set<GraphUpdateListener>();

export function setCurrentDocument(doc: Graph): void {
  currentDocument = doc;
  notifyListeners();
}

export function getCurrentDocument(): Graph {
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

      const validation = validateGraph(newDoc, fastify.registry as NodeRegistry);
      if (!validation.valid) {
        return reply.status(400).send({
          error: 'Connection is incompatible with socket types',
          details: validation.errors,
        });
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
    const result = validateGraph(currentDocument, fastify.registry as NodeRegistry);
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

    const result = validateGraph(body.document, fastify.registry as NodeRegistry);
    if (!result.valid) {
      return reply.status(400).send({
        error: 'Invalid graph document',
        details: result.errors,
      });
    }

    if (hasCycles(body.document as Graph)) {
      return reply.status(400).send({ error: 'Graph contains cycles' });
    }

    currentDocument = body.document as Graph;
    notifyListeners();
    return { ok: true, document: currentDocument };
  });

  // POST /api/v1/graph/tools/execute — execute the current graph document directly
  fastify.post('/tools/execute', async (_request, reply) => {
    const result = validateGraph(currentDocument, fastify.registry as NodeRegistry);
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
      const executor = await GraphExecutor.create(
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
