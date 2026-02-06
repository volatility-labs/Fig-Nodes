// src/nodes/core/io/text-input-node.ts
// Translated from: nodes/core/io/text_input_node.py

import { Base } from '@fig-node/core';
import type { NodeInputs, NodeOutputs, ParamMeta, DefaultParams, NodeUIConfig } from '@fig-node/core';

/**
 * Simple node that outputs a static text value from parameters.
 * Uses a DOM textarea widget for input via uiConfig.body.
 */
export class TextInput extends Base {
  static override inputs: Record<string, unknown> = {};
  static override outputs: Record<string, unknown> = { text: 'string' };

  // Support both legacy "value" and preferred "text" parameter keys
  static override defaultParams: DefaultParams = { value: '' };

  // No paramsMeta needed - textarea is defined in body, not as param widget
  static override paramsMeta: ParamMeta[] = [];

  // UI configuration: use DOM textarea widget in body
  static override uiConfig: NodeUIConfig = {
    size: [360, 200],
    resizable: true,
    displayResults: false,
    body: [{
      type: 'textarea',
      id: 'text-input',
      bind: 'properties.value',
      options: {
        placeholder: 'Enter text...',
        hideOnZoom: true,
      }
    }]
  };

  protected override async executeImpl(_inputs: NodeInputs): Promise<NodeOutputs> {
    return { text: this.params.value ?? '' };
  }
}
