import { LiteGraph } from '@fig-node/litegraph';
import {
  BaseOutputDisplayRenderer,
  type RenderBounds,
  type Point,
} from './OutputDisplayRenderer';

/**
 * Text display renderer for scrollable text output.
 *
 * Features:
 * - Scrollable text content
 * - Format detection (auto/json/plain/markdown)
 * - Copy to clipboard button
 * - Streaming support
 *
 * Extracted from LoggingNodeUI.ts
 */
export class TextDisplayRenderer extends BaseOutputDisplayRenderer {
  readonly type = 'text-display';

  private displayText: string = '';
  private scrollOffset: number = 0;
  private format: 'auto' | 'json' | 'plain' | 'markdown' = 'auto';

  // Copy button state
  private copyButtonBounds: RenderBounds | null = null;
  private copyFeedback: { message: string; success: boolean; timeout: number } | null = null;

  draw(ctx: CanvasRenderingContext2D, bounds: RenderBounds): void {
    const { x, y, width, height } = bounds;

    if (!this.displayText) {
      // Draw placeholder
      ctx.fillStyle = 'rgba(156, 163, 175, 0.4)';
      ctx.font = '12px Arial';
      ctx.textAlign = 'center';
      ctx.textBaseline = 'middle';
      ctx.fillText(
        this.options.placeholder ?? 'No output',
        x + width / 2,
        y + height / 2
      );
      return;
    }

    // Draw copy button if enabled
    if (this.options.copyButton !== false) {
      this.drawCopyButton(ctx, bounds);
    }

    // Adjust content area for copy button
    const contentY = y + (this.options.copyButton !== false ? 28 : 0);
    const contentHeight = height - (this.options.copyButton !== false ? 28 : 0);

    // Clip to content area
    ctx.save();
    ctx.beginPath();
    ctx.rect(x, contentY, width, contentHeight);
    ctx.clip();

    // Draw text with scroll offset
    ctx.font = '12px Arial';
    ctx.fillStyle = LiteGraph.NODE_TEXT_COLOR || '#AAA';
    ctx.textAlign = 'left';
    ctx.textBaseline = 'top';

    const padding = 4;
    const lineHeight = 15;
    const maxWidth = width - padding * 2;
    const lines = this.wrapText(this.displayText, maxWidth, ctx);

    // Calculate total content height for scrolling
    const totalContentHeight = lines.length * lineHeight;
    const maxScroll = Math.max(0, totalContentHeight - contentHeight);
    this.scrollOffset = Math.max(0, Math.min(maxScroll, this.scrollOffset));

    // Draw visible lines
    const startLine = Math.floor(this.scrollOffset / lineHeight);
    const startOffset = this.scrollOffset % lineHeight;

    for (let i = startLine; i < lines.length; i++) {
      const lineY = contentY + (i - startLine) * lineHeight - startOffset + padding;
      if (lineY + lineHeight < contentY) continue;
      if (lineY > contentY + contentHeight) break;

      const line = lines[i];
      if (line !== undefined) {
        ctx.fillText(line, x + padding, lineY);
      }
    }

    ctx.restore();

    // Draw scroll indicator if content overflows
    if (maxScroll > 0) {
      this.drawScrollIndicator(ctx, x + width - 6, contentY, 4, contentHeight, this.scrollOffset / maxScroll);
    }
  }

  private drawCopyButton(ctx: CanvasRenderingContext2D, bounds: RenderBounds): void {
    const btnX = bounds.x + 4;
    const btnY = bounds.y + 4;
    const btnW = 70;
    const btnH = 20;

    this.copyButtonBounds = { x: btnX, y: btnY, width: btnW, height: btnH };

    // Button background
    ctx.fillStyle = 'rgba(59, 130, 246, 0.3)';
    ctx.beginPath();
    ctx.roundRect(btnX, btnY, btnW, btnH, 4);
    ctx.fill();

    // Button text
    ctx.fillStyle = '#fff';
    ctx.font = '11px Arial';
    ctx.textAlign = 'center';
    ctx.textBaseline = 'middle';

    const label = this.copyFeedback
      ? (this.copyFeedback.success ? '✓ Copied' : '✗ Failed')
      : '📋 Copy';
    ctx.fillText(label, btnX + btnW / 2, btnY + btnH / 2);
  }

  private drawScrollIndicator(
    ctx: CanvasRenderingContext2D,
    x: number,
    y: number,
    width: number,
    height: number,
    position: number
  ): void {
    // Track
    ctx.fillStyle = 'rgba(255, 255, 255, 0.1)';
    ctx.fillRect(x, y, width, height);

    // Thumb
    const thumbHeight = Math.max(20, height * 0.2);
    const thumbY = y + (height - thumbHeight) * position;
    ctx.fillStyle = 'rgba(255, 255, 255, 0.3)';
    ctx.fillRect(x, thumbY, width, thumbHeight);
  }

  updateFromResult(result: unknown): void {
    this.displayText = this.formatValue(result);
    this.scrollOffset = 0;
    this.setDirtyCanvas();
  }

  onStreamUpdate(chunk: unknown): void {
    if (!this.options.streaming) {
      this.updateFromResult(chunk);
      return;
    }

    // Handle streaming chunk
    const chunkResult = chunk as { done?: boolean; message?: unknown; output?: unknown };

    if (chunkResult.done) {
      this.displayText = this.formatValue(chunkResult.message ?? chunkResult);
      this.scrollOffset = 0;
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

    this.setDirtyCanvas();
  }

  onMouseWheel(event: WheelEvent, pos: Point, _canvas: unknown): boolean {
    if (!this.displayText) return false;

    // Calculate scroll amount
    let scrollAmount: number;
    if (event.deltaMode === 0) {
      scrollAmount = event.deltaY * 0.8;
    } else if (event.deltaMode === 1) {
      scrollAmount = event.deltaY * 20;
    } else {
      scrollAmount = event.deltaY * 50;
    }

    this.scrollOffset += scrollAmount;
    this.setDirtyCanvas();
    return true;
  }

  onMouseDown(event: MouseEvent, pos: Point, _canvas: unknown): boolean {
    // Check if click is on copy button
    if (this.copyButtonBounds && this.options.copyButton !== false) {
      const { x, y, width, height } = this.copyButtonBounds;
      if (pos.x >= x && pos.x <= x + width && pos.y >= y && pos.y <= y + height) {
        this.copyToClipboard();
        return true;
      }
    }
    return false;
  }

  private copyToClipboard(): void {
    if (!this.displayText.trim()) {
      this.showCopyFeedback('No content', false);
      return;
    }

    navigator.clipboard.writeText(this.displayText).then(() => {
      this.showCopyFeedback('Copied!', true);
    }).catch(() => {
      this.showCopyFeedback('Failed', false);
    });
  }

  private showCopyFeedback(message: string, success: boolean): void {
    if (this.copyFeedback) {
      clearTimeout(this.copyFeedback.timeout);
    }

    const timeout = window.setTimeout(() => {
      this.copyFeedback = null;
      this.setDirtyCanvas();
    }, 2000);

    this.copyFeedback = { message, success, timeout };
    this.setDirtyCanvas();
  }

  destroy(): void {
    if (this.copyFeedback) {
      clearTimeout(this.copyFeedback.timeout);
      this.copyFeedback = null;
    }
  }

  // ============ Formatting ============

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

  // ============ Text Wrapping ============

  private wrapText(text: string, maxWidth: number, ctx: CanvasRenderingContext2D): string[] {
    const lines: string[] = [];
    const paragraphs = text.split('\n');

    for (const paragraph of paragraphs) {
      if (!paragraph) {
        lines.push('');
        continue;
      }

      const words = paragraph.split(' ');
      let currentLine = '';

      for (const word of words) {
        const testLine = currentLine ? `${currentLine} ${word}` : word;
        const metrics = ctx.measureText(testLine);

        if (metrics.width > maxWidth && currentLine) {
          lines.push(currentLine);
          currentLine = word;
        } else {
          currentLine = testLine;
        }
      }

      if (currentLine) {
        lines.push(currentLine);
      }
    }

    return lines;
  }
}
