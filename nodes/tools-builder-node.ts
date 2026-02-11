// src/nodes/core/llm/tools-builder-node.ts

import {
  Node,
  NodeCategory,
  port,
  serializeForApi,
  type NodeDefinition,
} from '@sosa/core';
import { validateLLMToolSpec, type LLMToolSpec } from './types';

/**
 * Takes a list of max 5 tool specs and outputs them as LLMToolSpecList.
 *
 * Input:
 * - tools_list: List[LLMToolSpec] - less than 5 tool specifications
 *
 * Output:
 * - tools: LLMToolSpecList
 */
export class ToolsBuilder extends Node {
  static definition: NodeDefinition = {
    inputs: [port('tools_list', 'LLMToolSpecList', { optional: true })],
    outputs: [port('tools', 'LLMToolSpecList')],
    category: NodeCategory.LLM,
    ui: {},
  };

  protected async run(
    inputs: Record<string, unknown>
  ): Promise<Record<string, unknown>> {
    const toolsInput = (inputs.tools_list as LLMToolSpec[]) || [];

    if (toolsInput.length > 5) {
      throw new Error(`tools_list must be less than 5 tools, got ${toolsInput.length}`);
    }

    // Validate and convert each tool spec
    const validatedTools: LLMToolSpec[] = [];

    for (let i = 0; i < toolsInput.length; i++) {
      const toolSpec = toolsInput[i];
      const validated = validateLLMToolSpec(toolSpec);

      if (validated) {
        validatedTools.push(validated);
      } else {
        throw new Error(`Tool at index ${i} is invalid: expected LLMToolSpec`);
      }
    }

    return { tools: serializeForApi(validatedTools) };
  }
}
