// src/nodes/core/io/text-input-node.ts
// Translated from: nodes/core/io/text_input_node.py

import { Base } from '../../base/base-node';
import type { NodeInputs, NodeOutputs, ParamMeta, DefaultParams } from '../../../core/types';

/**
 * Simple node that outputs a static text value from parameters.
 */
export class TextInput extends Base {
  static override inputs: Record<string, unknown> = {};
  static override outputs: Record<string, unknown> = { text: String };

  // Support both legacy "value" and preferred "text" parameter keys
  static override defaultParams: DefaultParams = { value: '', text: null };
  static override paramsMeta: ParamMeta[] = [
    { name: 'value', type: 'textarea', default: '' },
  ];

  protected override async executeImpl(inputs: NodeInputs): Promise<NodeOutputs> {
    // Prefer explicit "text" param if provided; fall back to legacy "value"
    let value = this.params.text;
    if (value === null || value === undefined || (typeof value === 'string' && value === '')) {
      value = this.params.value ?? '';
    }
    return { text: value };
  }
}
