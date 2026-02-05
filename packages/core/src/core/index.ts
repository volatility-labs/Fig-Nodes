// src/core/index.ts
// Core module exports

// Types and enums
export {
  // Enums
  AssetClass,
  InstrumentType,
  Provider,
  IndicatorType,
  ProgressState,
  ExecutionOutcome,
  NodeCategory,

  // Classes
  AssetSymbol,
  NodeError,
  NodeValidationError,
  NodeExecutionError,

  // Interfaces
  type OHLCVBar,
  type AssetSymbolData,
  type IndicatorValue,
  type IndicatorResult,
  type ExecutionResult,
  type ParamMeta,
  type DefaultParams,
  type NodeInputs,
  type NodeOutputs,
  type SerialisedLink,
  type SerialisedNode,
  type SerialisedNodeInput,
  type SerialisedNodeOutput,
  type SerialisedGraphState,
  type SerialisableGraph,
  type ProgressEvent,
  type ProgressCallback,
  type ResultCallback,
  type NodeRegistry,
  type NodeConstructor,

  // UI Configuration types (ComfyUI-style + Option B)
  type ResultDisplayMode,
  type NodeAction,
  type ResultFormatter,
  type BodyWidgetType,
  type DataSource,
  type BodyWidget,
  type BodyWidgetOptions,
  type ResultWidget,
  type SlotConfig,
  type NodeUIConfig,

  // Output Display types (Option A)
  type OutputDisplayType,
  type OutputDisplayConfig,
  type OutputDisplayOptions,

  // LLM Types
  type LLMToolFunction,
  type LLMToolSpec,
  type LLMToolCallFunction,
  type LLMToolCall,
  type LLMChatMessage,
  type LLMChatMetrics,
  type LLMToolHistoryItem,
  type LLMThinkingHistoryItem,

  // Type aliases
  type AssetSymbolList,
  type IndicatorDict,
  type AnyList,
  type ConfigDict,
  type OHLCVBundle,
  type LLMChatMessageList,
  type LLMToolSpecList,
  type LLMToolHistory,
  type LLMThinkingHistory,

  // Zod schemas
  LLMToolFunctionSchema,
  LLMToolSpecSchema,
  LLMToolCallFunctionSchema,
  LLMToolCallSchema,
  LLMChatMessageSchema,
  LLMChatMetricsSchema,
  LLMToolHistoryItemSchema,
  LLMThinkingHistoryItemSchema,

  // Factory functions
  createIndicatorValue,
  createIndicatorResult,
  ExecutionResultFactory,

  // Validation helpers
  validateLLMToolSpec,
  validateLLMChatMessage,
  serializeForApi,

  // Type registry
  TYPE_REGISTRY,
  getType,
} from './types';

// Type utilities
export { detectType, inferDataType, parseTypeString } from './type-utils';

// API Key Vault
export { APIKeyVault, getVault } from './api-key-vault';

// Serialization
export {
  serializeValue,
  serializeResults,
  isOHLCVBundle,
  serializeOHLCVBundle,
  type SerializedScalar,
  type SerializedValue,
  type ExecutionResults,
  type SerializedResults,
} from './serialization';

// Graph Executor
export { GraphExecutor } from './graph-executor';

// Node Registry
export {
  loadNodes,
  createEmptyRegistry,
  getNodeRegistry,
  resetNodeRegistry,
  setNodeRegistry,
} from './node-registry';
