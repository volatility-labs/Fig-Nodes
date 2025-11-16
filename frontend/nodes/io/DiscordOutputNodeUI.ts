import BaseCustomNode from '../base/BaseCustomNode';
import { LiteGraph } from '@fig-node/litegraph';

export default class DiscordOutputNodeUI extends BaseCustomNode {
    private textareaEl: HTMLTextAreaElement | null = null;
    private lastCanvasRef: any = null;
    private positionUpdateId: number | null = null;

    constructor(title: string, data: any, serviceRegistry: any) {
        super(title, data, serviceRegistry);
        this.resizable = true;
        this.size = [400, 250];

        // Remove the message_template widget (we'll use custom textarea instead)
        // But keep max_symbols_display widget
        if (this.widgets) {
            this.widgets = this.widgets.filter((widget: any) => {
                // Keep widgets that are NOT message_template
                return widget.paramName !== 'message_template';
            });
        }

        // Initialize message_template property if not present
        if (!this.properties.message_template) {
            this.properties.message_template = '📊 **Trading Symbols Update**\n\n{symbol_list}\n\n*Total: {count} symbols*';
        }

        // Use default node theme colors for consistency with other nodes
        this.displayResults = false;
    }

    // Lifecycle: called by LiteGraph when node is added to graph
    onAdded() { 
        this.ensureTextarea(); 
    }

    onRemoved() {
        this.detachTextarea();
        if (this.positionUpdateId) {
            cancelAnimationFrame(this.positionUpdateId);
            this.positionUpdateId = null;
        }
    }

    onDeselected() {
        // Keep editor visible even when not selected
        this.syncTextarea();
    }

    onResize(_size: [number, number]) {
        this.syncTextarea();
        this.setDirtyCanvas(true, true);
    }

    // Draw only minimal background under the textarea for visual consistency
    onDrawForeground(ctx: CanvasRenderingContext2D) {
        if (this.flags?.collapsed) {
            this.hideTextarea();
            return;
        }

        const padding = 8;
        const x = padding;
        // Account for widget height (max_symbols_display widget)
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

    // Do not override mouse handling; textarea will capture events itself

    private schedulePositionUpdate(x: number, y: number, w: number, h: number) {
        if (this.positionUpdateId !== null) return;
        
        this.positionUpdateId = requestAnimationFrame(() => {
            this.positionUpdateId = null;
            this.ensureTextarea();
            this.positionTextarea(x, y, w, h);
        });
    }

    private ensureTextarea() {
        const graph = this.graph;
        if (!graph) return;
        const canvas = graph.list_of_graphcanvas && graph.list_of_graphcanvas[0];
        if (!canvas || !canvas.canvas) return;

        if (!this.textareaEl || this.lastCanvasRef !== canvas) {
            this.detachTextarea();
            this.lastCanvasRef = canvas;
            const parent = document.body;
            const ta = document.createElement('textarea');
            ta.className = 'inline-node-textarea monospace';
            ta.spellcheck = false;
            ta.value = String(this.properties.message_template || '');
            ta.addEventListener('input', () => {
                this.properties.message_template = ta.value;
            });
            ta.addEventListener('blur', () => {
                this.properties.message_template = ta.value;
            });
            // Stop key events from bubbling to canvas shortcuts
            ta.addEventListener('keydown', (ev) => {
                ev.stopPropagation();
            });
            parent.appendChild(ta);
            this.textareaEl = ta;
        }
        // Don't call syncTextarea() here - let schedulePositionUpdate handle positioning
    }

    private detachTextarea() {
        if (this.textareaEl && this.textareaEl.parentElement) {
            this.textareaEl.parentElement.removeChild(this.textareaEl);
        }
        this.textareaEl = null;
        this.lastCanvasRef = null;
    }

    private hideTextarea() {
        if (this.textareaEl) {
            this.textareaEl.style.display = 'none';
        }
    }

    private syncTextarea() {
        if (!this.textareaEl) return;
        this.textareaEl.style.display = '';
        const current = String(this.properties.message_template ?? '');
        if (this.textareaEl.value !== current) {
            this.textareaEl.value = current;
        }
        // Ensure position up-to-date
        const padding = 8;
        const x = padding;
        const widgetHeight = this.widgets ? this.widgets.length * LiteGraph.NODE_WIDGET_HEIGHT : 0;
        const y = LiteGraph.NODE_TITLE_HEIGHT + widgetHeight + padding;
        const w = Math.max(0, this.size[0] - padding * 2);
        const h = Math.max(0, this.size[1] - LiteGraph.NODE_TITLE_HEIGHT - widgetHeight - padding * 2);
        this.positionTextarea(x, y, w, h);
    }

    private positionTextarea(localX: number, localY: number, localW: number, localH: number) {
        if (!this.textareaEl) return;
        const graph = this.graph;
        const canvas = graph && graph.list_of_graphcanvas && graph.list_of_graphcanvas[0];
        if (!canvas || !canvas.canvas) return;

        // Get canvas transform from LiteGraph's internal state (match title edit logic)
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
        const style = this.textareaEl.style;
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
            this.textareaEl.style.display = 'none';
        } else {
            this.textareaEl.style.display = '';
        }
    }
}

