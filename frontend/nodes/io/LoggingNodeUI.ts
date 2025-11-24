
import BaseCustomNode from '../base/BaseCustomNode';
import { LiteGraph } from '@fig-node/litegraph';
import { NodeRenderer } from '../utils/NodeRenderer';

class LoggingRenderer extends NodeRenderer {
    onDrawForeground(ctx: CanvasRenderingContext2D) {
        const node = this.node as LoggingNodeUI;
        this.drawHighlight(ctx);
        this.drawProgressBar(ctx);
        node.drawContent(ctx);
        this.drawError(ctx);
    }
}

export default class LoggingNodeUI extends BaseCustomNode {
    private copyButton: any = null;
    private copyFeedbackTimeout: number | null = null;
    private scrollOffset: number = 0; // Vertical scroll offset for text content

    constructor(title: string, data: any, serviceRegistry: any) {
        super(title, data, serviceRegistry);

        // Set larger size for displaying log data
        this.size = [400, 300];

        // Disable native canvas text rendering to enable custom scrolling
        this.displayResults = false;

        // Use custom renderer
        (this as any).renderer = new LoggingRenderer(this as any);

        // Add copy button widget
        this.copyButton = this.addWidget('button', '📋 Copy Log', '', () => {
            this.copyLogToClipboard();
        }, {});
    }

    // Override onMouseDown to ensure node can be selected properly
    onMouseDown(event: any, pos: [number, number], canvas: any): boolean {
        return false;
    }

    // Handle mouse wheel events for scrolling
    onMouseWheel(event: WheelEvent, pos: [number, number], canvas: any): boolean {
        const nodeWithFlags = this as { flags?: { collapsed?: boolean }; size: [number, number]; selected?: boolean };
        
        if (nodeWithFlags.flags?.collapsed || !this.displayText) {
            return false;
        }

        const padding = 12;
        const widgetHeight = this.widgets ? this.widgets.length * LiteGraph.NODE_WIDGET_HEIGHT : 0;
        const startY = LiteGraph.NODE_TITLE_HEIGHT + widgetHeight + padding;
        const contentHeight = Math.max(0, nodeWithFlags.size[1] - LiteGraph.NODE_TITLE_HEIGHT - widgetHeight - padding * 2);

        // Check if node is selected (for scrolling when selected)
        const isSelected = nodeWithFlags.selected || (canvas?.selected_nodes && canvas.selected_nodes[this.id]);
        
        // Use very lenient bounds for Mac trackpad
        const boundsMargin = 100;
        const isInScrollBounds = pos[0] >= -boundsMargin && pos[0] <= nodeWithFlags.size[0] + boundsMargin && 
                                 pos[1] >= startY - boundsMargin && pos[1] <= nodeWithFlags.size[1] + boundsMargin;
        
        // Always allow scrolling if node is selected, regardless of mouse position
        if (!isInScrollBounds && !isSelected) {
            return false;
        }

        // Calculate total content height
        const tempCanvas = document.createElement('canvas');
        const tempCtx = tempCanvas.getContext('2d');
        if (!tempCtx) return false;

        tempCtx.font = '12px Arial';
        const maxWidth = nodeWithFlags.size[0] - 20;
        const lines = this.wrapText(this.displayText, maxWidth, tempCtx);
        const totalContentHeight = lines.length * 15;

        // Only allow scrolling if content exceeds visible area
        const maxScroll = Math.max(0, totalContentHeight - contentHeight);
        if (maxScroll <= 0) {
            return false; // No scrolling needed
        }

        // Calculate scroll amount
        let scrollAmount: number;
        if (event.deltaMode === 0) {
            // Pixel mode (trackpad/mouse wheel)
            scrollAmount = event.deltaY * 0.8;
        } else if (event.deltaMode === 1) {
            // Line mode
            scrollAmount = event.deltaY * 20;
        } else {
            // Page mode
            scrollAmount = event.deltaY * contentHeight * 0.1;
        }

        // Apply scrolling (clamp to valid range)
        this.scrollOffset = Math.max(0, Math.min(maxScroll, this.scrollOffset + scrollAmount));

        this.setDirtyCanvas(true, true);
        return true;
    }

    private wrapText(text: string, maxWidth: number, ctx: CanvasRenderingContext2D): string[] {
        if (typeof text !== 'string') return [];
        const lines: string[] = [];
        const paragraphs = text.split('\n');
        for (const p of paragraphs) {
            const words = p.split(' ');
            let currentLine = words[0] || '';
            for (let i = 1; i < words.length; i++) {
                const word = words[i];
                const testLine = currentLine ? `${currentLine} ${word}` : word;
                const testWidth = ctx.measureText(testLine).width;
                
                if (testWidth > maxWidth) {
                    if (currentLine) {
                        lines.push(currentLine);
                        currentLine = '';
                    }
                    
                    const wordWidth = ctx.measureText(word).width;
                    if (wordWidth > maxWidth) {
                        let remainingWord = word;
                        while (remainingWord) {
                            let chunk = '';
                            for (let j = 0; j < remainingWord.length; j++) {
                                const testChunk = chunk + remainingWord[j];
                                if (ctx.measureText(testChunk).width > maxWidth && chunk) {
                                    break;
                                }
                                chunk = testChunk;
                            }
                            if (chunk) {
                                lines.push(chunk);
                                remainingWord = remainingWord.slice(chunk.length);
                            } else {
                                lines.push(remainingWord[0] || '');
                                remainingWord = remainingWord.slice(1);
                            }
                        }
                        currentLine = '';
                    } else {
                        currentLine = word;
                    }
                } else {
                    currentLine = testLine;
                }
            }
            if (currentLine) lines.push(currentLine);
        }
        return lines;
    }

    drawContent(ctx: CanvasRenderingContext2D) {
        const nodeWithFlags = this as { flags?: { collapsed?: boolean }; size: [number, number] };
        if (nodeWithFlags.flags?.collapsed || !this.displayText) {
            return;
        }

        const padding = 12;
        const widgetHeight = this.widgets ? this.widgets.length * LiteGraph.NODE_WIDGET_HEIGHT : 0;
        const x0 = padding;
        const y0 = LiteGraph.NODE_TITLE_HEIGHT + widgetHeight + padding + (this.progress >= 0 ? 9 : 0);
        const w = Math.max(0, nodeWithFlags.size[0] - padding * 2);
        const h = Math.max(0, nodeWithFlags.size[1] - LiteGraph.NODE_TITLE_HEIGHT - widgetHeight - padding * 2 - (this.progress >= 0 ? 9 : 0));

        // Clip to content area
        ctx.save();
        ctx.beginPath();
        ctx.rect(x0, y0, w, h);
        ctx.clip();

        // Wrap text
        ctx.font = '12px Arial';
        const maxWidth = w - padding;
        const lines = this.wrapText(this.displayText, maxWidth, ctx);

        // Draw text with scroll offset
        ctx.fillStyle = '#ffffff';
        ctx.textAlign = 'left';
        ctx.textBaseline = 'top';

        const lineHeight = 15;
        const startLine = Math.floor(this.scrollOffset / lineHeight);
        const startOffset = this.scrollOffset % lineHeight;

        for (let i = startLine; i < lines.length; i++) {
            const y = y0 + (i - startLine) * lineHeight - startOffset;
            // Only draw lines that are visible
            if (y + lineHeight < y0) continue;
            if (y > y0 + h) break;
            ctx.fillText(lines[i], x0, y);
        }

        ctx.restore();
    }

    private copyLogToClipboard() {
        const textToCopy = this.displayText || '';
        if (!textToCopy.trim()) {
            this.showCopyFeedback('No content to copy', false);
            return;
        }

        navigator.clipboard.writeText(textToCopy).then(() => {
            this.showCopyFeedback('Copied to clipboard!', true);
        }).catch((err) => {
            console.error('Failed to copy text: ', err);
            this.showCopyFeedback('Copy failed', false);
        });
    }

    private showCopyFeedback(message: string, success: boolean) {
        if (this.copyButton) {
            const originalText = this.copyButton.name;
            this.copyButton.name = success ? '✅ ' + message : '❌ ' + message;

            if (this.copyFeedbackTimeout) {
                clearTimeout(this.copyFeedbackTimeout);
            }

            this.copyFeedbackTimeout = window.setTimeout(() => {
                this.copyButton.name = originalText;
                this.copyFeedbackTimeout = null;
                this.setDirtyCanvas(true, true);
            }, 2000);

            this.setDirtyCanvas(true, true);
        }
    }

    private getSelectedFormat(): 'auto' | 'plain' | 'json' | 'markdown' {
        const fmt = (this.properties && this.properties['format']) || 'auto';
        if (fmt === 'plain' || fmt === 'json' || fmt === 'markdown') return fmt;
        return 'auto';
    }

    private tryFormat(value: any): string {
        const format = this.getSelectedFormat();
        let candidate: any = value;
        if (candidate && typeof candidate === 'object' && 'output' in candidate) {
            candidate = (candidate as { output: any }).output;
        }

        const stringifyPretty = (v: any) => {
            try { return JSON.stringify(v, null, 2); } catch { return String(v); }
        };

        if (value && typeof value === 'object' && 'role' in value && 'content' in value) {
            let text = this.tryFormat(value.content);
            if ('thinking' in value && value.thinking && format !== 'plain') {
                text += '\n\nThinking: ' + this.tryFormat(value.thinking);
            }
            return text;
        }

        if (value && typeof value === 'object' && 'content' in value && Object.keys(value).length === 1) {
            return this.tryFormat(value.content);
        }

        if (format === 'plain') {
            if (typeof candidate === 'string') return candidate;
            return stringifyPretty(candidate);
        }

        if (format === 'json') {
            if (typeof candidate === 'string') {
                try { return stringifyPretty(JSON.parse(candidate)); } catch { return candidate; }
            }
            return stringifyPretty(candidate);
        }

        if (format === 'markdown') {
            if (typeof candidate === 'string') return candidate;
            return stringifyPretty(candidate);
        }

        if (typeof candidate === 'string') {
            const trimmed = candidate.trim();
            if ((trimmed.startsWith('{') && trimmed.endsWith('}')) || (trimmed.startsWith('[') && trimmed.endsWith(']'))) {
                try { return stringifyPretty(JSON.parse(candidate)); } catch { /* ignore */ }
            }
            return candidate;
        }
        return stringifyPretty(candidate);
    }

    reset() {
        this.displayText = '';
        this.scrollOffset = 0; // Reset scroll when clearing
        this.setDirtyCanvas(true, true);
    }

    updateDisplay(result: any) {
        console.log('LoggingNodeUI.updateDisplay called with:', result);
        // If streaming-style payload, avoid replacing accumulated text
        if (result && (
            typeof (result as { assistant_text?: string }).assistant_text === 'string' ||
            ((result as { assistant_message?: { content?: string } }).assistant_message && typeof (result as { assistant_message: { content: string } }).assistant_message.content === 'string') ||
            ((result as { message?: { content?: string } }).message && typeof (result as { message: { content: string } }).message.content === 'string')
        )) {
            return;
        }
        const formatted = this.tryFormat(result);
        this.displayText = formatted;
        this.scrollOffset = 0; // Reset scroll when new content is loaded
        console.log('displayText set to:', this.displayText);
        this.setDirtyCanvas(true, true);
    }

    onStreamUpdate(result: any) {
        let chunk: string = '';
        const format = this.getSelectedFormat();

        if (result.done) {
            this.displayText = this.tryFormat(result.message || result);
            this.scrollOffset = 0; // Reset scroll when stream completes
        } else {
            const candidate = (result.output || result);
            if (typeof candidate === 'string') {
                chunk = candidate;
            } else if (candidate && candidate.message && typeof candidate.message.content === 'string') {
                chunk = candidate.message.content;
            } else {
                try { chunk = JSON.stringify(candidate); } catch { chunk = String(candidate ?? ''); }
            }

            const prev = this.displayText || '';

            if (prev && chunk.startsWith(prev)) {
                this.displayText = chunk;
            } else {
                if (format === 'json') {
                    try {
                        const parsed = JSON.parse(chunk);
                        this.displayText = JSON.stringify(parsed, null, 2);
                    } catch {
                        this.displayText = chunk;
                    }
                } else if (format === 'auto') {
                    const trimmed = chunk.trim();
                    if ((trimmed.startsWith('{') && trimmed.endsWith('}')) || (trimmed.startsWith('[') && trimmed.endsWith(']'))) {
                        try {
                            const parsed = JSON.parse(chunk);
                            this.displayText = JSON.stringify(parsed, null, 2);
                        } catch {
                            this.displayText = chunk;
                        }
                    } else {
                        this.displayText = chunk;
                    }
                } else {
                    this.displayText = chunk;
                }
            }
        }
        this.setDirtyCanvas(true, true);
    }

    // Clean up timeouts when node is destroyed
    onRemoved() {
        if (this.copyFeedbackTimeout) {
            clearTimeout(this.copyFeedbackTimeout);
            this.copyFeedbackTimeout = null;
        }
        super.onRemoved?.();
    }
}
