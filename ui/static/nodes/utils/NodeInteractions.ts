import { LGraphNode, LiteGraph } from '@comfyorg/litegraph';

export class NodeInteractions {
    private node: LGraphNode & { title: string; pos: any; size: any };

    constructor(node: LGraphNode & { title: string; pos: any; size: any }) {
        this.node = node;
    }

    onDblClick(_event: MouseEvent, pos: [number, number], _canvas: any): boolean {
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

    private getTitleTextBounds(): { x: number; y: number; width: number; height: number } | null {
        const fontSize = this.getTitleFontSize();
        const padLeft = LiteGraph.NODE_TITLE_HEIGHT;
        const baselineY = -LiteGraph.NODE_TITLE_HEIGHT + (LiteGraph as any).NODE_TITLE_TEXT_Y;

        const canvasEl = document.createElement('canvas');
        const ctx = canvasEl.getContext('2d');
        if (!ctx) return null;
        const fontStyle: any = (this.node as any).titleFontStyle || `${fontSize}px Arial`;
        ctx.font = String(fontStyle);
        const text = this.node.title ?? '';
        const textWidth = Math.ceil(ctx.measureText(text).width);

        const height = Math.ceil(fontSize + 6);
        const yTop = Math.round(baselineY - fontSize * 0.85);

        return { x: padLeft, y: yTop, width: Math.max(2, textWidth), height };
    }

    private getTitleFontSize(): number {
        try {
            const style: any = (this.node as any).titleFontStyle || '';
            const m = String(style).match(/(\d+(?:\.\d+)?)px/);
            if (m) return Math.round(Number(m[1]));
        } catch { /* ignore */ }
        try {
            const sizeConst: any = (LiteGraph as any).NODE_TEXT_SIZE;
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
            const graph: any = (this.node as any).graph;
            const canvas = graph?.list_of_graphcanvas?.[0];
            const rect: DOMRect | undefined = canvas?.canvas?.getBoundingClientRect();
            const scale: number = canvas?.ds?.scale ?? 1;
            const offset: [number, number] = canvas?.ds?.offset ?? [0, 0];

            if (rect) {
                const nodeScreenX = rect.left + (this.node.pos[0] + offset[0]) * scale;
                const nodeScreenY = rect.top + (this.node.pos[1] + offset[1]) * scale;

                const titleBarHeight = (LiteGraph as any).NODE_TITLE_HEIGHT || 30;
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
