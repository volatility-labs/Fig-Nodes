// src/nodes/core/io/system-prompt-loader-node.ts
// Translated from: nodes/core/io/system_prompt_loader_node.py

import { Base, NodeCategory } from '@fig-node/core';
import type { NodeInputs, NodeOutputs, ParamMeta, DefaultParams, NodeUIConfig } from '@fig-node/core';

/**
 * Loads a system prompt from UI-provided content (e.g., uploaded .md/.txt).
 *
 * Outputs:
 * - system: str
 */
export class SystemPromptLoader extends Base {
  static override inputs: Record<string, unknown> = {};
  static override outputs: Record<string, unknown> = { system: String };
  static override defaultParams: DefaultParams = { content: '', file: '' };
  static override paramsMeta: ParamMeta[] = [
    { name: 'content', type: 'textarea', default: '' },
    { name: 'file', type: 'fileupload', default: '', options: { accept: '.txt,.md' } },
  ];

  // Keep visible in IO category
  static override CATEGORY = NodeCategory.IO;

  static uiConfig: NodeUIConfig = {
    size: [360, 220],
    resizable: true,
    displayResults: true,
    body: [{
      type: 'textarea',
      id: 'content-display',
      bind: 'content',
      options: {
        placeholder: 'System prompt content...',
        hideOnZoom: true,
      }
    }]
  };

  protected override async executeImpl(_inputs: NodeInputs): Promise<NodeOutputs> {
    let content = this.params.content ?? '';
    if (typeof content !== 'string') {
      content = String(content);
    }
    return { system: content };
  }
}
