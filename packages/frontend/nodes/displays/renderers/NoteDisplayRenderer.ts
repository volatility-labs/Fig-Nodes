import { LiteGraph } from '@fig-node/litegraph';
import type { OutputDisplayConfig } from '@fig-node/core';
import type { LGraphNode } from '@fig-node/litegraph';
import {
  BaseOutputDisplayRenderer,
  type RenderBounds,
  type Point,
} from '../OutputDisplayRenderer';

/**
 * Note display renderer for sticky-note style nodes.
 *
 * Features:
 * - Uniform color for title and body
 * - Order locking (always in background)
 * - Double-click to edit title
 *
 * Extracted from NoteNodeUI.ts
 */
export class NoteDisplayRenderer extends BaseOutputDisplayRenderer {
  readonly type = 'note-display';

  private originalOrder: number = 0;
  private lockedOrder: number = -10000;

  init(node: LGraphNode, config: OutputDisplayConfig): void {
    super.init(node, config);

    // Apply uniform color
    const color = this.options.uniformColor ?? '#334';
    (node as any).color = color;
    (node as any).bgcolor = color;

    // Lock order to background
    if (this.options.orderLocked !== undefined) {
      this.lockedOrder = this.options.orderLocked;
      this.originalOrder = (node as any).order ?? 0;

      // Override order property with getter/setter
      Object.defineProperty(node, 'order', {
        get: () => this.lockedOrder,
        set: (_value: number) => {
          // Ignore attempts to modify order
        },
        enumerable: true,
        configurable: true,
      });
    }

    // Disable collapse if note-style
    if ((node as any).collapsable !== undefined) {
      (node as any).collapsable = false;
    }
  }

  /**
   * Override background drawing for uniform color.
   * This is called from the node's onDrawBackground.
   */
  drawBackground(ctx: CanvasRenderingContext2D, node: LGraphNode): void {
    const nodeAny = node as any;
    if (nodeAny.flags?.collapsed) return;

    const color = this.options.uniformColor ?? '#334';
    const size = node.size;

    ctx.save();
    ctx.fillStyle = color;
    ctx.beginPath();

    // Rounded rectangle
    const radius = 4;
    ctx.roundRect(0, 0, size[0], size[1], radius);
    ctx.fill();

    // Subtle border
    ctx.strokeStyle = this.lightenColor(color, 0.15);
    ctx.lineWidth = 1;
    ctx.stroke();

    // Draw title text
    ctx.fillStyle = '#ffffff';
    ctx.font = 'bold 14px Arial';
    ctx.textAlign = 'center';
    ctx.textBaseline = 'middle';

    const titleY = (LiteGraph.NODE_TITLE_HEIGHT / 2) - 2;
    const titleX = size[0] / 2;
    ctx.fillText(node.title, titleX, titleY);

    ctx.restore();
  }

  draw(ctx: CanvasRenderingContext2D, bounds: RenderBounds): void {
    // Note display doesn't draw in the content area - it overrides background
    // The actual note text is stored in properties and shown via title
  }

  updateFromResult(_result: unknown): void {
    // Notes don't have execution results
  }

  onDblClick(event: MouseEvent, pos: Point, _canvas: unknown): boolean {
    if (this.options.titleEditable === false) return false;

    // Check if click is in title area
    if (pos.y < LiteGraph.NODE_TITLE_HEIGHT) {
      const currentTitle = this.node.title;
      const newTitle = (LiteGraph as any).prompt?.('Edit Title', currentTitle, { multiline: false });

      if (newTitle !== null && newTitle !== undefined) {
        this.node.title = newTitle;
        // Sync to properties if used
        if ((this.node as any).properties) {
          (this.node as any).properties.text = newTitle;
        }
        this.setDirtyCanvas();
      }
      return true;
    }

    return false;
  }

  destroy(): void {
    // Restore original order behavior if it was locked
    if (this.options.orderLocked !== undefined) {
      Object.defineProperty(this.node, 'order', {
        value: this.originalOrder,
        writable: true,
        enumerable: true,
        configurable: true,
      });
    }
  }

  private lightenColor(color: string, amount: number): string {
    const hex = color.replace('#', '');
    const num = parseInt(hex, 16);
    const r = Math.min(255, ((num >> 16) & 0xFF) + Math.round(255 * amount));
    const g = Math.min(255, ((num >> 8) & 0xFF) + Math.round(255 * amount));
    const b = Math.min(255, (num & 0xFF) + Math.round(255 * amount));
    return `#${((r << 16) | (g << 8) | b).toString(16).padStart(6, '0')}`;
  }
}
