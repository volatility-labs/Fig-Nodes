// src/types/llm.ts
// LLM types with Zod schemas for runtime validation
import { z } from 'zod';
// ============ Zod Schemas ============
export const LLMToolFunctionSchema = z.object({
    name: z.string(),
    description: z.string().nullable().optional(),
    parameters: z.record(z.unknown()).default({}),
}).passthrough();
export const LLMToolSpecSchema = z.object({
    type: z.literal('function').default('function'),
    function: LLMToolFunctionSchema,
}).passthrough();
export const LLMToolCallFunctionSchema = z.object({
    name: z.string().default(''),
    arguments: z.record(z.unknown()).default({}),
}).passthrough();
export const LLMToolCallSchema = z.object({
    id: z.string().default(''),
    function: LLMToolCallFunctionSchema.default({ name: '', arguments: {} }),
}).passthrough();
export const LLMChatMessageSchema = z.object({
    role: z.enum(['system', 'user', 'assistant', 'tool']),
    content: z.union([z.string(), z.record(z.unknown())]).default(''),
    thinking: z.string().nullable().optional(),
    images: z.array(z.string()).nullable().optional(),
    tool_calls: z.array(LLMToolCallSchema).nullable().optional(),
    tool_name: z.string().nullable().optional(),
    tool_call_id: z.string().nullable().optional(),
}).passthrough();
export const LLMChatMetricsSchema = z.object({
    total_duration: z.number().nullable().optional(),
    load_duration: z.number().nullable().optional(),
    prompt_eval_count: z.number().nullable().optional(),
    prompt_eval_duration: z.number().nullable().optional(),
    eval_count: z.number().nullable().optional(),
    eval_duration: z.number().nullable().optional(),
    error: z.string().nullable().optional(),
    seed: z.number().nullable().optional(),
    temperature: z.number().nullable().optional(),
    parse_error: z.string().nullable().optional(),
}).passthrough();
export const LLMToolHistoryItemSchema = z.object({
    call: z.union([LLMToolCallSchema, z.record(z.unknown())]),
    result: z.record(z.unknown()).default({}),
}).passthrough();
export const LLMThinkingHistoryItemSchema = z.object({
    thinking: z.string(),
    iteration: z.number().default(0),
}).passthrough();
// ============ Validation Helpers ============
export function validateLLMToolSpec(obj) {
    const result = LLMToolSpecSchema.safeParse(obj);
    return result.success ? result.data : null;
}
export function validateLLMChatMessage(obj) {
    const result = LLMChatMessageSchema.safeParse(obj);
    return result.success ? result.data : null;
}
