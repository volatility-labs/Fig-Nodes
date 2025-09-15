import BaseCustomNode from './BaseCustomNode';
import { LiteGraph } from '@comfyorg/litegraph';

export default class TextInputNodeUI extends BaseCustomNode {
    private textareaEl: HTMLTextAreaElement | null = null;
    private lastCanvasRef: any = null;

    constructor(title: string, data: any) {
        super(title, data);
        this.resizable = true;
        this.size = [360, 200];

        // Remove default widgets (incl. Title) and let inline textarea handle input
        this.widgets = [];

        if (!this.properties.value) {
            this.properties.value = '';
        }

        // Use default node theme colors for consistency with other nodes
        this.displayResults = false;
    }

    // Lifecycle: called by LiteGraph when node is added to graph
    onAdded() { this.ensureTextarea(); }

    onRemoved() { this.detachTextarea(); }

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
        this.ensureTextarea();

        const padding = 8;
        const x = padding;
        const y = LiteGraph.NODE_TITLE_HEIGHT + padding;
        const w = Math.max(0, this.size[0] - padding * 2);
        const h = Math.max(0, this.size[1] - LiteGraph.NODE_TITLE_HEIGHT - padding * 2);

        // Background (will be fully covered by textarea but keeps a fallback look)
        ctx.fillStyle = '#2a2a2a';
        ctx.fillRect(x, y, w, h);

        // Border to match app theme
        ctx.strokeStyle = '#555';
        ctx.lineWidth = 1;
        ctx.strokeRect(x + 0.5, y + 0.5, w - 1, h - 1);

        this.positionTextarea(x, y, w, h);
    }

    // Do not override mouse handling; textarea will capture events itself

    private ensureTextarea() {
        const graph: any = (this as any).graph;
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
            ta.value = String(this.properties.value || '');
            ta.addEventListener('input', () => {
                this.properties.value = ta.value;
            });
            ta.addEventListener('blur', () => {
                this.properties.value = ta.value;
            });
            // Stop key events from bubbling to canvas shortcuts
            ta.addEventListener('keydown', (ev) => {
                ev.stopPropagation();
            });
            parent.appendChild(ta);
            this.textareaEl = ta;
        }
        this.syncTextarea();
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
        const current = String(this.properties.value ?? '');
        if (this.textareaEl.value !== current) {
            this.textareaEl.value = current;
        }
        // Ensure position up-to-date
        const padding = 8;
        const x = padding;
        const y = LiteGraph.NODE_TITLE_HEIGHT + padding;
        const w = Math.max(0, this.size[0] - padding * 2);
        const h = Math.max(0, this.size[1] - LiteGraph.NODE_TITLE_HEIGHT - padding * 2);
        this.positionTextarea(x, y, w, h);
    }

    private positionTextarea(localX: number, localY: number, localW: number, localH: number) {
        if (!this.textareaEl) return;
        const graph: any = (this as any).graph;
        const canvas = graph && graph.list_of_graphcanvas && graph.list_of_graphcanvas[0];
        if (!canvas || !canvas.canvas) return;

        // Get canvas transform from LiteGraph's internal state (match title edit logic)
        const scale = canvas.ds?.scale || canvas.scale || 1;
        const offset = canvas.ds?.offset || canvas.offset || [0, 0];
        const offx = Array.isArray(offset) ? offset[0] : 0;
        const offy = Array.isArray(offset) ? offset[1] : 0;

        // Convert canvas coordinates to screen coordinates: (pos + offset) * scale
        const canvasX = (this.pos[0] + localX + offx) * scale;
        const canvasY = (this.pos[1] + localY + offy) * scale;
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
        style.zIndex = '1000';

        // Match inline title editor behavior: scale font size with zoom
        style.fontSize = `${12 * scale}px`;

        // Hide if too small or out of viewport bounds
        const viewportWidth = window.innerWidth;
        const viewportHeight = window.innerHeight;
        if (canvasW <= 2 || canvasH <= 2 || screenX + canvasW < 0 || screenY + canvasH < 0 ||
            screenX > viewportWidth || screenY > viewportHeight) {
            this.textareaEl.style.display = 'none';
        } else {
            this.textareaEl.style.display = '';
        }
    }
}
