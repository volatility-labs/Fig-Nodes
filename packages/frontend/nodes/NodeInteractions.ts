import { LGraphNode, LiteGraph } from '@fig-node/litegraph';

export class NodeInteractions {
    private node: LGraphNode & { title: string; pos: [number, number]; size: [number, number] };

    constructor(node: LGraphNode & { title: string; pos: [number, number]; size: [number, number] }) {
        this.node = node;
    }

    /**
     * Handles double-click events on the node's title.
     * @param _event - The mouse event.
     * @param pos - The position of the click.
     * @param _canvas - The canvas.
     * @returns True if the double-click was handled, false otherwise.
     */
    onDblClick(_event: MouseEvent, pos: [number, number], _canvas: unknown): boolean {
        const bounds = this.getTitleTextBounds();
        if (!bounds) return false;
        const [x, y] = pos;
        const within = x >= bounds.x && x <= bounds.x + bounds.width && y >= bounds.y && y <= bounds.y + bounds.height;
        if (within) {
            this.startTitleEdit();
            return true;
        }
        return false;
    }

    /**
     * Gets the bounds of the node's title text.
     * @returns The bounds of the title text, or null if the bounds cannot be calculated.
     */
    private getTitleTextBounds(): { x: number; y: number; width: number; height: number } | null {
        const fontSize = this.getTitleFontSize();
        const padLeft = LiteGraph.NODE_TITLE_HEIGHT;
        const baselineY = -LiteGraph.NODE_TITLE_HEIGHT + LiteGraph.NODE_TITLE_TEXT_Y;

        const canvasEl = document.createElement('canvas');
        const ctx = canvasEl.getContext('2d');
        if (!ctx) return null;
        const fontStyle: string = (this.node as { titleFontStyle?: string }).titleFontStyle || `${fontSize}px Arial`;
        ctx.font = String(fontStyle);
        const text = this.node.title ?? '';
        const textWidth = Math.ceil(ctx.measureText(text).width);

        const height = Math.ceil(fontSize + 6);
        const yTop = Math.round(baselineY - fontSize * 0.85);

        return { x: padLeft, y: yTop, width: Math.max(2, textWidth), height };
    }

    private getTitleFontSize(): number {
        try {
            const style: string = (this.node as { titleFontStyle?: string }).titleFontStyle || '';
            const m = String(style).match(/(\d+(?:\.\d+)?)px/);
            if (m) return Math.round(Number(m[1]));
        } catch { /* ignore */ }
        try {
            const sizeConst: unknown = (LiteGraph as { NODE_TEXT_SIZE?: unknown }).NODE_TEXT_SIZE;
            if (typeof sizeConst === 'number' && Number.isFinite(sizeConst)) return sizeConst;
        } catch { /* ignore */ }
        return 16;
    }

    private startTitleEdit() {
        const titleElement = document.createElement('input');
        titleElement.className = 'inline-title-input';
        titleElement.value = this.node.title;
        titleElement.style.position = 'absolute';

        try {
            const graph: unknown = (this.node as { graph?: unknown }).graph;
            const canvas = (graph as { list_of_graphcanvas?: Array<{ canvas?: HTMLCanvasElement; ds?: { scale?: number; offset?: [number, number] } }> })?.list_of_graphcanvas?.[0];
            const rect: DOMRect | undefined = canvas?.canvas?.getBoundingClientRect();
            const scale: number = canvas?.ds?.scale ?? 1;
            const offset: [number, number] = canvas?.ds?.offset ?? [0, 0];

            if (rect) {
                const nodeScreenX = rect.left + (this.node.pos[0] + offset[0]) * scale;
                const nodeScreenY = rect.top + (this.node.pos[1] + offset[1]) * scale;

                const titleBarHeight = (LiteGraph as { NODE_TITLE_HEIGHT?: number }).NODE_TITLE_HEIGHT || 30;
                const titleBarTop = nodeScreenY - (titleBarHeight * scale);
                const titleBarWidth = this.node.size[0] * scale;

                const inputPadding = 8 * scale;
                const inputWidth = Math.max(100 * scale, titleBarWidth - (inputPadding * 2));
                const inputHeight = Math.min(28 * scale, titleBarHeight * 0.8);

                titleElement.style.left = `${Math.round(nodeScreenX + inputPadding)}px`;
                titleElement.style.top = `${Math.round(titleBarTop + (titleBarHeight * scale - inputHeight) / 2)}px`;
                titleElement.style.width = `${Math.round(inputWidth)}px`;
                titleElement.style.height = `${Math.round(inputHeight)}px`;

                const baseFontSize = 14;
                const scaledFontSize = Math.max(11, Math.min(18, baseFontSize * Math.sqrt(scale)));
                titleElement.style.fontSize = `${Math.round(scaledFontSize)}px`;
            } else {
                titleElement.style.left = `${this.node.pos[0] + 8}px`;
                titleElement.style.top = `${this.node.pos[1] - 25}px`;
                titleElement.style.width = `${Math.max(100, this.node.size[0] - 16)}px`;
                titleElement.style.height = '24px';
            }
        } catch {
            titleElement.style.left = `${this.node.pos[0] + 8}px`;
            titleElement.style.top = `${this.node.pos[1] - 25}px`;
            titleElement.style.width = `${Math.max(100, this.node.size[0] - 16)}px`;
            titleElement.style.height = '24px';
        }

        titleElement.style.zIndex = '3000';

        const finishEdit = (save: boolean) => {
            if (save && titleElement.value.trim()) {
                this.node.title = titleElement.value.trim();
            }
            if (titleElement.parentNode) {
                document.body.removeChild(titleElement);
            }
            this.node.setDirtyCanvas(true, true);
        };

        titleElement.addEventListener('keydown', (e: KeyboardEvent) => {
            e.stopPropagation();
            if (e.key === 'Enter') {
                finishEdit(true);
            } else if (e.key === 'Escape') {
                finishEdit(false);
            }
        });

        titleElement.addEventListener('blur', () => {
            finishEdit(true);
        });

        document.body.appendChild(titleElement);
        titleElement.focus();
        titleElement.select();
    }
}
