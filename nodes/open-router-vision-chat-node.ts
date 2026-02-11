// src/nodes/core/llm/open-router-vision-chat-node.ts

import { z } from 'zod';
import {
  Node,
  NodeCategory,
  ProgressState,
  PortType,
  ParamType,
  port,
  type NodeDefinition,
  type GraphContext,
} from '@sosa/core';
import type { LLMChatMessage, LLMThinkingHistory } from './types';
import type { ConfigDict } from './types';

// Response models for validation
const OpenRouterChatMessageSchema = z.object({
  role: z.string(),
  content: z.string().nullable().optional(),
});

const OpenRouterNonStreamingChoiceSchema = z.object({
  finish_reason: z.string().nullable().optional(),
  native_finish_reason: z.string().nullable().optional(),
  message: OpenRouterChatMessageSchema,
});

const OpenRouterResponseUsageSchema = z.object({
  prompt_tokens: z.number(),
  completion_tokens: z.number(),
  total_tokens: z.number(),
});

const OpenRouterChatResponseSchema = z.object({
  id: z.string(),
  choices: z.array(OpenRouterNonStreamingChoiceSchema),
  created: z.number(),
  model: z.string(),
  object: z.enum(['chat.completion', 'chat.completion.chunk']),
  usage: OpenRouterResponseUsageSchema.nullable().optional(),
  system_fingerprint: z.string().nullable().optional(),
});

type OpenRouterChatResponse = z.infer<typeof OpenRouterChatResponseSchema>;

interface MessageContent {
  type: string;
  text?: string;
  image_url?: { url: string };
}

/**
 * Vision-capable node that connects to the OpenRouter API for chat with LLMs.
 * Supports multimodal inputs with images for vision-capable models.
 * Web search is always enabled by default.
 */
export class OpenRouterVisionChat extends Node {
  static definition: NodeDefinition = {
    inputs: [
      port('prompt', PortType.STRING, { optional: true }),
      port('system_text', PortType.STRING, { optional: true }),
      port('system_message', PortType.LLM_CHAT_MESSAGE, { optional: true }),
      port('images', PortType.CONFIG_DICT, { optional: true }),
      port('message_0', PortType.LLM_CHAT_MESSAGE, { optional: true }),
      port('message_1', PortType.LLM_CHAT_MESSAGE, { optional: true }),
      port('message_2', PortType.LLM_CHAT_MESSAGE, { optional: true }),
      port('message_3', PortType.LLM_CHAT_MESSAGE, { optional: true }),
      port('message_4', PortType.LLM_CHAT_MESSAGE, { optional: true }),
    ],
    outputs: [
      port('response', PortType.LLM_CHAT_MESSAGE),
      port('thinking_history', PortType.LLM_THINKING_HISTORY),
    ],
    category: NodeCategory.LLM,
    requiredCredentials: ['OPENROUTER_API_KEY'],
    params: [
      { name: 'model', type: ParamType.COMBO, default: 'google/gemini-2.0-flash-001', options: ['google/gemini-2.0-flash-001', 'openai/gpt-4o'] },
      {
        name: 'temperature',
        type: ParamType.NUMBER,
        default: 0.2,
        min: 0.0,
        max: 2.0,
        step: 0.05,
      },
      {
        name: 'max_tokens',
        type: ParamType.NUMBER,
        default: 20000,
        min: 1,
        step: 1,
        precision: 0,
      },
      { name: 'seed', type: ParamType.NUMBER, default: 0, min: 0, step: 1, precision: 0 },
      {
        name: 'seed_mode',
        type: ParamType.COMBO,
        default: 'fixed',
        options: ['fixed', 'random', 'increment'],
      },
    ],
    ui: {},
  };

  private static readonly DEFAULT_ASSISTANT_MESSAGE: LLMChatMessage = {
    role: 'assistant',
    content: '',
  };

  private seedState: number | null = null;
  private abortController: AbortController | null = null;

  constructor(
    nodeId: string,
    params: Record<string, unknown>,
    graphContext: GraphContext = {} as GraphContext
  ) {
    super(nodeId, params, graphContext);
  }

  forceStop(): void {
    super.forceStop();
    if (this.abortController) {
      this.abortController.abort();
    }
  }

  private extractMessageFromResponse(response: OpenRouterChatResponse | null): LLMChatMessage {
    if (response?.choices?.length) {
      const firstChoice = response.choices[0];
      if (firstChoice && firstChoice.message) {
        return {
          role: firstChoice.message.role as 'system' | 'user' | 'assistant' | 'tool',
          content: firstChoice.message.content ?? '',
        };
      }
    }
    return { ...OpenRouterVisionChat.DEFAULT_ASSISTANT_MESSAGE };
  }

  private createErrorResponse(errorMsg: string): Record<string, unknown> {
    const errorMessage: LLMChatMessage = {
      ...OpenRouterVisionChat.DEFAULT_ASSISTANT_MESSAGE,
      content: errorMsg,
    };
    return {
      response: errorMessage,
      thinking_history: [] as LLMThinkingHistory,
    };
  }

  private static buildMessages(
    existingMessages: LLMChatMessage[] | null,
    prompt: string | null,
    systemInput: LLMChatMessage | string | null,
    images: ConfigDict | null = null
  ): LLMChatMessage[] {
    const result: LLMChatMessage[] = existingMessages ? [...existingMessages] : [];

    // Add system message if not already present
    if (systemInput && !result.some((m) => m.role === 'system')) {
      if (typeof systemInput === 'string') {
        result.unshift({ role: 'system', content: systemInput });
      } else {
        result.unshift(systemInput);
      }
    }

    // Build final user message with images if provided
    const textContent = prompt ?? '';
    if (textContent.trim() || images) {
      const userContent: MessageContent[] = [];

      if (textContent.trim()) {
        userContent.push({ type: 'text', text: textContent });
      } else {
        userContent.push({ type: 'text', text: '' });
      }

      if (images) {
        for (const dataUrl of Object.values(images)) {
          if (typeof dataUrl === 'string' && dataUrl.startsWith('data:image/')) {
            userContent.push({
              type: 'image_url',
              image_url: { url: dataUrl },
            });
          }
        }
      }

      result.push({ role: 'user', content: userContent as unknown as string });
    }

    return result;
  }

  private prepareGenerationOptions(): Record<string, unknown> {
    const options: Record<string, unknown> = {};

    const temperatureRaw = this.params.temperature;
    if (temperatureRaw !== undefined && temperatureRaw !== null) {
      options.temperature =
        typeof temperatureRaw === 'string' ? parseFloat(temperatureRaw) : temperatureRaw;
    }

    const maxTokensRaw = this.params.max_tokens;
    if (maxTokensRaw !== undefined && maxTokensRaw !== null) {
      try {
        options.max_tokens = parseInt(String(maxTokensRaw), 10);
      } catch {
        options.max_tokens = 1024;
      }
    } else {
      options.max_tokens = 1024;
    }

    const seedMode = String(this.params.seed_mode ?? 'fixed').trim().toLowerCase();
    const seedRaw = this.params.seed;
    let effectiveSeed: number;

    let baseSeed = 0;
    if (seedRaw !== undefined && seedRaw !== null) {
      try {
        baseSeed = parseInt(String(seedRaw), 10);
      } catch {
        baseSeed = 0;
      }
    }

    if (seedMode === 'random') {
      effectiveSeed = Math.floor(Math.random() * (2 ** 31 - 1));
    } else if (seedMode === 'increment') {
      if (this.seedState === null) {
        this.seedState = baseSeed;
      }
      effectiveSeed = this.seedState;
      this.seedState += 1;
    } else {
      // fixed
      effectiveSeed = baseSeed;
    }

    options.seed = effectiveSeed;
    return options;
  }

  private getModelWithWebSearch(baseModel: string): string {
    let model = baseModel;

    // Ensure vision-capable model
    const visionModels = ['google/gemini-2.0-flash-001', 'openai/gpt-4o'];
    if (!visionModels.some((vm) => model.includes(vm))) {
      model = 'google/gemini-2.0-flash-001';
    }

    // Add :online suffix to enable web search
    if (!model.endsWith(':online')) {
      model = `${model}:online`;
    }

    return model;
  }

  private async callLLM(
    messages: LLMChatMessage[],
    options: Record<string, unknown>,
    apiKey: string
  ): Promise<OpenRouterChatResponse> {
    const baseModel = String(this.params.model ?? 'google/gemini-2.0-flash-001');
    const modelWithWebSearch = this.getModelWithWebSearch(baseModel);

    const requestBody = {
      model: modelWithWebSearch,
      messages,
      stream: false,
      ...options,
    };

    if (this.cancelled) {
      throw new Error('Node stopped before HTTP request');
    }

    this.abortController = new AbortController();

    const response = await fetch('https://openrouter.ai/api/v1/chat/completions', {
      method: 'POST',
      headers: {
        Authorization: `Bearer ${apiKey}`,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(requestBody),
      signal: this.abortController.signal,
    });

    if (this.cancelled) {
      throw new Error('Node stopped during HTTP request');
    }

    if (!response.ok) {
      const errorText = await response.text();
      throw new Error(`OpenRouter API error: ${response.status} - ${errorText}`);
    }

    const respData = await response.json();
    return OpenRouterChatResponseSchema.parse(respData);
  }

  private ensureAssistantRoleInplace(message: LLMChatMessage): void {
    if (!message.role) {
      message.role = 'assistant';
    }
  }

  private isLLMChatMessage(msg: unknown): msg is LLMChatMessage {
    return (
      typeof msg === 'object' &&
      msg !== null &&
      'role' in msg &&
      'content' in msg &&
      typeof (msg as Record<string, unknown>).role === 'string' &&
      ['system', 'user', 'assistant', 'tool'].includes((msg as Record<string, unknown>).role as string)
    );
  }

  protected async run(inputs: Record<string, unknown>): Promise<Record<string, unknown>> {
    const promptText = inputs.prompt as string | null;
    const systemText = inputs.system_text as string | null;
    const systemMessage = inputs.system_message;
    let systemInput: LLMChatMessage | string | null = null;
    if (this.isLLMChatMessage(systemMessage)) {
      systemInput = systemMessage;
    } else if (typeof systemText === 'string' && systemText.trim()) {
      systemInput = systemText;
    }
    const images = inputs.images as ConfigDict | null;

    // Collect messages from message_0 to message_4
    const merged: LLMChatMessage[] = [];
    for (let i = 0; i < 5; i++) {
      const msg = inputs[`message_${i}`];
      if (msg) {
        if (this.isLLMChatMessage(msg)) {
          merged.push(msg);
        } else {
          throw new TypeError(`Expected LLMChatMessage for message_${i}, got ${typeof msg}`);
        }
      }
    }

    // Filter out empty messages
    const filteredMessages = merged.filter(
      (m) => m && String(m.content ?? '').trim()
    );

    const messages = OpenRouterVisionChat.buildMessages(filteredMessages, promptText, systemInput, images);

    if (!messages.length) {
      return this.createErrorResponse(
        'No valid messages, prompt, or system provided to OpenRouterVisionChatNode'
      );
    }

    // Check API key
    const apiKey = this.credentials.get('OPENROUTER_API_KEY');
    if (!apiKey) {
      return this.createErrorResponse('OpenRouter API key missing. Set OPENROUTER_API_KEY.');
    }

    const options = this.prepareGenerationOptions();

    // Emit progress update before LLM call
    this.emitProgress(ProgressState.UPDATE, 50.0, 'Calling LLM...');

    // Call LLM
    const respDataModel = await this.callLLM(messages, options, apiKey);

    // Emit progress update after receiving response
    this.emitProgress(ProgressState.UPDATE, 90.0, 'Received...');

    if (!respDataModel.choices?.length) {
      return this.createErrorResponse('No choices in response');
    }

    let finalMessage = this.extractMessageFromResponse(respDataModel);

    if (!finalMessage) {
      finalMessage = { ...OpenRouterVisionChat.DEFAULT_ASSISTANT_MESSAGE };
    }

    this.ensureAssistantRoleInplace(finalMessage);

    // Check for error finish reason
    if (respDataModel.choices?.[0]?.finish_reason === 'error') {
      return this.createErrorResponse('API returned error');
    }

    return {
      response: finalMessage,
      thinking_history: [] as LLMThinkingHistory,
    };
  }
}
