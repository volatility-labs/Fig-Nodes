import BaseCustomNode from '../base/BaseCustomNode';
import { LiteGraph } from '@comfyorg/litegraph';
import { NodeRenderer } from '../utils/NodeRenderer';

class OHLCVPlotRenderer extends NodeRenderer {
    onDrawForeground(ctx: CanvasRenderingContext2D) {
        const node = this.node as OHLCVPlotNodeUI;
        node.drawPlots(ctx);
        this.drawHighlight(ctx);
        this.drawProgressBar(ctx);
        this.drawError(ctx);
    }
}

export default class OHLCVPlotNodeUI extends BaseCustomNode {
    private images: { [label: string]: string } = {};

    constructor(title: string, data: any) {
        super(title, data);
        this.size = [500, 360];
        this.color = '#3949ab';
        this.bgcolor = '#1c2147';
        this.displayResults = false; // custom canvas rendering
        this.renderer = new OHLCVPlotRenderer(this as any);
    }

    updateDisplay(result: any) {
        // Expect { images: { label: dataUrl } }
        const imgs = (result && result.images) || {};
        this.images = imgs;
        this.setDirtyCanvas(true, true);
    }

    drawPlots(ctx: CanvasRenderingContext2D) {
        // In jsdom test environments, canvas.getContext('2d') may return null.
        // Guard to no-op when a real 2D context is not available.
        if (!ctx || typeof (ctx as any).fillRect !== 'function') {
            return;
        }
        const labels = Object.keys(this.images || {});
        const padding = 8;
        const widgetHeight = (this as any).widgets ? (this as any).widgets.length * LiteGraph.NODE_WIDGET_HEIGHT : 0;
        const x0 = padding;
        const y0 = LiteGraph.NODE_TITLE_HEIGHT + widgetHeight + padding;
        const w = Math.max(0, (this as any).size[0] - padding * 2);
        const h = Math.max(0, (this as any).size[1] - LiteGraph.NODE_TITLE_HEIGHT - widgetHeight - padding * 2);

        // Background
        ctx.fillStyle = '#111827';
        ctx.fillRect(x0, y0, w, h);
        ctx.strokeStyle = '#374151';
        ctx.strokeRect(x0 + 0.5, y0 + 0.5, w - 1, h - 1);

        if (!labels.length) {
            ctx.fillStyle = '#9ca3af';
            ctx.font = '12px Arial';
            ctx.fillText('No images', x0 + 10, y0 + 20);
            return;
        }

        // Compute grid
        const cols = Math.ceil(Math.sqrt(labels.length));
        const rows = Math.ceil(labels.length / cols);
        const cellW = Math.floor((w - (cols - 1) * 6) / cols);
        const cellH = Math.floor((h - (rows - 1) * 6) / rows);

        // Draw each image into a cell
        let idx = 0;
        for (let r = 0; r < rows; r++) {
            for (let c = 0; c < cols; c++) {
                if (idx >= labels.length) break;
                const label = labels[idx++];
                const dataUrl = this.images[label];

                const cx = x0 + c * (cellW + 6);
                const cy = y0 + r * (cellH + 6);

                // Label background
                ctx.fillStyle = 'rgba(0,0,0,0.45)';
                ctx.fillRect(cx, cy, cellW, 16);
                ctx.fillStyle = '#e5e7eb';
                ctx.font = '11px Arial';
                ctx.fillText(String(label), cx + 6, cy + 12);

                // Image
                const img = new Image();
                img.onload = () => {
                    // Reserve space below label
                    const ih = Math.max(0, cellH - 18);
                    const iw = cellW;
                    ctx.drawImage(img, cx, cy + 18, iw, ih);
                };
                img.src = dataUrl;

                // Cell border
                ctx.strokeStyle = '#4b5563';
                ctx.strokeRect(cx + 0.5, cy + 0.5, cellW - 1, cellH - 1);
            }
        }
    }
}


