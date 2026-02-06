// src/types/type-registry.ts
// Runtime type registry mapping type names to TypeScript types
import { AssetSymbol, } from './domain';
export const TYPE_REGISTRY = {
    // Primitives
    any: {},
    string: '',
    number: 0,
    boolean: false,
    object: {},
    array: [],
    // Domain types
    AssetSymbol,
    AssetSymbolList: [],
    Exchange: '',
    Timestamp: 0,
    IndicatorDict: {},
    AnyList: [],
    ConfigDict: {},
    OHLCVBundle: new Map(),
    Score: 0,
    LLMChatMessage: {},
    LLMChatMessageList: [],
    LLMToolSpec: {},
    LLMToolSpecList: [],
    LLMChatMetrics: {},
    LLMToolHistory: [],
    LLMThinkingHistory: [],
    IndicatorValue: {},
    IndicatorResult: {},
};
/**
 * Returns the canonical type name string for use in node input/output definitions.
 * Provides compile-time validation that the type exists in TYPE_REGISTRY.
 */
export function getType(typeName) {
    if (!(typeName in TYPE_REGISTRY)) {
        throw new Error(`Unknown type: ${typeName}`);
    }
    return typeName;
}
