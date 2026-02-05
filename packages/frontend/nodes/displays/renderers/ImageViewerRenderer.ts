import { LiteGraph } from '@fig-node/litegraph';
import {
  BaseOutputDisplayRenderer,
  type RenderBounds,
  type Point,
} from '../OutputDisplayRenderer';

/**
 * Image viewer renderer with zoom and pan support.
 *
 * Features:
 * - Zoom with shift+scroll
 * - Pan/scroll navigation
 * - Infinite scroll for grid
 * - Aspect ratio preservation
 *
 * Extracted from ImageDisplayNodeUI.ts
 */
export class ImageViewerRenderer extends BaseOutputDisplayRenderer {
  readonly type = 'image-viewer';

  private images: Record<string, string> = {};
  private loadedImages: Map<string, HTMLImageElement> = new Map();
  private imageAspectRatios: Map<string, number> = new Map();

  // View state
  private zoomLevel: number = 1.0;
  private scrollOffsetX: number = 0;
  private scrollOffsetY: number = 0;
  private gridScrollOffset: number = 0;
  private gridScrollOffsetX: number = 0;

  // Cached bounds for event handling
  private lastBounds: RenderBounds | null = null;

  draw(ctx: CanvasRenderingContext2D, bounds: RenderBounds): void {
    if (!ctx || typeof ctx.fillRect !== 'function') return;

    this.lastBounds = bounds;
    const { x, y, width, height } = bounds;
    const labels = Object.keys(this.images);

    // Background
    ctx.fillStyle = LiteGraph.WIDGET_BGCOLOR || '#0f1419';
    ctx.fillRect(x, y, width, height);

    if (!labels.length) {
      ctx.fillStyle = LiteGraph.WIDGET_SECONDARY_TEXT_COLOR || 'rgba(156, 163, 175, 0.4)';
      ctx.font = '12px Arial';
      ctx.textAlign = 'center';
      ctx.textBaseline = 'middle';
      ctx.fillText('No images to display', x + width / 2, y + height / 2);
      return;
    }

    ctx.save();
    ctx.beginPath();
    ctx.rect(x, y, width, height);
    ctx.clip();

    if (labels.length === 1) {
      this.drawSingleImage(ctx, x, y, width, height, labels[0]!);
    } else {
      this.drawImageGrid(ctx, x, y, width, height, labels);
    }

    ctx.restore();
  }

  private drawSingleImage(
    ctx: CanvasRenderingContext2D,
    x: number,
    y: number,
    width: number,
    height: number,
    label: string
  ): void {
    const img = this.loadedImages.get(label);
    if (!img) {
      this.drawLoadingState(ctx, x, y, width, height);
      return;
    }

    const fit = this.fitImageToBounds(img.width, img.height, width, height);
    const zoomedW = fit.width * this.zoomLevel;
    const zoomedH = fit.height * this.zoomLevel;

    const centerX = x + width / 2;
    const centerY = y + height / 2;
    const drawX = centerX - zoomedW / 2;
    const drawY = centerY - zoomedH / 2;

    const maxScrollX = Math.max(0, zoomedW - width);
    const maxScrollY = Math.max(0, zoomedH - height);

    this.scrollOffsetX = Math.max(0, Math.min(maxScrollX, this.scrollOffsetX));
    this.scrollOffsetY = Math.max(0, Math.min(maxScrollY, this.scrollOffsetY));

    ctx.drawImage(
      img,
      drawX - this.scrollOffsetX,
      drawY - this.scrollOffsetY,
      zoomedW,
      zoomedH
    );

    // Draw zoom indicator if zoomed
    if (this.zoomLevel > 1.0) {
      ctx.fillStyle = 'rgba(0, 0, 0, 0.6)';
      ctx.fillRect(x + width - 50, y + 4, 46, 18);
      ctx.fillStyle = '#fff';
      ctx.font = '10px Arial';
      ctx.textAlign = 'center';
      ctx.fillText(`${Math.round(this.zoomLevel * 100)}%`, x + width - 27, y + 16);
    }
  }

  private drawImageGrid(
    ctx: CanvasRenderingContext2D,
    x: number,
    y: number,
    width: number,
    height: number,
    labels: string[]
  ): void {
    const cols = Math.ceil(Math.sqrt(labels.length));
    const rows = Math.ceil(labels.length / cols);
    const cellSpacing = 2;
    const baseCellW = Math.floor((width - (cols - 1) * cellSpacing) / cols);
    const baseCellH = Math.floor((height - (rows - 1) * cellSpacing) / rows);

    // Calculate cell sizes with zoom
    const cellSizes: Array<{ width: number; height: number }> = [];
    let maxCellW = 0;
    let maxCellH = 0;

    for (const label of labels) {
      const img = this.loadedImages.get(label);
      if (!img) continue;

      const fit = this.fitImageToBounds(img.width, img.height, baseCellW, baseCellH);
      const zoomedW = fit.width * this.zoomLevel;
      const zoomedH = fit.height * this.zoomLevel;

      cellSizes.push({ width: zoomedW, height: zoomedH });
      maxCellW = Math.max(maxCellW, zoomedW);
      maxCellH = Math.max(maxCellH, zoomedH);
    }

    const totalGridH = rows * maxCellH + (rows - 1) * cellSpacing;
    const totalGridW = cols * maxCellW + (cols - 1) * cellSpacing;

    const needsVerticalScroll = totalGridH > height;
    const needsHorizontalScroll = totalGridW > width;

    // Apply scroll wrapping for infinite scroll
    if (this.options.infiniteScroll) {
      const scrollableH = needsVerticalScroll ? totalGridH + 50 : totalGridH;
      const scrollableW = needsHorizontalScroll ? totalGridW + 50 : totalGridW;

      if (needsVerticalScroll && scrollableH > 0) {
        this.gridScrollOffset = ((this.gridScrollOffset % scrollableH) + scrollableH) % scrollableH;
      }
      if (needsHorizontalScroll && scrollableW > 0) {
        this.gridScrollOffsetX = ((this.gridScrollOffsetX % scrollableW) + scrollableW) % scrollableW;
      }
    } else {
      this.gridScrollOffset = Math.max(0, Math.min(totalGridH - height, this.gridScrollOffset));
      this.gridScrollOffsetX = Math.max(0, Math.min(totalGridW - width, this.gridScrollOffsetX));
    }

    // Draw grid
    let idx = 0;
    for (let r = 0; r < rows; r++) {
      for (let c = 0; c < cols; c++) {
        if (idx >= labels.length) break;

        const label = labels[idx];
        const img = label ? this.loadedImages.get(label) : undefined;
        const cellSize = cellSizes[idx];

        if (img && cellSize) {
          const cellCenterX = x + c * (maxCellW + cellSpacing) + maxCellW / 2 - this.gridScrollOffsetX;
          const cellCenterY = y + r * (maxCellH + cellSpacing) + maxCellH / 2 - this.gridScrollOffset;
          const drawX = cellCenterX - cellSize.width / 2;
          const drawY = cellCenterY - cellSize.height / 2;

          // Only draw if visible
          if (drawX + cellSize.width >= x && drawX <= x + width &&
              drawY + cellSize.height >= y && drawY <= y + height) {
            ctx.drawImage(img, drawX, drawY, cellSize.width, cellSize.height);
          }
        }

        idx++;
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
    ctx.fillStyle = LiteGraph.WIDGET_SECONDARY_TEXT_COLOR || 'rgba(156, 163, 175, 0.5)';
    ctx.font = '12px Arial';
    ctx.textAlign = 'center';
    ctx.textBaseline = 'middle';
    ctx.fillText('Loading...', x + width / 2, y + height / 2);
  }

  updateFromResult(result: unknown): void {
    const resultObj = result as Record<string, unknown>;
    const imgs = (resultObj?.images as Record<string, string>) ??
                 (typeof result === 'object' ? result as Record<string, string> : {});

    this.images = imgs;
    this.loadedImages.clear();
    this.imageAspectRatios.clear();
    this.resetViewState();

    Object.entries(imgs).forEach(([label, dataUrl]) => {
      if (typeof dataUrl !== 'string') return;

      const img = new Image();
      img.onload = () => {
        this.loadedImages.set(label, img);
        this.imageAspectRatios.set(label, img.width / img.height);
        this.setDirtyCanvas();
      };
      img.src = dataUrl;
    });

    this.setDirtyCanvas();
  }

  private resetViewState(): void {
    this.scrollOffsetX = 0;
    this.scrollOffsetY = 0;
    this.gridScrollOffset = 0;
    this.gridScrollOffsetX = 0;
    this.zoomLevel = 1.0;
  }

  onMouseWheel(event: WheelEvent, pos: Point, _canvas: unknown): boolean {
    if (!this.images || Object.keys(this.images).length === 0) return false;

    const shiftPressed = event.shiftKey;

    // Zoom with shift
    if (shiftPressed && this.options.zoomable !== false) {
      const minZoom = this.options.minZoom ?? 1.0;
      const maxZoom = this.options.maxZoom ?? 5.0;
      const zoomSpeed = event.deltaMode === 0 ? 0.03 : 0.01;
      const zoomDelta = -event.deltaY * zoomSpeed;

      this.zoomLevel = Math.max(minZoom, Math.min(maxZoom, this.zoomLevel + zoomDelta));
      this.setDirtyCanvas();
      return true;
    }

    // Pan/scroll
    if (this.options.pannable !== false) {
      const labels = Object.keys(this.images);

      if (labels.length === 1) {
        // Single image pan
        const isHorizontal = Math.abs(event.deltaX) > Math.abs(event.deltaY);
        const scrollAmount = (isHorizontal ? event.deltaX : event.deltaY) * 0.8;

        if (isHorizontal) {
          this.scrollOffsetX += scrollAmount;
        } else {
          this.scrollOffsetY += scrollAmount;
        }
      } else {
        // Grid scroll
        this.gridScrollOffset += event.deltaY * 1.2;
        this.gridScrollOffsetX += event.deltaX * 1.2;
      }

      this.setDirtyCanvas();
      return true;
    }

    return false;
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
}
