import type { LGraphNode } from '@fig-node/litegraph';
import type { OutputDisplayConfig, OutputDisplayOptions } from '@fig-node/core';

/**
 * Bounds for rendering within a node.
 */
export interface RenderBounds {
  x: number;
  y: number;
  width: number;
  height: number;
}

/**
 * Point coordinates for mouse events.
 */
export interface Point {
  x: number;
  y: number;
}

/**
 * Interface for output display renderers.
 *
 * Output displays handle how execution results are visualized in node bodies.
 * They are separate from input widgets (which handle user input via params_meta).
 *
 * Each renderer type handles a specific kind of output visualization:
 * - text-display: Scrollable text with formatting
 * - image-gallery: Grid of images
 * - image-viewer: Zoomable/pannable images
 * - chart-preview: Mini financial charts
 * - note-display: Colored note display
 */
export interface OutputDisplayRenderer {
  /** Unique type identifier */
  readonly type: string;

  // ============ Lifecycle ============

  /**
   * Initialize the renderer with node and configuration.
   * Called once when the node is created.
   */
  init(node: LGraphNode, config: OutputDisplayConfig): void;

  /**
   * Clean up resources when node is removed.
   */
  destroy(): void;

  // ============ Rendering ============

  /**
   * Draw the output display on the canvas.
   * Called during node's onDrawForeground.
   */
  draw(ctx: CanvasRenderingContext2D, bounds: RenderBounds): void;

  // ============ Data Binding ============

  /**
   * Update display with new execution result.
   * Called when node execution completes.
   */
  updateFromResult(result: unknown): void;

  /**
   * Update display with streaming chunk.
   * Called during streaming execution.
   */
  onStreamUpdate?(chunk: unknown): void;

  // ============ Events (optional) ============

  /**
   * Handle mouse wheel events.
   * Return true if the event was handled (prevents propagation).
   */
  onMouseWheel?(event: WheelEvent, pos: Point, canvas: unknown): boolean;

  /**
   * Handle mouse down events.
   * Return true if the event was handled.
   */
  onMouseDown?(event: MouseEvent, pos: Point, canvas: unknown): boolean;

  /**
   * Handle mouse move events.
   */
  onMouseMove?(event: MouseEvent, pos: Point, canvas: unknown): void;

  /**
   * Handle mouse up events.
   */
  onMouseUp?(event: MouseEvent, pos: Point, canvas: unknown): void;

  /**
   * Handle double-click events.
   * Return true if the event was handled.
   */
  onDblClick?(event: MouseEvent, pos: Point, canvas: unknown): boolean;

  // ============ Node Integration ============

  /**
   * Called when the node is resized.
   * Allows renderer to recalculate layout.
   */
  onResize?(newSize: [number, number]): void;

  /**
   * Get minimum size requirements for this display.
   */
  getMinSize?(): [number, number];

  /**
   * Get preferred size based on content.
   */
  getPreferredSize?(): [number, number];
}

/**
 * Base class for output display renderers.
 * Provides common functionality and default implementations.
 */
export abstract class BaseOutputDisplayRenderer implements OutputDisplayRenderer {
  abstract readonly type: string;

  protected node!: LGraphNode;
  protected config!: OutputDisplayConfig;
  protected options!: OutputDisplayOptions;

  init(node: LGraphNode, config: OutputDisplayConfig): void {
    this.node = node;
    this.config = config;
    this.options = config.options ?? {};
  }

  destroy(): void {
    // Override in subclasses if cleanup is needed
  }

  abstract draw(ctx: CanvasRenderingContext2D, bounds: RenderBounds): void;
  abstract updateFromResult(result: unknown): void;

  /**
   * Helper to trigger canvas redraw.
   */
  protected setDirtyCanvas(): void {
    if (this.node && typeof (this.node as any).setDirtyCanvas === 'function') {
      (this.node as any).setDirtyCanvas(true, true);
    }
  }

  /**
   * Helper to extract bound value from result.
   */
  protected extractBoundValue(result: unknown): unknown {
    if (!this.config.bind || !result) {
      return result;
    }

    const parts = this.config.bind.split('.');
    let value: unknown = result;

    for (const part of parts) {
      if (value === null || value === undefined) return undefined;
      value = (value as Record<string, unknown>)[part];
    }

    return value;
  }
}
