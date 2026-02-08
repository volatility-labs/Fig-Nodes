// LLM types with Zod schemas for runtime validation

import { z } from 'zod';
import { registerType } from '@fig-node/core';

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

// ============ Inferred Types ============

export type LLMToolFunction = z.infer<typeof LLMToolFunctionSchema>;
export type LLMToolSpec = z.infer<typeof LLMToolSpecSchema>;
export type LLMToolCallFunction = z.infer<typeof LLMToolCallFunctionSchema>;
export type LLMToolCall = z.infer<typeof LLMToolCallSchema>;
export type LLMChatMessage = z.infer<typeof LLMChatMessageSchema>;
export type LLMChatMetrics = z.infer<typeof LLMChatMetricsSchema>;
export type LLMToolHistoryItem = z.infer<typeof LLMToolHistoryItemSchema>;
export type LLMThinkingHistoryItem = z.infer<typeof LLMThinkingHistoryItemSchema>;

// ============ LLM Type Aliases ============

export type LLMChatMessageList = LLMChatMessage[];
export type LLMToolSpecList = LLMToolSpec[];
export type LLMToolHistory = LLMToolHistoryItem[];
export type LLMThinkingHistory = LLMThinkingHistoryItem[];

// ============ Validation Helpers ============

export function validateLLMToolSpec(obj: unknown): LLMToolSpec | null {
  const result = LLMToolSpecSchema.safeParse(obj);
  return result.success ? result.data : null;
}

export function validateLLMChatMessage(obj: unknown): LLMChatMessage | null {
  const result = LLMChatMessageSchema.safeParse(obj);
  return result.success ? result.data : null;
}

// ============ Register LLM port types ============

registerType('LLMChatMessage');
registerType('LLMChatMessageList');
registerType('LLMToolSpec');
registerType('LLMToolSpecList');
registerType('LLMChatMetrics');
registerType('LLMToolHistory');
registerType('LLMThinkingHistory');
registerType('LLMToolHistoryItem');
registerType('LLMThinkingHistoryItem');
