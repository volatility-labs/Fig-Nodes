// src/nodes/core/io/system-prompt-loader-node.ts
// Translated from: nodes/core/io/system_prompt_loader_node.py

import { Base } from '../../base/base-node';
import { NodeCategory } from '../../../core/types';
import type { NodeInputs, NodeOutputs, ParamMeta, DefaultParams } from '../../../core/types';

/**
 * Loads a system prompt from UI-provided content (e.g., uploaded .md/.txt).
 *
 * Outputs:
 * - system: str
 */
export class SystemPromptLoader extends Base {
  static override inputs: Record<string, unknown> = {};
  static override outputs: Record<string, unknown> = { system: String };
  static override defaultParams: DefaultParams = { content: '' };
  static override paramsMeta: ParamMeta[] = [
    { name: 'content', type: 'textarea', default: '' },
  ];

  // Keep visible in IO category
  static override CATEGORY = NodeCategory.IO;

  protected override async executeImpl(_inputs: NodeInputs): Promise<NodeOutputs> {
    let content = this.params.content ?? '';
    if (typeof content !== 'string') {
      content = String(content);
    }
    return { system: content };
  }
}
