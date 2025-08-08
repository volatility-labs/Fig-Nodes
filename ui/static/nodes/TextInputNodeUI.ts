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
        this.size = [280, 160];

        // Remove default widget to handle custom editing
        this.widgets = [];

        // Set initial value from properties
        if (!this.properties.value) {
            this.properties.value = '';
        }
    }

    getLines(): string[] {
        return this.properties.value.split('\n');
    }

    setLines(lines: string[]) {
        this.properties.value = lines.join('\n');
    }

    onMouseDown(event: MouseEvent, pos: [number, number], graphcanvas: LGraphCanvas) {
        if (this.flags?.collapsed) return false;
        if (pos[1] < LiteGraph.NODE_TITLE_HEIGHT) return false;

        // Calculate cursor position based on click
        const localY = pos[1] - LiteGraph.NODE_TITLE_HEIGHT - 10;
        const localX = pos[0] - 10;
        const lineHeight = 15;
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

        let y = LiteGraph.NODE_TITLE_HEIGHT + 10;
        const lineHeight = 15;
        ctx.font = '12px monospace';
        ctx.textAlign = 'left';
        ctx.fillStyle = '#ffffff';

        const lines = this.getLines();
        lines.forEach((lineText: string) => {
            ctx.fillText(lineText, 10, y);
            y += lineHeight;
        });

        // Draw cursor if editing
        if (this.editing && (Date.now() - this.cursorBlink) % 1000 < 500) {
            const { line, col } = this.cursorPos;
            if (line < lines.length) {
                const cursorX = 10 + ctx.measureText(lines[line].substring(0, col)).width;
                const cursorY = LiteGraph.NODE_TITLE_HEIGHT + 10 + line * lineHeight;
                ctx.fillRect(cursorX, cursorY - 12, 1, lineHeight);
            }
        }

        // Adjust node size based on content
        const requiredHeight = LiteGraph.NODE_TITLE_HEIGHT + lines.length * lineHeight + 20;
        if (this.size[1] < requiredHeight) {
            this.size[1] = requiredHeight;
        }
    }

    onResize(size: [number, number]) {
        this.setDirtyCanvas(true, true);
    }
}
