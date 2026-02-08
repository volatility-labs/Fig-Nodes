// src/nodes/core/io/text-input-node.ts

import { Node, port, type NodeDefinition } from '@fig-node/core';

/**
 * Simple node that outputs a static text value from parameters.
 * Uses a DOM textarea widget for input via uiConfig.body.
 */
export class TextInput extends Node {
  static definition: NodeDefinition = {
    inputs: {},
    outputs: { text: port('string') },

    // Support both legacy "value" and preferred "text" parameter keys
    defaults: { value: '' },

    // No params needed - textarea is defined in body, not as param widget
    params: [],

    // UI configuration: use DOM textarea widget in body
    ui: {
      body: [{
        type: 'textarea',
        id: 'text-input',
        bind: 'value',
        options: {
          placeholder: 'Enter text...',
          hideOnZoom: true,
        }
      }]
    },
  };

  protected async run(_inputs: Record<string, unknown>): Promise<Record<string, unknown>> {
    return { text: this.params.value ?? '' };
  }
}
