import type { LGraphNode } from '@fig-node/litegraph';
import type { OutputDisplayConfig } from '@fig-node/core';
import {
  BaseOutputDisplayRenderer,
  type RenderBounds,
} from './OutputDisplayRenderer';

/**
 * DOM-based text display renderer with native text selection.
 *
 * Unlike TextDisplayRenderer which draws to canvas, this renderer
 * uses an HTML element that overlays the canvas, allowing users
 * to select and copy text natively.
 *
 * Features:
 * - Native text selection and copy (Cmd/Ctrl+C)
 * - Scrollable content
 * - Format detection (auto/json/plain/markdown)
 * - Streaming support
 */
export class DOMTextDisplayRenderer extends BaseOutputDisplayRenderer {
  readonly type = 'text-display-dom';

  private displayText: string = '';
  private format: 'auto' | 'json' | 'plain' | 'markdown' = 'auto';
  private element: HTMLDivElement | null = null;
  private attached: boolean = false;
  private lastBounds: RenderBounds | null = null;

  override init(node: LGraphNode, config: OutputDisplayConfig): void {
    super.init(node, config);
    this.createDOMElement();
  }

  private createDOMElement(): void {
    const el = document.createElement('div');
    el.className = 'fignode-text-display';

    // Essential positioning styles (CSS handles visual styling)
    Object.assign(el.style, {
      position: 'absolute',
      display: 'none', // Hidden until positioned
      zIndex: '100',
    });

    // Placeholder for CSS ::before pseudo-element
    el.dataset.placeholder = this.options.placeholder ?? 'Logs appear here...';

    this.element = el;
  }

  private attachToCanvas(): void {
    if (this.attached || !this.element) return;

    // Find canvas container
    const graph = (this.node as any).graph;
    if (!graph) return;

    // Get the canvas element from the graph's list_of_graphcanvas
    const canvasList = graph.list_of_graphcanvas;
    if (!canvasList || canvasList.length === 0) return;

    const lgCanvas = canvasList[0];
    const canvas = lgCanvas?.canvas;
    if (!canvas) return;

    const container = canvas.parentElement;
    if (!container) return;

    // Ensure container has position for absolute children
    if (getComputedStyle(container).position === 'static') {
      container.style.position = 'relative';
    }

    container.appendChild(this.element);
    this.attached = true;
  }

  override destroy(): void {
    if (this.element) {
      this.element.remove();
      this.element = null;
    }
    this.attached = false;
  }

  /**
   * Position the DOM element to match the canvas bounds.
   * Called during draw() to keep element synchronized with node position.
   */
  draw(_ctx: CanvasRenderingContext2D, bounds: RenderBounds): void {
    if (!this.element) return;

    // Lazy attach to canvas container
    if (!this.attached) {
      this.attachToCanvas();
    }

    if (!this.attached) return;

    this.lastBounds = bounds;
    this.positionElement(bounds);
    this.updateContent();
  }

  private positionElement(bounds: RenderBounds): void {
    if (!this.element) return;

    // Get canvas and transform info
    const graph = (this.node as any).graph;
    if (!graph) return;

    const canvasList = graph.list_of_graphcanvas;
    if (!canvasList || canvasList.length === 0) return;

    const lgCanvas = canvasList[0];
    const canvas = lgCanvas?.canvas;
    if (!canvas) return;

    const container = canvas.parentElement;
    if (!container) return;

    const scale = lgCanvas.ds?.scale ?? 1;
    const offset = lgCanvas.ds?.offset ?? [0, 0];
    const nodePos = this.node.pos;

    const canvasRect = canvas.getBoundingClientRect();
    const containerRect = container.getBoundingClientRect();

    // Transform to screen coords
    const screenX = (nodePos[0] + bounds.x + offset[0]) * scale;
    const screenY = (nodePos[1] + bounds.y + offset[1]) * scale;
    const screenW = bounds.width * scale;
    const screenH = bounds.height * scale;

    // Position relative to container
    const relativeX = canvasRect.left - containerRect.left + screenX;
    const relativeY = canvasRect.top - containerRect.top + screenY;

    // Check visibility
    const isNodeVisible = lgCanvas.isNodeVisible?.(this.node) ?? true;
    const isCollapsed = this.node.flags?.collapsed ?? false;
    const zoomThreshold = 0.5;
    const isLowQuality = scale < zoomThreshold;

    if (!isNodeVisible || isCollapsed || isLowQuality ||
        screenW <= 2 || screenH <= 2 ||
        relativeX + screenW < 0 || relativeY + screenH < 0 ||
        relativeX > containerRect.width || relativeY > containerRect.height) {
      this.element.style.display = 'none';
      return;
    }

    this.element.style.display = '';
    this.element.style.left = `${relativeX}px`;
    this.element.style.top = `${relativeY}px`;
    this.element.style.width = `${Math.max(0, screenW)}px`;
    this.element.style.height = `${Math.max(0, screenH)}px`;
    this.element.style.fontSize = `${12 * scale}px`;
  }

  private updateContent(): void {
    if (!this.element) return;

    if (!this.displayText) {
      this.element.textContent = '';
      this.element.style.color = 'rgba(156, 163, 175, 0.6)';
      this.element.textContent = this.element.dataset.placeholder ?? '';
    } else {
      this.element.style.color = '#e0e0e0';
      this.element.textContent = this.displayText;
    }
  }

  updateFromResult(result: unknown): void {
    this.displayText = this.formatValue(result);
    this.updateContent();
    this.setDirtyCanvas();
  }

  onStreamUpdate(chunk: unknown): void {
    if (!this.options.streaming) {
      this.updateFromResult(chunk);
      return;
    }

    const chunkResult = chunk as { done?: boolean; message?: unknown; output?: unknown };

    if (chunkResult.done) {
      this.displayText = this.formatValue(chunkResult.message ?? chunkResult);
    } else {
      const candidate = chunkResult.output ?? chunk;
      let text: string;

      if (typeof candidate === 'string') {
        text = candidate;
      } else if (candidate && typeof candidate === 'object' && 'message' in candidate) {
        const msg = (candidate as { message?: { content?: string } }).message;
        text = typeof msg?.content === 'string' ? msg.content : JSON.stringify(candidate);
      } else {
        text = JSON.stringify(candidate);
      }

      // Check if this is incremental update or replacement
      if (this.displayText && text.startsWith(this.displayText)) {
        this.displayText = text;
      } else {
        this.displayText = this.autoFormat(text);
      }
    }

    this.updateContent();
    this.setDirtyCanvas();
  }

  // ============ Formatting (same as TextDisplayRenderer) ============

  private formatValue(value: unknown): string {
    const format = this.options.defaultFormat ?? this.format;

    // Unwrap common wrapper patterns
    let candidate = value;
    if (candidate && typeof candidate === 'object' && 'output' in candidate) {
      candidate = (candidate as { output: unknown }).output;
    }

    // Handle LLM message format
    if (value && typeof value === 'object' && 'role' in value && 'content' in value) {
      let text = this.formatValue((value as { content: unknown }).content);
      if ('thinking' in value && (value as { thinking?: string }).thinking && format !== 'plain') {
        text += '\n\nThinking: ' + this.formatValue((value as { thinking: string }).thinking);
      }
      return text;
    }

    // Handle content-only wrapper
    if (value && typeof value === 'object' && 'content' in value && Object.keys(value).length === 1) {
      return this.formatValue((value as { content: unknown }).content);
    }

    switch (format) {
      case 'plain':
        return typeof candidate === 'string' ? candidate : this.stringify(candidate);

      case 'json':
        if (typeof candidate === 'string') {
          try {
            return this.stringify(JSON.parse(candidate));
          } catch {
            return candidate;
          }
        }
        return this.stringify(candidate);

      case 'markdown':
        return typeof candidate === 'string' ? candidate : this.stringify(candidate);

      case 'auto':
      default:
        return this.autoFormat(candidate);
    }
  }

  private autoFormat(value: unknown): string {
    if (typeof value === 'string') {
      const trimmed = value.trim();
      if ((trimmed.startsWith('{') && trimmed.endsWith('}')) ||
          (trimmed.startsWith('[') && trimmed.endsWith(']'))) {
        try {
          return this.stringify(JSON.parse(value));
        } catch {
          return value;
        }
      }
      return value;
    }
    return this.stringify(value);
  }

  private stringify(value: unknown): string {
    try {
      return JSON.stringify(value, null, 2);
    } catch {
      return String(value);
    }
  }
}
