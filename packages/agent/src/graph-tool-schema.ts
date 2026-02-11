// src/graph-tool-schema.ts
// LLM tool type definitions for graph manipulation
// These define the function-calling interface for AI agents to build/modify graphs.

import type { Graph } from '@sosa/core';

// Re-export mutation input types from core (single source of truth)
export type {
  AddNodeInput,
  RemoveNodeInput,
  ConnectInput,
  DisconnectInput,
  SetParamInput,
} from '@sosa/core';

// ============ Agent-only Input Types ============

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
