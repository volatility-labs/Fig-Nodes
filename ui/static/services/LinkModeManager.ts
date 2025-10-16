import { LGraphCanvas, LiteGraph } from '@comfyorg/litegraph';
import type { GraphData } from '../types/litegraph-extensions';

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

        if (typeof this.canvas.setDirty === 'function') {
            this.canvas.setDirty(true, true);
        }

        this.updateButtonLabel();
    }

    cycleLinkMode(): void {
        const currentIndex = this.linkModeValues.indexOf(this.currentLinkMode);
        const nextIndex = (currentIndex + 1) % this.linkModeValues.length;
        const nextMode = this.linkModeValues[nextIndex];
        if (nextMode !== undefined) {
            this.applyLinkMode(nextMode);
        }
    }

    getCurrentLinkMode(): number {
        return this.currentLinkMode;
    }

    getLinkModeName(mode?: number): string {
        const targetMode = mode ?? this.currentLinkMode;
        const modeIndex = this.linkModeValues.indexOf(targetMode);
        return this.linkModeNames[modeIndex] || this.linkModeNames[0] || 'Curved';
    }

    private updateButtonLabel(): void {
        const modeIndex = this.linkModeValues.indexOf(this.currentLinkMode);
        const linkModeBtn = document.getElementById('link-mode-btn');
        if (linkModeBtn) {
            const modeName = this.linkModeNames[modeIndex] || this.linkModeNames[0] || 'Curved';
            linkModeBtn.textContent = modeName;
            linkModeBtn.title = `Link style: ${modeName} (click to cycle)`;
        }
    }

    // Save/restore link mode for graph serialization
    saveToGraphConfig(graphData: GraphData): void {
        if (!graphData.config) graphData.config = {};
        graphData.config.linkRenderMode = this.currentLinkMode;
    }

    restoreFromGraphConfig(graphData: GraphData): void {
        // Check both config and extra for linkRenderMode (extra is the current format)
        const linkRenderMode = graphData.extra?.linkRenderMode ?? graphData.config?.linkRenderMode;
        if (typeof linkRenderMode === 'number') {
            this.applyLinkMode(linkRenderMode);
        }
    }
}
