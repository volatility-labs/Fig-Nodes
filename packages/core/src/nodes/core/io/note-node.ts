// src/nodes/core/io/note-node.ts
// Translated from: nodes/core/io/note_node.py

import { Base } from '../../base/base-node';
import { NodeCategory } from '../../../core/types';
import type { NodeInputs, NodeOutputs, ParamMeta, DefaultParams, NodeUIConfig } from '../../../core/types';

/**
 * A visual note/annotation node for organizing and labeling groups of nodes.
 *
 * This node provides no functionality - it's purely visual. It renders as a
 * colored rectangle with editable text content that can be used to visually
 * group and annotate other nodes on the canvas.
 */
export class Note extends Base {
  static override inputs: Record<string, unknown> = {};
  static override outputs: Record<string, unknown> = {};
  static override CATEGORY: NodeCategory = NodeCategory.IO;

  static override paramsMeta: ParamMeta[] = [
    {
      name: 'text',
      type: 'textarea',
      default: 'Note',
    },
    {
      name: 'color',
      type: 'text',
      default: '#334',
    },
  ];

  static override defaultParams: DefaultParams = {
    text: 'Note',
    color: '#334',
  };

  static uiConfig: NodeUIConfig = {
    size: [300, 200],
    resizable: true,
    displayResults: false,
    outputDisplay: {
      type: 'note-display',
      options: {
        uniformColor: '#334',
        orderLocked: -10000,
        titleEditable: true,
      },
    },
  };

  protected override async executeImpl(_inputs: NodeInputs): Promise<NodeOutputs> {
    // Note node provides no execution - it's purely visual.
    return {};
  }
}
