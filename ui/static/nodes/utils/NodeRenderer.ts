import { LGraphNode, LiteGraph } from '@comfyorg/litegraph';

export class NodeRenderer {
    protected node: LGraphNode & {
        displayResults: boolean;
        result: any;
        displayText: string;
        error: string;
        highlightStartTs: number | null;
        readonly highlightDurationMs: number;
        progress: number;
        progressText: string;
        properties: { [key: string]: any };
    };

    constructor(node: LGraphNode & {
        displayResults: boolean;
        result: any;
        displayText: string;
        error: string;
        highlightStartTs: number | null;
        readonly highlightDurationMs: number;
        progress: number;
        progressText: string;
        properties: { [key: string]: any };
    }) {
        this.node = node;
    }

    wrapText(text: string, maxWidth: number, ctx: CanvasRenderingContext2D): string[] {
        if (typeof text !== 'string') return [];
        const lines: string[] = [];
        const paragraphs = text.split('\n');
        for (const p of paragraphs) {
            const words = p.split(' ');
            let currentLine = words[0] || '';
            for (let i = 1; i < words.length; i++) {
                const word = words[i];
                const width = ctx.measureText(currentLine + ' ' + word).width;
                if (width < maxWidth) {
                    currentLine += ' ' + word;
                } else {
                    lines.push(currentLine);
                    currentLine = word;
                }
            }
            if (currentLine) lines.push(currentLine);
        }
        return lines;
    }

    onDrawForeground(ctx: CanvasRenderingContext2D) {
        this.drawHighlight(ctx);
        this.drawProgressBar(ctx);
        this.drawContent(ctx);
        this.drawError(ctx);
    }

    protected drawHighlight(ctx: CanvasRenderingContext2D) {
        if (this.node.highlightStartTs !== null) {
            const now = performance.now();
            const elapsed = now - this.node.highlightStartTs;
            if (elapsed < this.node.highlightDurationMs) {
                const t = 1 - (elapsed / this.node.highlightDurationMs);
                const alpha = 0.25 + 0.55 * t;
                const glow = Math.floor(6 * t) + 2;
                ctx.save();
                ctx.strokeStyle = `rgba(33, 150, 243, ${alpha.toFixed(3)})`;
                ctx.lineWidth = 2;
                (ctx as any).shadowColor = `rgba(33, 150, 243, ${Math.min(0.8, 0.2 + 0.6 * t).toFixed(3)})`;
                (ctx as any).shadowBlur = glow;
                ctx.strokeRect(1, 1, (this.node as any).size[0] - 2, (this.node as any).size[1] - 2);
                ctx.restore();
                this.node.setDirtyCanvas(true, true);
            } else {
                this.node.highlightStartTs = null;
            }
        }
    }

    drawProgressBar(ctx: CanvasRenderingContext2D) {
        if (this.node.progress >= 0) {
            const barHeight = 5;
            const barY = 2;
            const barWidth = Math.max(0, (this.node as any).size[0] - 16);
            const barX = 8;

            // Background bar
            ctx.fillStyle = 'rgba(0, 0, 0, 0.2)';
            ctx.fillRect(barX, barY, barWidth, barHeight);

            // Inner background
            ctx.fillStyle = 'rgba(255, 255, 255, 0.05)';
            ctx.fillRect(barX + 1, barY + 1, barWidth - 2, barHeight - 2);

            // Progress fill
            const clampedPercent = Math.max(0, Math.min(100, this.node.progress));
            const progressWidth = Math.max(0, Math.min(barWidth - 2, ((barWidth - 2) * clampedPercent) / 100));

            if (progressWidth > 0) {
                ctx.fillStyle = '#2196f3';
                ctx.fillRect(barX + 1, barY + 1, progressWidth, barHeight - 2);
            }

            // Progress text
            if (this.node.progressText) {
                ctx.save();
                ctx.fillStyle = '#ffffff';
                ctx.font = 'bold 10px Arial';
                ctx.textAlign = 'right';
                ctx.textBaseline = 'middle';

                ctx.shadowColor = 'rgba(0, 0, 0, 0.7)';
                ctx.shadowBlur = 1;
                ctx.shadowOffsetX = 0;
                ctx.shadowOffsetY = 1;

                ctx.fillText(this.node.progressText, barX + barWidth - 3, barY + barHeight / 2);
                ctx.restore();
            }
        }
    }

    protected drawContent(ctx: CanvasRenderingContext2D) {
        if ((this.node as any).flags?.collapsed || !this.node.displayResults || !this.node.displayText) {
            return;
        }

        const maxWidth = (this.node as any).size[0] - 20;

        const tempCanvas = document.createElement('canvas');
        const tempCtx = tempCanvas.getContext('2d');
        if (!tempCtx) return;

        tempCtx.font = '12px Arial';
        const lines = this.wrapText(this.node.displayText, maxWidth, tempCtx);

        let y = LiteGraph.NODE_TITLE_HEIGHT + 4 + (this.node.progress >= 0 ? 9 : 0);
        if ((this.node as any).widgets) {
            y += (this.node as any).widgets.length * LiteGraph.NODE_WIDGET_HEIGHT;
        }
        y += 10;
        const contentHeight = lines.length * 15;
        const neededHeight = y + contentHeight + 10;

        if (Math.abs((this.node as any).size[1] - neededHeight) > 1) {
            (this.node as any).size[1] = neededHeight;
            this.node.setDirtyCanvas(true, true);
            return;
        }

        ctx.font = '12px Arial';
        ctx.fillStyle = '#ffffff';
        ctx.textAlign = 'left';

        lines.forEach((line, index) => {
            ctx.fillText(line, 10, y + index * 15);
        });
    }

    protected drawError(ctx: CanvasRenderingContext2D) {
        if (this.node.error) {
            ctx.fillStyle = '#FF0000';
            ctx.font = 'bold 12px Arial';
            const errorY = this.calculateErrorY();
            ctx.fillText(`Error: ${this.node.error}`, 10, errorY);
            (this.node as any).size[1] = Math.max((this.node as any).size[1], errorY + 20);
        }
    }

    private calculateErrorY(): number {
        const baseY = LiteGraph.NODE_TITLE_HEIGHT + 4 + (this.node.progress >= 0 ? 9 : 0);
        const widgetOffset = (this.node as any).widgets ? (this.node as any).widgets.length * LiteGraph.NODE_WIDGET_HEIGHT : 0;
        const contentOffset = this.node.displayText ? this.wrapText(this.node.displayText, (this.node as any).size[0] - 20, { measureText: () => ({ width: 0 }) } as any).length * 15 + 10 : 0;
        return baseY + widgetOffset + contentOffset;
    }

    setProgress(progress: number, text?: string) {
        this.node.progress = Math.max(-1, Math.min(100, progress));
        this.node.progressText = text || '';
        this.node.setDirtyCanvas(true, true);
    }

    clearProgress() {
        this.node.progress = -1;
        this.node.progressText = '';
        this.node.setDirtyCanvas(true, true);
    }

    pulseHighlight() {
        this.node.highlightStartTs = performance.now();
        this.node.setDirtyCanvas(true, true);
    }

}
