import { LiteGraph } from '@fig-node/litegraph';
import {
  BaseOutputDisplayRenderer,
  type RenderBounds,
} from './OutputDisplayRenderer';

/**
 * Image gallery renderer for displaying multiple images.
 *
 * Features:
 * - Grid layout for multiple images
 * - Aspect ratio preservation
 * - Auto-resize node to fit content
 * - Loading states
 *
 * Extracted from OHLCVPlotNodeUI.ts
 */
export class ImageGalleryRenderer extends BaseOutputDisplayRenderer {
  readonly type = 'image-gallery';

  private images: Record<string, string> = {};
  private loadedImages: Map<string, HTMLImageElement> = new Map();
  private imageAspectRatios: Map<string, number> = new Map();

  draw(ctx: CanvasRenderingContext2D, bounds: RenderBounds): void {
    if (!ctx || typeof ctx.fillRect !== 'function') return;

    const { x, y, width, height } = bounds;
    const labels = Object.keys(this.images);

    // Background
    ctx.fillStyle = '#0f1419';
    ctx.fillRect(x, y, width, height);

    // Border
    ctx.strokeStyle = 'rgba(75, 85, 99, 0.2)';
    ctx.lineWidth = 1;
    ctx.strokeRect(x + 0.5, y + 0.5, width - 1, height - 1);

    if (!labels.length) {
      // Empty state
      ctx.fillStyle = 'rgba(156, 163, 175, 0.4)';
      ctx.font = '12px Arial';
      ctx.textAlign = 'center';
      ctx.textBaseline = 'middle';
      ctx.fillText(
        this.options.emptyText ?? 'No images to display',
        x + width / 2,
        y + height / 2
      );
      return;
    }

    // Single image: use full space
    if (labels.length === 1) {
      const label = labels[0]!;
      const img = this.loadedImages.get(label);

      if (img) {
        const fit = this.fitImageToBounds(img.width, img.height, width - 4, height - 4);
        ctx.drawImage(img, x + 2 + fit.x, y + 2 + fit.y, fit.width, fit.height);
      } else {
        this.drawLoadingState(ctx, x, y, width, height);
      }
      return;
    }

    // Multiple images: grid layout
    const { cols, rows } = this.calculateGridLayout(labels.length, width, height);
    const cellSpacing = 4;
    const cellW = Math.floor((width - (cols - 1) * cellSpacing) / cols);
    const cellH = Math.floor((height - (rows - 1) * cellSpacing) / rows);

    let idx = 0;
    for (let r = 0; r < rows; r++) {
      for (let c = 0; c < cols; c++) {
        if (idx >= labels.length) break;

        const label = labels[idx++]!;
        const img = this.loadedImages.get(label);
        const cellX = x + c * (cellW + cellSpacing);
        const cellY = y + r * (cellH + cellSpacing);

        if (img) {
          const fit = this.fitImageToBounds(img.width, img.height, cellW - 2, cellH - 2);
          ctx.drawImage(img, cellX + 1 + fit.x, cellY + 1 + fit.y, fit.width, fit.height);
        }

        // Cell border
        ctx.strokeStyle = 'rgba(75, 85, 99, 0.18)';
        ctx.lineWidth = 1;
        ctx.strokeRect(cellX + 0.5, cellY + 0.5, cellW - 1, cellH - 1);
      }
    }
  }

  private drawLoadingState(
    ctx: CanvasRenderingContext2D,
    x: number,
    y: number,
    width: number,
    height: number
  ): void {
    ctx.fillStyle = 'rgba(156, 163, 175, 0.5)';
    ctx.font = '12px Arial';
    ctx.textAlign = 'center';
    ctx.textBaseline = 'middle';
    ctx.fillText('Loading...', x + width / 2, y + height / 2);
  }

  updateFromResult(result: unknown): void {
    // Expect { images: { label: dataUrl } } or just { label: dataUrl }
    const resultObj = result as Record<string, unknown>;
    const imgs = (resultObj?.images as Record<string, string>) ??
                 (typeof result === 'object' ? result as Record<string, string> : {});

    this.images = imgs;
    this.loadedImages.clear();
    this.imageAspectRatios.clear();

    // Preload all images
    let loadedCount = 0;
    const totalImages = Object.keys(imgs).length;

    Object.entries(imgs).forEach(([label, dataUrl]) => {
      if (typeof dataUrl !== 'string') return;

      const img = new Image();
      img.onload = () => {
        this.loadedImages.set(label, img);
        this.imageAspectRatios.set(label, img.width / img.height);
        loadedCount++;

        // Auto-resize when all loaded
        if (loadedCount === totalImages && this.options.autoResize) {
          this.resizeNodeToFit();
        }

        this.setDirtyCanvas();
      };
      img.src = dataUrl;
    });

    this.setDirtyCanvas();
  }

  private fitImageToBounds(
    imgWidth: number,
    imgHeight: number,
    maxWidth: number,
    maxHeight: number
  ): { width: number; height: number; x: number; y: number } {
    const imgAspect = imgWidth / imgHeight;
    const containerAspect = maxWidth / maxHeight;

    let width: number;
    let height: number;

    if (imgAspect > containerAspect) {
      width = maxWidth;
      height = maxWidth / imgAspect;
    } else {
      height = maxHeight;
      width = maxHeight * imgAspect;
    }

    return {
      width,
      height,
      x: (maxWidth - width) / 2,
      y: (maxHeight - height) / 2,
    };
  }

  private calculateGridLayout(
    count: number,
    containerWidth: number,
    containerHeight: number
  ): { cols: number; rows: number } {
    if (this.options.gridLayout && typeof this.options.gridLayout === 'object') {
      return this.options.gridLayout;
    }

    // Auto layout: try to make cells as square as possible
    const cols = Math.ceil(Math.sqrt(count));
    const rows = Math.ceil(count / cols);
    return { cols, rows };
  }

  private resizeNodeToFit(): void {
    const labels = Object.keys(this.images);
    if (!labels.length) return;

    const widgetHeight = (this.node as any).widgets?.length
      ? (this.node as any).widgets.length * LiteGraph.NODE_WIDGET_HEIGHT
      : 0;
    const padding = 12;
    const headerHeight = LiteGraph.NODE_TITLE_HEIGHT + widgetHeight + 8;
    const minWidth = 400;
    const minHeight = 200;
    const maxWidth = 800;

    if (labels.length === 1) {
      const aspectRatio = this.imageAspectRatios.get(labels[0]!);
      if (!aspectRatio) return;

      const contentWidth = Math.max(minWidth, Math.min(maxWidth, 500));
      const contentHeight = contentWidth / aspectRatio;
      const totalHeight = headerHeight + padding * 2 + contentHeight;

      this.node.size[0] = contentWidth + padding * 2;
      this.node.size[1] = Math.max(minHeight + headerHeight, totalHeight);
    } else {
      const { cols, rows } = this.calculateGridLayout(labels.length, 500, 400);
      const aspectRatios = Array.from(this.imageAspectRatios.values());
      const avgAspect = aspectRatios.reduce((sum, ar) => sum + ar, 0) / aspectRatios.length;

      const cellSpacing = 4;
      const targetCellWidth = Math.max(150, Math.min(250, 200));
      const targetCellHeight = targetCellWidth / avgAspect;

      const contentWidth = cols * targetCellWidth + (cols - 1) * cellSpacing;
      const contentHeight = rows * targetCellHeight + (rows - 1) * cellSpacing;
      const totalHeight = headerHeight + padding * 2 + contentHeight;

      this.node.size[0] = Math.max(minWidth, Math.min(maxWidth, contentWidth + padding * 2));
      this.node.size[1] = Math.max(minHeight + headerHeight, totalHeight);
    }

    this.setDirtyCanvas();
  }
}
