// src/nodes/core/io/note-node.ts

import { Node, NodeCategory, type NodeDefinition } from '@fig-node/core';

/**
 * A visual note/annotation node for organizing and labeling groups of nodes.
 *
 * This node provides no functionality - it's purely visual. It renders as a
 * colored rectangle with editable text content that can be used to visually
 * group and annotate other nodes on the canvas.
 */
export class Note extends Node {
  static definition: NodeDefinition = {
    inputs: {},
    outputs: {},
    category: NodeCategory.IO,

    params: [
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
    ],

    ui: {
      outputDisplay: {
        type: 'note-display',
        options: {
          uniformColor: '#334',
          orderLocked: -10000,
          titleEditable: true,
        },
      },
    },
  };

  protected async run(_inputs: Record<string, unknown>): Promise<Record<string, unknown>> {
    // Note node provides no execution - it's purely visual.
    return {};
  }
}
