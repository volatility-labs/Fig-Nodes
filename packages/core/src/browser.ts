// src/browser.ts
// Browser-safe entry point for @fig-node/core
// Excludes registry (uses fs/path/url) and engine (server-only)

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

// Tools (graph converter, validator, LLM tool types)
export * from './tools/index';

// Utils
export * from './utils/index';

// Base node class
export { Base } from './nodes/base/index';

// Version info
export const VERSION = '0.1.0';
