// src/types/index.ts
// Barrel re-export for all types

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
  // Interfaces & types
  type OHLCVBar,
  type AssetSymbolData,
  type IndicatorValue,
  type CreateIndicatorValueOptions,
  type IndicatorResult,
  type CreateIndicatorResultOptions,
  // Factory functions
  createIndicatorValue,
  createIndicatorResult,
  // Type aliases
  type AssetSymbolList,
  type IndicatorDict,
  type AnyList,
  type ConfigDict,
  type OHLCVBundle,
} from './domain';

export {
  type SerialisedLink,
  type SerialisedNodeInput,
  type SerialisedNodeOutput,
  type SerialisedNode,
  type SerialisedGraphState,
  type SerialisableGraph,
} from './graph';

export {
  // Zod schemas
  LLMToolFunctionSchema,
  LLMToolSpecSchema,
  LLMToolCallFunctionSchema,
  LLMToolCallSchema,
  LLMChatMessageSchema,
  LLMChatMetricsSchema,
  LLMToolHistoryItemSchema,
  LLMThinkingHistoryItemSchema,
  // Inferred types
  type LLMToolFunction,
  type LLMToolSpec,
  type LLMToolCallFunction,
  type LLMToolCall,
  type LLMChatMessage,
  type LLMChatMetrics,
  type LLMToolHistoryItem,
  type LLMThinkingHistoryItem,
  // LLM type aliases
  type LLMChatMessageList,
  type LLMToolSpecList,
  type LLMToolHistory,
  type LLMThinkingHistory,
  // Validation helpers
  validateLLMToolSpec,
  validateLLMChatMessage,
} from './llm';

export {
  // Parameter types
  type ParamScalar,
  type ParamValue,
  type ParamType,
  type ParamMeta,
  type DefaultParams,
  type NodeInputs,
  type NodeOutputs,
  // Output display
  type OutputDisplayType,
  type OutputDisplayConfig,
  type OutputDisplayOptions,
  // Result display
  type ResultDisplayMode,
  type NodeAction,
  type ResultFormatter,
  // Body widgets
  type BodyWidgetType,
  type DataSource,
  type BodyWidget,
  type BodyWidgetOptions,
  type ResultWidget,
  type SlotConfig,
  // Node UI config
  type NodeUIConfig,
} from './node-ui';

export {
  type ExecutionResult,
  ExecutionResultFactory,
  type ProgressEvent,
  type ProgressCallback,
  type ResultCallback,
  type NodeConstructor,
  type NodeRegistry,
  serializeForApi,
} from './execution';

export {
  NodeError,
  NodeValidationError,
  NodeExecutionError,
} from './errors';

export {
  TYPE_REGISTRY,
  type RegisteredTypeName,
  getType,
} from './type-registry';

export {
  type CredentialProvider,
  CREDENTIAL_PROVIDER_KEY,
} from './credentials';
