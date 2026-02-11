import { Node, NodeCategory, PortType, OutputDisplayType, port, type NodeDefinition } from '@sosa/core';

const MAX_DISPLAY_CHARS = 10_000;

/**
 * Logging node that takes any input and displays it in the node.
 */
export class Logging extends Node {
  static definition: NodeDefinition = {
    inputs: [port('input', PortType.ANY)],
    outputs: [port('output', PortType.STRING)],

    category: NodeCategory.IO,

    params: [],

    ui: {
      outputDisplay: {
        type: OutputDisplayType.TEXT_DISPLAY_DOM,
        bind: 'output',
        options: {
          placeholder: 'Logs appear here...',
          scrollable: true,
          streaming: true,
          formats: ['auto', 'json', 'plain', 'markdown'],
        },
      },
    },
  };

  constructor(
    nodeId: string,
    params: Record<string, unknown>,
    graphContext: Record<string, unknown> = {}
  ) {
    super(nodeId, params, graphContext);
  }

  protected async run(inputs: Record<string, unknown>): Promise<Record<string, unknown>> {
    const value = inputs.input;

    if (value === null || value === undefined) {
      return { output: '(no input)' };
    }

    let text: string;
    if (typeof value === 'string') {
      text = value;
    } else {
      try {
        text = JSON.stringify(value, null, 2);
      } catch {
        text = String(value);
      }
    }

    if (text.length > MAX_DISPLAY_CHARS) {
      text = text.slice(0, MAX_DISPLAY_CHARS) + `\n\n--- truncated (${text.length} total chars) ---`;
    }

    return { output: text };
  }
}
