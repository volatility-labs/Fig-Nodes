// src/nodes/core/io/text-input-node.ts

import { Node, PortType, ParamType, BodyWidgetType, port, type NodeDefinition } from '@sosa/core';

/**
 * Simple node that outputs a static text value from parameters.
 * Uses a DOM textarea widget for input via uiConfig.body.
 */
export class TextInput extends Node {
  static definition: NodeDefinition = {
    inputs: [],
    outputs: [port('text', PortType.STRING)],

    // Default for body-bound textarea widget
    params: [
      { name: 'value', type: ParamType.TEXTAREA, default: '' },
    ],

    // UI configuration: use DOM textarea widget in body
    ui: {
      body: [{
        type: BodyWidgetType.TEXTAREA,
        id: 'text-input',
        bind: 'value',
        options: {
          placeholder: 'Enter text...',
        }
      }]
    },
  };

  protected async run(_inputs: Record<string, unknown>): Promise<Record<string, unknown>> {
    return { text: this.params.value ?? '' };
  }
}
