// src/types/type-registry.ts
// Runtime type registry mapping type names to TypeScript types

import {
  AssetSymbol,
  type AssetSymbolList,
  type IndicatorDict,
  type AnyList,
  type ConfigDict,
  type OHLCVBundle,
  type IndicatorValue,
  type IndicatorResult,
} from './domain';

import type {
  LLMChatMessage,
  LLMChatMessageList,
  LLMToolSpec,
  LLMToolSpecList,
  LLMChatMetrics,
  LLMToolHistory,
  LLMThinkingHistory,
} from './llm';

export const TYPE_REGISTRY = {
  // Primitives
  any: {} as unknown,
  string: '' as string,
  number: 0 as number,
  boolean: false as boolean,
  object: {} as object,
  array: [] as unknown[],
  // Domain types
  AssetSymbol,
  AssetSymbolList: [] as AssetSymbolList,
  Exchange: '' as string,
  Timestamp: 0 as number,
  IndicatorDict: {} as IndicatorDict,
  AnyList: [] as AnyList,
  ConfigDict: {} as ConfigDict,
  OHLCVBundle: new Map() as OHLCVBundle,
  Score: 0 as number,
  LLMChatMessage: {} as LLMChatMessage,
  LLMChatMessageList: [] as LLMChatMessageList,
  LLMToolSpec: {} as LLMToolSpec,
  LLMToolSpecList: [] as LLMToolSpecList,
  LLMChatMetrics: {} as LLMChatMetrics,
  LLMToolHistory: [] as LLMToolHistory,
  LLMThinkingHistory: [] as LLMThinkingHistory,
  IndicatorValue: {} as IndicatorValue,
  IndicatorResult: {} as IndicatorResult,
} as const;

/** Valid type names for node inputs/outputs */
export type RegisteredTypeName = keyof typeof TYPE_REGISTRY;

/**
 * Returns the canonical type name string for use in node input/output definitions.
 * Provides compile-time validation that the type exists in TYPE_REGISTRY.
 */
export function getType<T extends RegisteredTypeName>(typeName: T): T {
  if (!(typeName in TYPE_REGISTRY)) {
    throw new Error(`Unknown type: ${typeName}`);
  }
  return typeName;
}
