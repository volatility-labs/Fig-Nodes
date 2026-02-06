import { AssetSymbol, type AssetSymbolList, type IndicatorDict, type AnyList, type ConfigDict, type OHLCVBundle, type IndicatorValue, type IndicatorResult } from './domain';
import type { LLMChatMessage, LLMChatMessageList, LLMToolSpec, LLMToolSpecList, LLMChatMetrics, LLMToolHistory, LLMThinkingHistory } from './llm';
export declare const TYPE_REGISTRY: {
    readonly any: unknown;
    readonly string: string;
    readonly number: number;
    readonly boolean: boolean;
    readonly object: object;
    readonly array: unknown[];
    readonly AssetSymbol: typeof AssetSymbol;
    readonly AssetSymbolList: AssetSymbolList;
    readonly Exchange: string;
    readonly Timestamp: number;
    readonly IndicatorDict: IndicatorDict;
    readonly AnyList: AnyList;
    readonly ConfigDict: ConfigDict;
    readonly OHLCVBundle: OHLCVBundle;
    readonly Score: number;
    readonly LLMChatMessage: LLMChatMessage;
    readonly LLMChatMessageList: LLMChatMessageList;
    readonly LLMToolSpec: LLMToolSpec;
    readonly LLMToolSpecList: LLMToolSpecList;
    readonly LLMChatMetrics: LLMChatMetrics;
    readonly LLMToolHistory: LLMToolHistory;
    readonly LLMThinkingHistory: LLMThinkingHistory;
    readonly IndicatorValue: IndicatorValue;
    readonly IndicatorResult: IndicatorResult;
};
/** Valid type names for node inputs/outputs */
export type RegisteredTypeName = keyof typeof TYPE_REGISTRY;
/**
 * Returns the canonical type name string for use in node input/output definitions.
 * Provides compile-time validation that the type exists in TYPE_REGISTRY.
 */
export declare function getType<T extends RegisteredTypeName>(typeName: T): T;
