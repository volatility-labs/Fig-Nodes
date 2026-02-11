// src/index.ts
// Main entry point for @sosa/core (browser-safe)
// Node-only exports (node registry, dynamic discovery) live in ./node-runtime.ts

// Types (execution, credentials, ports, port types, node-ui, messages, errors)
export * from './types.js';

// Graph types, mutations (pure functions), and validation
export {
  type Graph,
  type GraphNode,
  type GraphEdge,
  createEmptyDocument,
  parseEdgeEndpoint,
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
  validateGraph,
  hasCycles,
  type ValidationError,
  type ValidationResult,
} from './graph.js';

// Engine
export { GraphExecutor } from './engine.js';

// Sockets
export {
  getOrCreateSocket,
  getSocketKey,
  areSocketKeysCompatible,
  areSocketTypesCompatible,
} from './sockets.js';

// Node base class
export { Node, type NodeDefinition } from './node.js';
