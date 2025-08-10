import BaseCustomNode from './BaseCustomNode';
import { LGraphCanvas, LiteGraph } from '@comfyorg/litegraph';

export default class TextInputNodeUI extends BaseCustomNode {
    editing: boolean = false;
    cursorPos: { line: number, col: number } = { line: 0, col: 0 };
    cursorBlink: number = 0;
    graphcanvas: LGraphCanvas | null = null;

    constructor(title: string, data: any) {
        super(title, data);
        this.resizable = true;
        this.size = [300, 180];

        // Remove default widget to handle custom editing
        this.widgets = [];

        // Set initial value from properties
        if (!this.properties.value) {
            this.properties.value = '';
        }

        // Set colors for text input styling
        this.color = "#2c2c2c";
        this.bgcolor = "#1e1e1e";
    }

    getLines(): string[] {
        return this.properties.value.split('\n');
    }

    setLines(lines: string[]) {
        this.properties.value = lines.join('\n');
    }

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

    onMouseDown(event: MouseEvent, pos: [number, number], graphcanvas: LGraphCanvas) {
        if (this.flags?.collapsed) return false;
        if (pos[1] < LiteGraph.NODE_TITLE_HEIGHT) return false;

        const padding = 10;
        const textAreaX = padding;
        const textAreaY = LiteGraph.NODE_TITLE_HEIGHT + padding;
        const textAreaWidth = this.size[0] - (padding * 2);
        const textAreaHeight = this.size[1] - LiteGraph.NODE_TITLE_HEIGHT - (padding * 2);

        // Check if click is within text area bounds
        if (pos[0] < textAreaX || pos[0] > textAreaX + textAreaWidth ||
            pos[1] < textAreaY || pos[1] > textAreaY + textAreaHeight) {
            return false;
        }

        // Calculate cursor position based on click
        const localY = pos[1] - textAreaY - padding;
        const localX = pos[0] - textAreaX - padding;
        const lineHeight = 16;
        const line = Math.floor(localY / lineHeight);
        const lines = this.getLines();

        if (line < lines.length) {
            const ctx = graphcanvas.ctx;
            ctx.font = '12px monospace';
            let col = 0;
            const lineText = lines[line];
            while (col < lineText.length) {
                const width = ctx.measureText(lineText.substring(0, col + 1)).width;
                if (width > localX) break;
                col++;
            }
            this.cursorPos = { line, col };
        } else {
            this.cursorPos = { line: lines.length - 1, col: lines[lines.length - 1].length };
        }

        this.editing = true;
        this.cursorBlink = Date.now();
        this.graphcanvas = graphcanvas;
        // @ts-ignore
        graphcanvas.editingNode = this;
        this.setDirtyCanvas(true, true);
        return true;
    }

    onKeyDown(e: KeyboardEvent) {
        if (!this.editing) return;

        if (e.key === 'Escape') {
            this.editing = false;
            if (this.graphcanvas) {
                // @ts-ignore
                this.graphcanvas.editingNode = null;
            }
            this.setDirtyCanvas(true, true);
            return;
        }

        const lines = this.getLines();
        const { line, col } = this.cursorPos;
        let currentLine = lines[line] || '';

        if (e.key === 'Enter') {
            const before = currentLine.substring(0, col);
            const after = currentLine.substring(col);
            lines[line] = before;
            lines.splice(line + 1, 0, after);
            this.cursorPos = { line: line + 1, col: 0 };
        } else if (e.key === 'Backspace') {
            if (col > 0) {
                lines[line] = currentLine.substring(0, col - 1) + currentLine.substring(col);
                this.cursorPos.col--;
            } else if (line > 0) {
                const prevLine = lines[line - 1];
                lines[line - 1] = prevLine + currentLine;
                lines.splice(line, 1);
                this.cursorPos = { line: line - 1, col: prevLine.length };
            }
        } else if (e.key === 'Delete') {
            if (col < currentLine.length) {
                lines[line] = currentLine.substring(0, col) + currentLine.substring(col + 1);
            } else if (line < lines.length - 1) {
                lines[line] = currentLine + lines[line + 1];
                lines.splice(line + 1, 1);
            }
        } else if (e.key === 'ArrowLeft') {
            if (col > 0) this.cursorPos.col--;
            else if (line > 0) this.cursorPos = { line: line - 1, col: lines[line - 1].length };
        } else if (e.key === 'ArrowRight') {
            if (col < currentLine.length) this.cursorPos.col++;
            else if (line < lines.length - 1) this.cursorPos = { line: line + 1, col: 0 };
        } else if (e.key === 'ArrowUp' && line > 0) {
            this.cursorPos.line--;
            this.cursorPos.col = Math.min(col, lines[this.cursorPos.line].length);
        } else if (e.key === 'ArrowDown' && line < lines.length - 1) {
            this.cursorPos.line++;
            this.cursorPos.col = Math.min(col, lines[this.cursorPos.line].length);
        } else if (e.key.length === 1 && !e.ctrlKey && !e.metaKey) {
            lines[line] = currentLine.substring(0, col) + e.key + currentLine.substring(col);
            this.cursorPos.col++;
        } else {
            return; // Unhandled key
        }

        this.setLines(lines);
        this.cursorBlink = Date.now();
        this.setDirtyCanvas(true, true);
        e.preventDefault();
        e.stopPropagation();
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
        ctx.fillStyle = this.editing ? '#2a2a2a' : '#1a1a1a';
        ctx.fillRect(textAreaX, textAreaY, textAreaWidth, textAreaHeight);

        // Draw border
        ctx.strokeStyle = this.editing ? '#5a9fd4' : '#444444';
        ctx.lineWidth = borderWidth;
        ctx.strokeRect(textAreaX, textAreaY, textAreaWidth, textAreaHeight);

        // Set up text rendering
        ctx.font = '12px monospace';
        ctx.textAlign = 'left';
        ctx.fillStyle = '#ffffff';

        // Get wrapped lines and render
        const wrappedLines = this.getWrappedLines(ctx);
        let y = textAreaY + padding + 12; // Start position for text

        // Clip text to text area bounds
        ctx.save();
        ctx.beginPath();
        ctx.rect(textAreaX + borderWidth, textAreaY + borderWidth,
            textAreaWidth - (borderWidth * 2), textAreaHeight - (borderWidth * 2));
        ctx.clip();

        wrappedLines.forEach((lineText: string, index: number) => {
            if (y <= textAreaY + textAreaHeight - padding) {
                ctx.fillText(lineText, textAreaX + padding, y);
                y += lineHeight;
            }
        });

        ctx.restore();

        // Draw cursor if editing
        if (this.editing && (Date.now() - this.cursorBlink) % 1000 < 500) {
            const { line, col } = this.cursorPos;
            const rawLines = this.getLines();
            if (line < rawLines.length) {
                const cursorText = rawLines[line].substring(0, col);
                const cursorX = textAreaX + padding + ctx.measureText(cursorText).width;
                const cursorY = textAreaY + padding + (line * lineHeight);

                if (cursorY >= textAreaY && cursorY <= textAreaY + textAreaHeight - padding) {
                    ctx.fillStyle = '#ffffff';
                    ctx.fillRect(cursorX, cursorY, 1, lineHeight);
                }
            }
        }

        // Auto-adjust node size based on content
        const minHeight = LiteGraph.NODE_TITLE_HEIGHT + 80;
        const contentHeight = Math.max(wrappedLines.length * lineHeight + (padding * 3) + LiteGraph.NODE_TITLE_HEIGHT, minHeight);

        if (this.size[1] < contentHeight) {
            this.size[1] = contentHeight;
        }
    }

    onResize(size: [number, number]) {
        this.setDirtyCanvas(true, true);
    }
}
