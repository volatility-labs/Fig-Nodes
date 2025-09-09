import BaseCustomNode from './BaseCustomNode';
import { LGraphCanvas, LiteGraph } from '@comfyorg/litegraph';
import { showTextEditor } from '@utils/uiUtils';

export default class TextInputNodeUI extends BaseCustomNode {
    hovering: boolean = false;
    previewLines: string[] = [];

    constructor(title: string, data: any) {
        super(title, data);
        this.resizable = true;
        this.size = [300, 180];

        // Remove default widget and store preview
        this.widgets = [];
        this.updatePreview();

        // Set initial value from properties
        if (!this.properties.value) {
            this.properties.value = '';
        }

        // Set colors for text input styling
        this.color = "#2c2c2c";
        this.bgcolor = "#1e1e1e";
    }

    getLines(): string[] { return (this.properties.value || '').split('\n'); }
    setLines(lines: string[]) { this.properties.value = lines.join('\n'); }

    wrapLine(text: string, maxWidth: number, ctx: CanvasRenderingContext2D): string[] {
        if (!text) return [''];

        const words = text.split(' ');
        const lines: string[] = [];
        let currentLine = '';

        for (const word of words) {
            const testLine = currentLine ? `${currentLine} ${word}` : word;
            const metrics = ctx.measureText(testLine);

            if (metrics.width <= maxWidth) {
                currentLine = testLine;
            } else {
                if (currentLine) {
                    lines.push(currentLine);
                    currentLine = word;
                } else {
                    // Word is too long, force break
                    lines.push(word);
                }
            }
        }

        if (currentLine) {
            lines.push(currentLine);
        }

        return lines.length > 0 ? lines : [''];
    }

    getWrappedLines(ctx: CanvasRenderingContext2D): string[] {
        const textAreaWidth = this.size[0] - 30; // Account for padding and border
        const rawLines = this.getLines();
        const wrappedLines: string[] = [];

        for (const line of rawLines) {
            const wrapped = this.wrapLine(line, textAreaWidth, ctx);
            wrappedLines.push(...wrapped);
        }

        return wrappedLines;
    }

    async onDblClick(_event: MouseEvent, _pos: [number, number], _graphcanvas: LGraphCanvas) {
        if (this.flags?.collapsed) return false;
        const newVal = await showTextEditor(this.properties.value || '', { title: this.title || 'Text', monospace: true, width: 560, height: 380 });
        if (newVal !== null) {
            this.properties.value = newVal;
            this.updatePreview();
            this.setDirtyCanvas(true, true);
        }
        return true;
    }

    onMouseEnter() { this.hovering = true; }
    onMouseLeave() { this.hovering = false; }

    updatePreview() {
        const ctx = (this as any).graph && (this as any).graph.list_of_graphcanvas && (this as any).graph.list_of_graphcanvas[0]?.ctx;
        if (!ctx) {
            this.previewLines = (this.properties.value || '').split('\n').slice(0, 8);
            return;
        }
        const lines = (this.properties.value || '').split('\n');
        const textAreaWidth = this.size[0] - 30;
        ctx.font = '12px monospace';
        const wrapped: string[] = [];
        for (const l of lines) {
            const parts = this.wrapLine(l, textAreaWidth, ctx);
            wrapped.push(...parts);
            if (wrapped.length > 8) break;
        }
        this.previewLines = wrapped.slice(0, 8);
    }

    onDrawForeground(ctx: CanvasRenderingContext2D) {
        if (this.flags?.collapsed) return;

        const padding = 10;
        const borderWidth = 2;
        const lineHeight = 16;
        const textAreaX = padding;
        const textAreaY = LiteGraph.NODE_TITLE_HEIGHT + padding;
        const textAreaWidth = this.size[0] - (padding * 2);
        const textAreaHeight = this.size[1] - LiteGraph.NODE_TITLE_HEIGHT - (padding * 2);

        // Draw text area background and border
        ctx.fillStyle = this.hovering ? '#2a2a2a' : '#1a1a1a';
        ctx.fillRect(textAreaX, textAreaY, textAreaWidth, textAreaHeight);

        // Draw border
        ctx.strokeStyle = this.hovering ? '#5a9fd4' : '#444444';
        ctx.lineWidth = borderWidth;
        ctx.strokeRect(textAreaX, textAreaY, textAreaWidth, textAreaHeight);

        // Set up text rendering
        ctx.font = '12px monospace';
        ctx.textAlign = 'left';
        ctx.fillStyle = '#ffffff';

        // Render preview lines
        this.updatePreview();
        const wrappedLines = this.previewLines;
        let y = textAreaY + padding + 12; // Start position for text

        // Clip text to text area bounds
        ctx.save();
        ctx.beginPath();
        ctx.rect(textAreaX + borderWidth, textAreaY + borderWidth,
            textAreaWidth - (borderWidth * 2), textAreaHeight - (borderWidth * 2));
        ctx.clip();

        wrappedLines.forEach((lineText: string) => {
            if (y <= textAreaY + textAreaHeight - padding) {
                ctx.fillText(lineText, textAreaX + padding, y);
                y += lineHeight;
            }
        });

        ctx.restore();

        // Hint to open editor
        if (!this.hovering) {
            ctx.fillStyle = '#9aa0a6';
            ctx.fillText('Double-click to edit…', textAreaX + padding, textAreaY + textAreaHeight - padding);
        }

        // Auto-adjust node size based on content
        const minHeight = LiteGraph.NODE_TITLE_HEIGHT + 80;
        const contentHeight = Math.max(wrappedLines.length * lineHeight + (padding * 3) + LiteGraph.NODE_TITLE_HEIGHT, minHeight);

        if (this.size[1] < contentHeight) {
            this.size[1] = contentHeight;
        }
    }

    onResize(_size: [number, number]) {
        this.setDirtyCanvas(true, true);
    }
}
