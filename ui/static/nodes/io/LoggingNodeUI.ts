
import BaseCustomNode from '../base/BaseCustomNode';
import { NodeRenderer } from '../utils/NodeRenderer';
import { LiteGraph } from '@comfyorg/litegraph';

class LoggingNodeRenderer extends NodeRenderer {
    onDrawForeground(ctx: CanvasRenderingContext2D) {
        // Call the node's custom drawing logic first
        const loggingNode = this.node as LoggingNodeUI;
        loggingNode.drawLoggingContent(ctx);

        // Then call the standard renderer for highlights, progress, etc.
        this.drawHighlight(ctx);
        this.drawProgressBar(ctx);
        this.drawError(ctx);
    }
}

export default class LoggingNodeUI extends BaseCustomNode {
    private copyButton: any = null;
    private copyFeedbackTimeout: number | null = null;
    private displayTextarea: HTMLTextAreaElement | null = null;
    private lastCanvasRef: any = null;
    private positionUpdateId: number | null = null;

    constructor(title: string, data: any, serviceRegistry: any) {
        super(title, data, serviceRegistry);

        // Use custom renderer for logging-specific drawing
        this.renderer = new LoggingNodeRenderer(this);

        // Set larger size for displaying log data
        this.size = [400, 300];

        // Disable canvas text rendering - we'll use HTML overlay
        this.displayResults = false;

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
        this.syncDisplayTextarea();
        this.setDirtyCanvas(true, true);
    }

    // Lifecycle methods for textarea management
    onAdded() { this.ensureDisplayTextarea(); }
    onDeselected() { this.syncDisplayTextarea(); }
    onResize(_size: [number, number]) { this.syncDisplayTextarea(); this.setDirtyCanvas(true, true); }

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
        this.syncDisplayTextarea();
        this.setDirtyCanvas(true, true);
    }

    onStreamUpdate(result: any) {
        let chunk: string = '';
        const format = this.getSelectedFormat();

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
        this.syncDisplayTextarea();
        this.setDirtyCanvas(true, true);
    }

    drawLoggingContent(ctx: CanvasRenderingContext2D) {
        if (this.flags?.collapsed) {
            this.hideDisplayTextarea();
            return;
        }

        const padding = 8;
        const x = padding;
        const widgetHeight = this.widgets ? this.widgets.length * LiteGraph.NODE_WIDGET_HEIGHT : 0;
        const y = LiteGraph.NODE_TITLE_HEIGHT + widgetHeight + padding;
        const w = Math.max(0, this.size[0] - padding * 2);
        const h = Math.max(0, this.size[1] - LiteGraph.NODE_TITLE_HEIGHT - widgetHeight - padding * 2);

        // Background (will be fully covered by textarea but keeps a fallback look)
        ctx.fillStyle = '#2a2a2a';
        ctx.fillRect(x, y, w, h);

        // Border to match app theme
        ctx.strokeStyle = '#555';
        ctx.lineWidth = 1;
        ctx.strokeRect(x + 0.5, y + 0.5, w - 1, h - 1);

        // Schedule position update instead of doing it synchronously
        this.schedulePositionUpdate(x, y, w, h);
    }

    private schedulePositionUpdate(x: number, y: number, w: number, h: number) {
        if (this.positionUpdateId !== null) return;
        
        this.positionUpdateId = requestAnimationFrame(() => {
            this.positionUpdateId = null;
            this.ensureDisplayTextarea();
            this.positionDisplayTextarea(x, y, w, h);
        });
    }

    private ensureDisplayTextarea() {
        const graph = this.graph;
        if (!graph) return;
        const canvas = graph.list_of_graphcanvas && graph.list_of_graphcanvas[0];
        if (!canvas || !canvas.canvas) return;

        if (!this.displayTextarea || this.lastCanvasRef !== canvas) {
            this.detachDisplayTextarea();
            this.lastCanvasRef = canvas;
            const parent = document.body;
            const ta = document.createElement('textarea');
            ta.className = 'inline-node-textarea monospace';
            ta.readOnly = true; // Make it read-only for display
            ta.spellcheck = false;
            ta.value = this.displayText || '';
            ta.style.resize = 'none'; // Prevent manual resizing
            ta.style.overflowY = 'auto'; // Allow scrolling for long content
            parent.appendChild(ta);
            this.displayTextarea = ta;
        }
        // Don't call syncDisplayTextarea() here - let schedulePositionUpdate handle positioning
    }

    private detachDisplayTextarea() {
        if (this.displayTextarea && this.displayTextarea.parentElement) {
            this.displayTextarea.parentElement.removeChild(this.displayTextarea);
        }
        this.displayTextarea = null;
        this.lastCanvasRef = null;
    }

    private hideDisplayTextarea() {
        if (this.displayTextarea) {
            this.displayTextarea.style.display = 'none';
        }
    }

    private syncDisplayTextarea() {
        if (!this.displayTextarea) return;
        this.displayTextarea.style.display = '';
        const current = this.displayText || '';
        if (this.displayTextarea.value !== current) {
            this.displayTextarea.value = current;
            // Auto-scroll to bottom for log-like behavior
            this.displayTextarea.scrollTop = this.displayTextarea.scrollHeight;
        }
        // Ensure position up-to-date
        const padding = 8;
        const x = padding;
        const widgetHeight = this.widgets ? this.widgets.length * LiteGraph.NODE_WIDGET_HEIGHT : 0;
        const y = LiteGraph.NODE_TITLE_HEIGHT + widgetHeight + padding;
        const w = Math.max(0, this.size[0] - padding * 2);
        const h = Math.max(0, this.size[1] - LiteGraph.NODE_TITLE_HEIGHT - widgetHeight - padding * 2);
        this.positionDisplayTextarea(x, y, w, h);
    }

    private positionDisplayTextarea(localX: number, localY: number, localW: number, localH: number) {
        if (!this.displayTextarea) return;
        const graph = this.graph;
        const canvas = graph && graph.list_of_graphcanvas && graph.list_of_graphcanvas[0];
        if (!canvas || !canvas.canvas) return;

        // Get canvas transform from LiteGraph's internal state
        const scale = canvas.ds?.scale || canvas.scale || 1;
        const offset = canvas.ds?.offset || canvas.offset || [0, 0];
        const offx = Array.isArray(offset) ? offset[0] : 0;
        const offy = Array.isArray(offset) ? offset[1] : 0;

        // Snapshot position to avoid race conditions
        const nodePos = [...this.pos] as [number, number];

        // Convert canvas coordinates to screen coordinates: (pos + offset) * scale
        const canvasX = (nodePos[0] + localX + offx) * scale;
        const canvasY = (nodePos[1] + localY + offy) * scale;
        const canvasW = localW * scale;
        const canvasH = localH * scale;

        // Get canvas element position on screen
        const canvasRect = canvas.canvas.getBoundingClientRect();

        // Calculate screen position relative to document body
        const screenX = canvasRect.left + canvasX;
        const screenY = canvasRect.top + canvasY;

        // Position relative to document body for proper overlay
        const style = this.displayTextarea.style;
        style.position = 'absolute';
        style.left = `${screenX}px`;
        style.top = `${screenY}px`;
        style.width = `${Math.max(0, canvasW)}px`;
        style.height = `${Math.max(0, canvasH)}px`;
        style.zIndex = '500'; // Lower z-index to stay below footer

        // Match inline title editor behavior: scale font size with zoom
        style.fontSize = `${12 * scale}px`;

        // Hide if too small or out of viewport bounds, but ensure it doesn't overlap footer
        const viewportWidth = window.innerWidth;
        const viewportHeight = window.innerHeight;
        const footerHeight = 36; // Footer height from CSS
        const footerTop = viewportHeight - footerHeight;

        if (canvasW <= 2 || canvasH <= 2 || screenX + canvasW < 0 || screenY + canvasH < 0 ||
            screenX > viewportWidth || screenY > footerTop) {
            this.displayTextarea.style.display = 'none';
        } else {
            this.displayTextarea.style.display = '';
        }
    }

    // Clean up timeouts when node is destroyed
    onRemoved() {
        this.detachDisplayTextarea();
        if (this.copyFeedbackTimeout) {
            clearTimeout(this.copyFeedbackTimeout);
            this.copyFeedbackTimeout = null;
        }
        if (this.positionUpdateId) {
            cancelAnimationFrame(this.positionUpdateId);
            this.positionUpdateId = null;
        }
        super.onRemoved?.();
    }
}