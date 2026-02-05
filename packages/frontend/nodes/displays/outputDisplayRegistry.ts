import type { OutputDisplayType } from '@fig-node/core';
import type { OutputDisplayRenderer } from './OutputDisplayRenderer';

// Import renderer implementations
import { TextDisplayRenderer } from './renderers/TextDisplayRenderer';
import { DOMTextDisplayRenderer } from './renderers/DOMTextDisplayRenderer';
import { ImageGalleryRenderer } from './renderers/ImageGalleryRenderer';
import { ImageViewerRenderer } from './renderers/ImageViewerRenderer';
import { ChartPreviewRenderer } from './renderers/ChartPreviewRenderer';
import { NoteDisplayRenderer } from './renderers/NoteDisplayRenderer';

/**
 * Factory function type for creating output display renderers.
 */
type OutputDisplayRendererFactory = () => OutputDisplayRenderer;

/**
 * Registry of output display renderers.
 * Maps display types to their factory functions.
 */
const registry = new Map<OutputDisplayType, OutputDisplayRendererFactory>([
  ['text-display', () => new TextDisplayRenderer()],
  ['text-display-dom', () => new DOMTextDisplayRenderer()],
  ['image-gallery', () => new ImageGalleryRenderer()],
  ['image-viewer', () => new ImageViewerRenderer()],
  ['chart-preview', () => new ChartPreviewRenderer()],
  ['note-display', () => new NoteDisplayRenderer()],
]);

/**
 * Create an output display renderer by type.
 * @param type The output display type
 * @returns A new renderer instance, or null for 'none' type
 * @throws Error if type is not registered
 */
export function createOutputDisplay(type: OutputDisplayType): OutputDisplayRenderer | null {
  if (type === 'none') {
    return null;
  }

  const factory = registry.get(type);
  if (!factory) {
    console.warn(`Unknown output display type: ${type}, falling back to text-display`);
    return new TextDisplayRenderer();
  }

  return factory();
}

/**
 * Register a custom output display renderer.
 * Allows extensions to add new display types.
 * @param type The display type identifier
 * @param factory Factory function to create renderer instances
 */
export function registerOutputDisplay(
  type: OutputDisplayType | string,
  factory: OutputDisplayRendererFactory
): void {
  registry.set(type as OutputDisplayType, factory);
}

/**
 * Check if an output display type is registered.
 */
export function hasOutputDisplay(type: OutputDisplayType | string): boolean {
  return type === 'none' || registry.has(type as OutputDisplayType);
}

/**
 * Get all registered output display types.
 */
export function getRegisteredDisplayTypes(): OutputDisplayType[] {
  return ['none', ...registry.keys()];
}
