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

        // ComfyUI-like colors
        this.color = '#2c2c2c';
        this.bgcolor = '#1e1e1e';
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
        ctx.fillStyle = '#1a1a1a';
        ctx.fillRect(x, y, w, h);

        // Border to match ComfyUI prompt box
        ctx.strokeStyle = '#3a3a3a';
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
            const parent = canvas.canvas.parentElement || document.body;
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
        if (!canvas) return;

        // Convert node-local canvas coords to overlay CSS pixels
        const ds = (canvas as any).ds || { scale: 1, offset: [0, 0] };
        const scale = ds.scale || 1;
        const offx = Array.isArray(ds.offset) ? ds.offset[0] : 0;
        const offy = Array.isArray(ds.offset) ? ds.offset[1] : 0;

        const cx = (this.pos[0] + localX) * scale + offx;
        const cy = (this.pos[1] + localY) * scale + offy;
        const cw = localW * scale;
        const ch = localH * scale;

        const parent = (canvas.canvas.parentElement || document.body);
        // Position absolute within the canvas parent
        const style = this.textareaEl.style;
        style.position = 'absolute';
        style.left = `${cx}px`;
        style.top = `${cy}px`;
        style.width = `${Math.max(0, cw)}px`;
        style.height = `${Math.max(0, ch)}px`;
        style.zIndex = '10';

        // Keep font size stable; match ComfyUI prompt look
        (this.textareaEl as HTMLTextAreaElement).style.fontSize = '12px';

        // Clamp within parent bounds
        const rect = parent.getBoundingClientRect();
        if (cw <= 2 || ch <= 2 || cx > rect.width || cy > rect.height) {
            this.textareaEl.style.display = 'none';
        }
    }
}
