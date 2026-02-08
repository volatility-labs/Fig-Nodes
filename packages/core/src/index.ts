// src/index.ts
// Main entry point for @sosa/core (browser-safe)
// Node-only exports (node registry, dynamic discovery) live in ./node-runtime.ts

// Types (execution, credentials, ports, node-ui, errors)
export * from './types.js';

// WebSocket message types (shared client ↔ server contract)
export * from './messages.js';

// Type registry
export {
  TYPE_ALIASES,
  registerType,
  isRegisteredType,
  getRegisteredTypes,
  port,
  execPort,
} from './type-registry.js';

// Port helpers
export { EXEC_SOCKET_TYPE, isExecPort } from './ports.js';

// Graph types
export {
  type Graph,
  type GraphNode,
  type GraphEdge,
  type GraphGroup,
  type GraphLayout,
  createEmptyDocument,
  parseEdgeEndpoint,
  makeEdgeEndpoint,
} from './graph.js';

// Engine
export { GraphExecutor } from './engine.js';

// Tools (graph mutation, validator, LLM tool types)
export {
  validateGraph,
  validateEdgeTypes,
  hasCycles,
  type ValidationError,
  type ValidationResult,
} from './validator.js';
export {
  GRAPH_TOOLS,
  applyAddNode,
  applyRemoveNode,
  applyConnect,
  applyDisconnect,
  applySetParam,
  type AddNodeInput,
  type RemoveNodeInput,
  type ConnectInput,
  type DisconnectInput,
  type SetParamInput,
  type LoadGraphInput,
  type ToolDefinition,
} from './graph-tools.js';

// Sockets
export {
  getOrCreateSocket,
  anySocket,
  getSocketKey,
  areSocketKeysCompatible,
  areSocketTypesCompatible,
} from './sockets.js';

// Node base class
export { Node, type NodeDefinition } from './node.js';

// Version info
export const VERSION = '0.1.0';
