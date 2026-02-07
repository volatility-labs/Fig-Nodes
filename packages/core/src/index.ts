// src/index.ts
// Main entry point for @fig-node/core

// Types
export * from './types/index';

// GraphDocument types
export {
  type GraphDocument,
  type GraphNode,
  type GraphEdge,
  type GraphGroup,
  type GraphLayout,
  createEmptyDocument,
  parseEdgeEndpoint,
  makeEdgeEndpoint,
} from './types/graph-document';

// Engine
export * from './engine/index';

// Registry
export * from './registry/index';

// Utils
export * from './utils/index';

// Tools (graph converter, validator, LLM tool types)
export * from './tools/index';

// Sockets
export * from './sockets/index';

// Base node class
export { Base } from './nodes/base/index';

// Version info
export const VERSION = '0.1.0';
