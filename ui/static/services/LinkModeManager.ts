import { LGraphCanvas, LiteGraph } from '@comfyorg/litegraph';

export class LinkModeManager {
    private canvas: LGraphCanvas;
    private currentLinkMode: number;
    private readonly linkModeNames = ['Curved', 'Orthogonal', 'Straight'];
    private readonly linkModeValues = [LiteGraph.SPLINE_LINK, LiteGraph.LINEAR_LINK, LiteGraph.STRAIGHT_LINK];

    constructor(canvas: LGraphCanvas) {
        this.canvas = canvas;
        this.currentLinkMode = LiteGraph.SPLINE_LINK; // Default curved
        this.initialize();
    }

    private initialize(): void {
        this.applyLinkMode(this.currentLinkMode);
    }

    applyLinkMode(mode: number): void {
        this.currentLinkMode = mode;
        this.canvas.links_render_mode = mode;
        this.canvas.render_curved_connections = (mode === LiteGraph.SPLINE_LINK);

        if (typeof (this.canvas as any).setDirty === 'function') {
            (this.canvas as any).setDirty(true, true);
        }

        this.updateButtonLabel();
    }

    cycleLinkMode(): void {
        const currentIndex = this.linkModeValues.indexOf(this.currentLinkMode);
        const nextIndex = (currentIndex + 1) % this.linkModeValues.length;
        this.applyLinkMode(this.linkModeValues[nextIndex]);
    }

    getCurrentLinkMode(): number {
        return this.currentLinkMode;
    }

    getLinkModeName(mode?: number): string {
        const targetMode = mode ?? this.currentLinkMode;
        const modeIndex = this.linkModeValues.indexOf(targetMode);
        return this.linkModeNames[modeIndex] || this.linkModeNames[0];
    }

    private updateButtonLabel(): void {
        const modeIndex = this.linkModeValues.indexOf(this.currentLinkMode);
        const linkModeBtn = document.getElementById('link-mode-btn');
        if (linkModeBtn) {
            linkModeBtn.textContent = this.linkModeNames[modeIndex] || this.linkModeNames[0];
            linkModeBtn.title = `Link style: ${this.linkModeNames[modeIndex] || this.linkModeNames[0]} (click to cycle)`;
        }
    }

    // Save/restore link mode for graph serialization
    saveToGraphConfig(graphData: any): void {
        if (!graphData.config) graphData.config = {};
        (graphData.config as any).linkRenderMode = this.currentLinkMode;
    }

    restoreFromGraphConfig(graphData: any): void {
        if (typeof (graphData.config as any)?.linkRenderMode === 'number') {
            this.applyLinkMode((graphData.config as any).linkRenderMode);
        }
    }
}
