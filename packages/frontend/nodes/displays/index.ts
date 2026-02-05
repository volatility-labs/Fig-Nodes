// Output Display Module
// Handles rendering of execution results in node bodies

export type {
  OutputDisplayRenderer,
  RenderBounds,
  Point,
} from './OutputDisplayRenderer';

export { BaseOutputDisplayRenderer } from './OutputDisplayRenderer';

export {
  createOutputDisplay,
  registerOutputDisplay,
  hasOutputDisplay,
  getRegisteredDisplayTypes,
} from './outputDisplayRegistry';

// Re-export renderer implementations for direct access if needed
export { TextDisplayRenderer } from './renderers/TextDisplayRenderer';
export { ImageGalleryRenderer } from './renderers/ImageGalleryRenderer';
export { ImageViewerRenderer } from './renderers/ImageViewerRenderer';
export { ChartPreviewRenderer } from './renderers/ChartPreviewRenderer';
export { NoteDisplayRenderer } from './renderers/NoteDisplayRenderer';
