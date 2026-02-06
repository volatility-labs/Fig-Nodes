// src/nodes/core/llm/tools-builder-node.ts
// Translated from: nodes/core/llm/tools_builder_node.py

import { Base, NodeCategory, getType, LLMToolSpec, validateLLMToolSpec, serializeForApi } from '@fig-node/core';
import type { NodeUIConfig } from '@fig-node/core';

/**
 * Takes a list of max 5 tool specs and outputs them as LLMToolSpecList.
 *
 * Input:
 * - tools_list: List[LLMToolSpec] - less than 5 tool specifications
 *
 * Output:
 * - tools: LLMToolSpecList
 */
export class ToolsBuilder extends Base {
  static inputs = {
    tools_list: getType('LLMToolSpecList'),
  };

  static optional_inputs = ['tools_list'];

  static outputs = {
    tools: getType('LLMToolSpecList'),
  };

  static CATEGORY = NodeCategory.LLM;

  static uiConfig: NodeUIConfig = {
    size: [200, 80],
    displayResults: false,
    resizable: false,
  };

  protected async executeImpl(
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
