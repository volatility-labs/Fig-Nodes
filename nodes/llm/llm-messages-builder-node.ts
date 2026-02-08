// src/nodes/core/llm/llm-messages-builder-node.ts

import {
  Node,
  NodeCategory,
  serializeForApi,
  port,
  type NodeDefinition,
} from '@fig-node/core';
import { validateLLMChatMessage, type LLMChatMessage } from './types';

/**
 * Builds a well-formed LLMChatMessageList by merging multiple input messages.
 *
 * Inputs:
 * - messages: LLMChatMessage (multi-connection) – individual messages to append in order
 *
 * Output:
 * - messages: LLMChatMessageList – merged, ordered, filtered
 */
export class LLMMessagesBuilder extends Node {
  static definition: NodeDefinition = {
    inputs: {
      messages: port('LLMChatMessage', { multi: true, optional: true }),
    },
    outputs: {
      messages: port('LLMChatMessageList'),
    },
    params: [],
    category: NodeCategory.LLM,
    ui: {
      resultDisplay: 'json',  // Shows message list as JSON
    },
  };

  protected async run(inputs: Record<string, unknown>): Promise<Record<string, unknown>> {
    const rawMessages = inputs.messages;
    const messagesInput = (Array.isArray(rawMessages) ? rawMessages : []) as unknown[];

    const merged: LLMChatMessage[] = [];
    for (const msg of messagesInput) {
      if (msg) {
        const validated = validateLLMChatMessage(msg);
        if (validated) {
          merged.push(validated);
        } else {
          throw new TypeError(`Expected LLMChatMessage, got ${typeof msg}`);
        }
      }
    }

    // Always drop empty messages
    const messages = merged.filter((m) => {
      if (!m) return false;
      const content = typeof m.content === 'string' ? m.content : '';
      return content.trim().length > 0;
    });

    return { messages: serializeForApi(messages) };
  }
}
