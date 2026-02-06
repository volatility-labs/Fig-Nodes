// src/nodes/core/market/utils/image-display-node.ts
// Translated from: nodes/core/market/utils/image_display_node.py

import { Base, NodeCategory, getType, type NodeUIConfig } from '@fig-node/core';

/**
 * Display node for images. Takes images as input and passes them through for display in the UI.
 *
 * - Inputs: 'images' -> Dict[str, str] mapping label to data URL
 * - Output: 'images' -> Dict[str, str] mapping label to data URL (pass-through)
 */
export class ImageDisplay extends Base {
  static inputs = {
    images: getType('ConfigDict'),
  };

  static outputs = {
    images: getType('ConfigDict'),
  };

  static optional_inputs = ['images'];

  static CATEGORY = NodeCategory.MARKET;

  static uiConfig: NodeUIConfig = {
    size: [500, 360],
    resizable: true,
    displayResults: false,
    outputDisplay: {
      type: 'image-viewer',
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
  };

  protected async executeImpl(
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
