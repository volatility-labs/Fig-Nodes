
import BaseCustomNode from '../base/BaseCustomNode';
import { LiteGraph } from '@comfyorg/litegraph';

export default class LoggingNodeUI extends BaseCustomNode {
    private copyButton: any = null;
    private copyFeedbackTimeout: number | null = null;
    private scrollOffset: number = 0;
    private maxVisibleHeight: number = 400; // Maximum visible height in pixels
    private lineHeight: number = 15;

    constructor(title: string, data: any, serviceRegistry: any) {
        super(title, data, serviceRegistry);

        // Set larger size for displaying log data
        this.size = [400, 300];

        // Enable native canvas text rendering
        this.displayResults = true;

        // Add copy button widget
        this.copyButton = this.addWidget('button', '📋 Copy Log', '', () => {
            this.copyLogToClipboard();
        }, {});
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

            // Clear any existing timeout
            if (this.copyFeedbackTimeout) {
                clearTimeout(this.copyFeedbackTimeout);
            }

            // Reset button text after 2 seconds
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
        // Normalize candidate into a string or object first
        let candidate: any = value;
        if (candidate && typeof candidate === 'object' && 'output' in candidate) {
            candidate = (candidate as { output: any }).output;
        }

        // Helper to stringify objects consistently
        const stringifyPretty = (v: any) => {
            try { return JSON.stringify(v, null, 2); } catch { return String(v); }
        };

        // Handle LLMChatMessage - extract only the content
        if (value && typeof value === 'object' && 'role' in value && 'content' in value) {
            // This is an LLMChatMessage - extract only the content
            let text = this.tryFormat(value.content);
            // Optionally include thinking if present and format is not 'plain'
            if ('thinking' in value && value.thinking && format !== 'plain') {
                text += '\n\nThinking: ' + this.tryFormat(value.thinking);
            }
            return text;
        }

        // Handle simple objects with content property (like streaming messages)
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
            // We do not render markdown; we preserve text for canvas display.
            if (typeof candidate === 'string') return candidate;
            return stringifyPretty(candidate);
        }

        // auto: try JSON parse when string looks like JSON, else fallback to string/pretty
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
        this.scrollOffset = 0;
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
        console.log('displayText set to:', this.displayText);
        // Reset scroll to top when new content arrives
        this.scrollOffset = 0;
        this.setDirtyCanvas(true, true);
    }

    onStreamUpdate(result: any) {
        let chunk: string = '';
        const format = this.getSelectedFormat();

        // Check if we're at the bottom before updating
        const wasAtBottom = this.isAtBottom();

        if (result.done) {
            // For final, format the full message
            this.displayText = this.tryFormat(result.message || result);
        } else {
            // Extract chunk for partial
            const candidate = (result.output || result);
            if (typeof candidate === 'string') {
                chunk = candidate;
            } else if (candidate && candidate.message && typeof candidate.message.content === 'string') {
                chunk = candidate.message.content;
            } else {
                try { chunk = JSON.stringify(candidate); } catch { chunk = String(candidate ?? ''); }
            }

            const prev = this.displayText || '';

            // If chunk starts with prev, it's cumulative; otherwise replace
            if (prev && chunk.startsWith(prev)) {
                this.displayText = chunk;  // Replace with cumulative chunk
            } else {
                // Not cumulative, so use the chunk as-is (possibly formatted)
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

        // Auto-scroll to bottom if user was already at bottom
        if (wasAtBottom) {
            this.scrollToBottom();
        }

        this.setDirtyCanvas(true, true);
    }

    private isAtBottom(): boolean {
        const nodeWithFlags = this as { flags?: { collapsed?: boolean }; size: [number, number] };
        if (!this.displayText) return true;

        const tempCanvas = document.createElement('canvas');
        const tempCtx = tempCanvas.getContext('2d');
        if (!tempCtx) return true;

        tempCtx.font = '12px Arial';
        const lines = this.wrapText(this.displayText, nodeWithFlags.size[0] - 20, tempCtx);
        const totalContentHeight = lines.length * this.lineHeight;

        const startY = LiteGraph.NODE_TITLE_HEIGHT + 4 + (this.progress >= 0 ? 9 : 0) + 
                       (this.widgets ? this.widgets.length * LiteGraph.NODE_WIDGET_HEIGHT : 0) + 10;
        const contentAreaHeight = nodeWithFlags.size[1] - startY - 10;
        const maxScroll = Math.max(0, totalContentHeight - contentAreaHeight);

        // Consider at bottom if within 5 pixels of bottom
        return Math.abs(this.scrollOffset - maxScroll) < 5;
    }

    private scrollToBottom() {
        const nodeWithFlags = this as { flags?: { collapsed?: boolean }; size: [number, number] };
        if (!this.displayText) return;

        const tempCanvas = document.createElement('canvas');
        const tempCtx = tempCanvas.getContext('2d');
        if (!tempCtx) return;

        tempCtx.font = '12px Arial';
        const lines = this.wrapText(this.displayText, nodeWithFlags.size[0] - 20, tempCtx);
        const totalContentHeight = lines.length * this.lineHeight;

        const startY = LiteGraph.NODE_TITLE_HEIGHT + 4 + (this.progress >= 0 ? 9 : 0) + 
                       (this.widgets ? this.widgets.length * LiteGraph.NODE_WIDGET_HEIGHT : 0) + 10;
        const contentAreaHeight = nodeWithFlags.size[1] - startY - 10;
        const maxScroll = Math.max(0, totalContentHeight - contentAreaHeight);

        this.scrollOffset = maxScroll;
    }

    // Clean up timeouts when node is destroyed
    onRemoved() {
        if (this.copyFeedbackTimeout) {
            clearTimeout(this.copyFeedbackTimeout);
            this.copyFeedbackTimeout = null;
        }
        super.onRemoved?.();
    }

    // Override onDrawForeground to add scrolling support
    onDrawForeground(ctx: CanvasRenderingContext2D) {
        // Draw progress bar and highlight first
        this.drawProgressBar(ctx);
        this.renderer['drawHighlight'](ctx);
        
        // Draw scrollable content
        this.drawScrollableContent(ctx);
        
        // Draw error if any
        this.renderer['drawError'](ctx);
    }

    private drawScrollableContent(ctx: CanvasRenderingContext2D) {
        const nodeWithFlags = this as { flags?: { collapsed?: boolean }; size: [number, number] };
        if (nodeWithFlags.flags?.collapsed || !this.displayResults || !this.displayText) {
            return;
        }

        const maxWidth = nodeWithFlags.size[0] - 20;

        // Create temp canvas for text measurement
        const tempCanvas = document.createElement('canvas');
        const tempCtx = tempCanvas.getContext('2d');
        if (!tempCtx) return;

        tempCtx.font = '12px Arial';
        const lines = this.wrapText(this.displayText, maxWidth, tempCtx);

        // Calculate starting Y position (after title, progress bar, widgets)
        let startY = LiteGraph.NODE_TITLE_HEIGHT + 4 + (this.progress >= 0 ? 9 : 0);
        if (this.widgets) {
            startY += this.widgets.length * LiteGraph.NODE_WIDGET_HEIGHT;
        }
        startY += 10; // Padding

        // Calculate visible area
        const nodeHeight = nodeWithFlags.size[1];
        const contentAreaHeight = nodeHeight - startY - 10; // 10px bottom padding
        const maxVisibleLines = Math.floor(contentAreaHeight / this.lineHeight);

        // Calculate total content height
        const totalContentHeight = lines.length * this.lineHeight;
        
        // Clamp scroll offset
        const maxScroll = Math.max(0, totalContentHeight - contentAreaHeight);
        this.scrollOffset = Math.max(0, Math.min(maxScroll, this.scrollOffset));

        // Calculate which lines to draw
        const startLine = Math.floor(this.scrollOffset / this.lineHeight);
        const endLine = Math.min(lines.length, startLine + maxVisibleLines + 1); // +1 for partial line

        // Set fixed node height if content exceeds visible area
        if (totalContentHeight > contentAreaHeight) {
            const fixedHeight = startY + contentAreaHeight + 10;
            if (Math.abs(nodeWithFlags.size[1] - fixedHeight) > 1) {
                nodeWithFlags.size[1] = fixedHeight;
                this.setDirtyCanvas(true, true);
                return; // Redraw with new size
            }
        } else {
            // Auto-size if content fits
            const neededHeight = startY + totalContentHeight + 10;
            if (Math.abs(nodeWithFlags.size[1] - neededHeight) > 1) {
                nodeWithFlags.size[1] = neededHeight;
                this.setDirtyCanvas(true, true);
                return;
            }
        }

        // Draw visible lines
        ctx.font = '12px Arial';
        ctx.fillStyle = '#ffffff';
        ctx.textAlign = 'left';
        ctx.textBaseline = 'top';

        // Clip to content area
        ctx.save();
        ctx.beginPath();
        ctx.rect(10, startY, maxWidth, contentAreaHeight);
        ctx.clip();

        // Calculate Y offset for partial line scrolling
        const lineOffset = (this.scrollOffset % this.lineHeight) / this.lineHeight;
        const yOffset = -lineOffset * this.lineHeight;

        for (let i = startLine; i < endLine; i++) {
            const lineY = startY + (i - startLine) * this.lineHeight + yOffset;
            ctx.fillText(lines[i], 10, lineY);
        }

        ctx.restore();

        // Draw scrollbar if content exceeds visible area
        if (totalContentHeight > contentAreaHeight) {
            this.drawScrollbar(ctx, nodeWithFlags.size[0], startY, contentAreaHeight, totalContentHeight);
        }
    }

    private drawScrollbar(ctx: CanvasRenderingContext2D, nodeWidth: number, startY: number, visibleHeight: number, totalHeight: number) {
        const scrollbarWidth = 8;
        const scrollbarX = nodeWidth - scrollbarWidth - 2;
        const scrollbarHeight = visibleHeight;
        
        // Scrollbar track
        ctx.fillStyle = 'rgba(100, 100, 100, 0.3)';
        ctx.fillRect(scrollbarX, startY, scrollbarWidth, scrollbarHeight);

        // Scrollbar thumb
        const maxScroll = Math.max(0, totalHeight - visibleHeight);
        if (maxScroll <= 0) return; // No scrolling needed
        
        const thumbHeight = Math.max(20, (visibleHeight / totalHeight) * scrollbarHeight);
        const scrollRatio = maxScroll > 0 ? this.scrollOffset / maxScroll : 0;
        const thumbY = startY + scrollRatio * (scrollbarHeight - thumbHeight);
        
        ctx.fillStyle = 'rgba(150, 150, 150, 0.7)';
        ctx.fillRect(scrollbarX, thumbY, scrollbarWidth, thumbHeight);
    }

    // Handle mouse wheel events for scrolling (works with both mouse and trackpad)
    onMouseWheel(event: WheelEvent, pos: [number, number], canvas: any): boolean {
        const nodeWithFlags = this as { flags?: { collapsed?: boolean }; size: [number, number] };
        if (nodeWithFlags.flags?.collapsed || !this.displayResults || !this.displayText) {
            return false;
        }

        // Check if mouse is over the content area
        const startY = LiteGraph.NODE_TITLE_HEIGHT + 4 + (this.progress >= 0 ? 9 : 0) + 
                       (this.widgets ? this.widgets.length * LiteGraph.NODE_WIDGET_HEIGHT : 0) + 10;
        const contentAreaHeight = nodeWithFlags.size[1] - startY - 10;

        // Check if mouse is within node bounds
        if (pos[0] < 0 || pos[0] > nodeWithFlags.size[0] || pos[1] < startY || pos[1] > nodeWithFlags.size[1]) {
            return false;
        }

        // Calculate total content height
        const tempCanvas = document.createElement('canvas');
        const tempCtx = tempCanvas.getContext('2d');
        if (!tempCtx) return false;
        
        tempCtx.font = '12px Arial';
        const lines = this.wrapText(this.displayText, nodeWithFlags.size[0] - 20, tempCtx);
        const totalContentHeight = lines.length * this.lineHeight;
        const maxScroll = Math.max(0, totalContentHeight - contentAreaHeight);
        
        if (maxScroll <= 0) return false; // No scrolling needed

        // Handle different delta modes (pixel, line, page)
        // Trackpads typically use deltaMode = 0 (pixels), mouse wheels use deltaMode = 1 (lines)
        let scrollAmount: number;
        if (event.deltaMode === 0) {
            // Pixel mode (trackpad) - use deltaY directly with slight scaling
            scrollAmount = event.deltaY * 0.8;
        } else if (event.deltaMode === 1) {
            // Line mode (mouse wheel) - convert to pixels
            scrollAmount = event.deltaY * this.lineHeight;
        } else {
            // Page mode - scroll by page height
            scrollAmount = event.deltaY * contentAreaHeight;
        }

        this.scrollOffset = Math.max(0, Math.min(maxScroll, this.scrollOffset + scrollAmount));

        this.setDirtyCanvas(true, true);
        return true; // Event handled
    }
}