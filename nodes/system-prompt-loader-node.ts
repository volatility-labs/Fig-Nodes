// src/nodes/core/io/system-prompt-loader-node.ts

import { Node, NodeCategory, port, type NodeDefinition } from '@sosa/core';

/**
 * Loads a system prompt from UI-provided content (e.g., uploaded .md/.txt).
 *
 * Outputs:
 * - system: str
 */
export class SystemPromptLoader extends Node {
  static definition: NodeDefinition = {
    inputs: [],
    outputs: [port('system', 'string')],
    params: [
      { name: 'content', type: 'textarea', default: '' },
      { name: 'file', type: 'fileupload', default: '', options: { accept: '.txt,.md' } },
    ],

    // Keep visible in IO category
    category: NodeCategory.IO,

    ui: {
      body: [{
        type: 'textarea',
        id: 'content-display',
        bind: 'content',
        options: {
          placeholder: 'System prompt content...',
        }
      }]
    },
  };

  protected async run(_inputs: Record<string, unknown>): Promise<Record<string, unknown>> {
    let content = this.params.content ?? '';
    if (typeof content !== 'string') {
      content = String(content);
    }
    return { system: content };
  }
}
