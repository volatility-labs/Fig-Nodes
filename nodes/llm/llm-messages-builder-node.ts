// src/nodes/core/llm/llm-messages-builder-node.ts
// Translated from: nodes/core/llm/llm_messages_builder_node.py

import { Base, NodeCategory, getType, validateLLMChatMessage, serializeForApi } from '@fig-node/core';
import type {
  NodeInputs,
  NodeOutputs,
  ParamMeta,
  DefaultParams,
  LLMChatMessage,
  NodeUIConfig,
} from '@fig-node/core';

/**
 * Builds a well-formed LLMChatMessageList by merging multiple input messages.
 *
 * Inputs:
 * - message_i: LLMChatMessage (optional, up to 10) – individual messages to append in order
 *
 * Output:
 * - messages: LLMChatMessageList – merged, ordered, filtered
 */
export class LLMMessagesBuilder extends Base {
  static override inputs: Record<string, unknown> = {
    message_0: getType('LLMChatMessage'),
    message_1: getType('LLMChatMessage'),
    message_2: getType('LLMChatMessage'),
    message_3: getType('LLMChatMessage'),
    message_4: getType('LLMChatMessage'),
    message_5: getType('LLMChatMessage'),
    message_6: getType('LLMChatMessage'),
    message_7: getType('LLMChatMessage'),
    message_8: getType('LLMChatMessage'),
    message_9: getType('LLMChatMessage'),
  };

  static override outputs: Record<string, unknown> = {
    messages: getType('LLMChatMessageList'),
  };

  static override defaultParams: DefaultParams = {};
  static override paramsMeta: ParamMeta[] = [];
  static override CATEGORY = NodeCategory.LLM;

  // UI configuration (ComfyUI-style) - replaces separate LLMMessagesBuilderNodeUI.ts
  static override uiConfig: NodeUIConfig = {
    size: [340, 240],
    displayResults: true,
    resultDisplay: 'json',  // Shows message list as JSON
  };

  protected override async executeImpl(inputs: NodeInputs): Promise<NodeOutputs> {
    const merged: LLMChatMessage[] = [];

    for (let i = 0; i < 10; i++) {
      const msg = inputs[`message_${i}`];
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
