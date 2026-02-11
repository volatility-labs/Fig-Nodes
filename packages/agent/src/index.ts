// src/index.ts
// Main entry point for @sosa/agent

// Tool schema and definitions (for LLM function-calling)
export {
  GRAPH_TOOLS,
  type ToolDefinition,
  type AddNodeInput,
  type RemoveNodeInput,
  type ConnectInput,
  type DisconnectInput,
  type SetParamInput,
  type LoadGraphInput,
} from './graph-tool-schema.js';
