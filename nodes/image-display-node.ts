// src/nodes/core/market/utils/image-display-node.ts

import { Node, NodeCategory, PortType, OutputDisplayType, port, type NodeDefinition } from '@sosa/core';

/**
 * Display node for images. Takes images as input and passes them through for display in the UI.
 *
 * - Inputs: 'images' -> Dict[str, str] mapping label to data URL
 * - Output: 'images' -> Dict[str, str] mapping label to data URL (pass-through)
 */
export class ImageDisplay extends Node {
  static definition: NodeDefinition = {
    inputs: [port('images', PortType.CONFIG_DICT, { optional: true })],
    outputs: [port('images', PortType.CONFIG_DICT)],
    category: NodeCategory.MARKET,
    ui: {
      outputDisplay: {
        type: OutputDisplayType.IMAGE_VIEWER,
        bind: 'images',
        options: {
          zoomable: true,
          pannable: true,
          infiniteScroll: true,
          minZoom: 1.0,
          maxZoom: 5.0,
          placeholder: 'No images to display',
        },
      },
    },
    params: [],
  };

  protected async run(
    inputs: Record<string, unknown>
  ): Promise<Record<string, unknown>> {
    const images = inputs.images;

    if (images === null || images === undefined) {
      return { images: {} };
    }

    // Pass through images for display
    return { images };
  }
}
