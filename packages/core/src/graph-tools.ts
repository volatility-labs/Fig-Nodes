// src/graph-tools.ts
// LLM tool type definitions for graph manipulation

import type { Graph, GraphNode, GraphEdge } from './graph.js';
import { parseEdgeEndpoint } from './graph.js';

// ============ Tool Input Types ============

export interface AddNodeInput {
  id: string;
  type: string;
  params?: Record<string, unknown>;
  title?: string;
  position?: [number, number];
}

export interface RemoveNodeInput {
  id: string;
}

export interface ConnectInput {
  from: string;
  to: string;
}

export interface DisconnectInput {
  from: string;
  to: string;
}

export interface SetParamInput {
  node_id: string;
  key: string;
  value: unknown;
}

export interface LoadGraphInput {
  document: Graph;
}

// ============ Tool Definitions (for function-calling) ============

export interface ToolDefinition {
  name: string;
  description: string;
  parameters: Record<string, unknown>;
}

export const GRAPH_TOOLS: ToolDefinition[] = [
  {
    name: 'get_graph',
    description: 'Get the current graph document and available node types',
    parameters: {
      type: 'object',
      properties: {},
      required: [],
    },
  },
  {
    name: 'add_node',
    description: 'Add a new node to the graph',
    parameters: {
      type: 'object',
      properties: {
        id: { type: 'string', description: 'Unique node ID (e.g., "fetch_1")' },
        type: { type: 'string', description: 'Node type (e.g., "DataFetch")' },
        params: { type: 'object', description: 'Node parameters', additionalProperties: true },
        title: { type: 'string', description: 'Display title (optional)' },
        position: {
          type: 'array',
          items: { type: 'number' },
          minItems: 2,
          maxItems: 2,
          description: 'Position [x, y] on canvas',
        },
      },
      required: ['id', 'type'],
    },
  },
  {
    name: 'remove_node',
    description: 'Remove a node from the graph (also removes connected edges)',
    parameters: {
      type: 'object',
      properties: {
        id: { type: 'string', description: 'Node ID to remove' },
      },
      required: ['id'],
    },
  },
  {
    name: 'connect',
    description: 'Connect an output port of one node to an input port of another',
    parameters: {
      type: 'object',
      properties: {
        from: { type: 'string', description: 'Source endpoint "nodeId.outputName"' },
        to: { type: 'string', description: 'Target endpoint "nodeId.inputName"' },
      },
      required: ['from', 'to'],
    },
  },
  {
    name: 'disconnect',
    description: 'Remove an edge between two ports',
    parameters: {
      type: 'object',
      properties: {
        from: { type: 'string', description: 'Source endpoint "nodeId.outputName"' },
        to: { type: 'string', description: 'Target endpoint "nodeId.inputName"' },
      },
      required: ['from', 'to'],
    },
  },
  {
    name: 'set_param',
    description: 'Set a parameter value on a node',
    parameters: {
      type: 'object',
      properties: {
        node_id: { type: 'string', description: 'Node ID' },
        key: { type: 'string', description: 'Parameter name' },
        value: { description: 'New value for the parameter' },
      },
      required: ['node_id', 'key', 'value'],
    },
  },
  {
    name: 'validate',
    description: 'Validate the current graph document',
    parameters: {
      type: 'object',
      properties: {},
      required: [],
    },
  },
  {
    name: 'load',
    description: 'Replace the entire graph with a new document',
    parameters: {
      type: 'object',
      properties: {
        document: { type: 'object', description: 'A full Graph object' },
      },
      required: ['document'],
    },
  },
];

// ============ Mutation Helpers ============

export function applyAddNode(doc: Graph, input: AddNodeInput): Graph {
  if (input.id in doc.nodes) {
    throw new Error(`Node "${input.id}" already exists`);
  }
  const node: GraphNode = {
    type: input.type,
    params: input.params ?? {},
    ...(input.title ? { title: input.title } : {}),
    ...(input.position ? { position: input.position } : {}),
  };
  return {
    ...doc,
    nodes: { ...doc.nodes, [input.id]: node },
  };
}

export function applyRemoveNode(doc: Graph, input: RemoveNodeInput): Graph {
  if (!(input.id in doc.nodes)) {
    throw new Error(`Node "${input.id}" does not exist`);
  }
  const { [input.id]: _, ...remainingNodes } = doc.nodes;
  const edges = doc.edges.filter((e) => {
    const fromNode = parseEdgeEndpoint(e.from).nodeId;
    const toNode = parseEdgeEndpoint(e.to).nodeId;
    return fromNode !== input.id && toNode !== input.id;
  });
  return { ...doc, nodes: remainingNodes, edges };
}

export function applyConnect(doc: Graph, input: ConnectInput): Graph {
  const exists = doc.edges.some((e) => e.from === input.from && e.to === input.to);
  if (exists) return doc;
  const edge: GraphEdge = { from: input.from, to: input.to };
  return { ...doc, edges: [...doc.edges, edge] };
}

export function applyDisconnect(doc: Graph, input: DisconnectInput): Graph {
  const edges = doc.edges.filter(
    (e) => !(e.from === input.from && e.to === input.to),
  );
  return { ...doc, edges };
}

export function applySetParam(doc: Graph, input: SetParamInput): Graph {
  const node = doc.nodes[input.node_id];
  if (!node) {
    throw new Error(`Node "${input.node_id}" does not exist`);
  }
  return {
    ...doc,
    nodes: {
      ...doc.nodes,
      [input.node_id]: {
        ...node,
        params: { ...node.params, [input.key]: input.value },
      },
    },
  };
}
