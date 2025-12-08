import BaseCustomNode from '../base/BaseCustomNode';
import { LiteGraph } from '@fig-node/litegraph';
import { NodeRenderer } from '../utils/NodeRenderer';

class StochasticHeatmapPlotRenderer extends NodeRenderer {
    onDrawForeground(ctx: CanvasRenderingContext2D) {
        const node = this.node as StochasticHeatmapPlotNodeUI;
        node.drawPlots(ctx);
        this.drawHighlight(ctx);
        this.drawProgressBar(ctx);
        this.drawError(ctx);
    }
}

export default class StochasticHeatmapPlotNodeUI extends BaseCustomNode {
    private images: { [label: string]: string } = {};
    private loadedImages: Map<string, HTMLImageElement> = new Map();
    private imageAspectRatios: Map<string, number> = new Map();

    constructor(title: string, data: any, serviceRegistry: any) {
        super(title, data, serviceRegistry);
        this.size = [500, 480];
        this.displayResults = false;
        this.renderer = new StochasticHeatmapPlotRenderer(this);
        this.resizable = true;
    }

    updateDisplay(result: any) {
        const imgs = (result && result.images) || {};
        this.images = imgs;
        this.loadedImages.clear();
        this.imageAspectRatios.clear();
        
        this.setDirtyCanvas(true, true);
    }

    onExecute(nodeData: any): void {
        // Images are output via the output port - propagate to connected nodes
        const imagesOutputIndex = this.findOutputSlotIndex('images');
        if (imagesOutputIndex >= 0 && nodeData.images) {
            this.setOutputData(imagesOutputIndex, nodeData.images);
            
            // Manually propagate to connected nodes (like ImageDisplay)
            if (this.graph && this.outputs && this.outputs[imagesOutputIndex]) {
                const outputSlot = this.outputs[imagesOutputIndex];
                if (outputSlot.links) {
                    for (const linkId of outputSlot.links) {
                        const link = this.graph._links.get(linkId);
                        if (link) {
                            const targetNode = this.graph.getNodeById(link.target_id);
                            if (targetNode && typeof (targetNode as any).updateDisplay === 'function') {
                                (targetNode as any).updateDisplay({ images: nodeData.images });
                            }
                        }
                    }
                }
            }
        }
        this.setDirtyCanvas(true, true);
    }

    drawPlots(ctx: CanvasRenderingContext2D) {
        if (!ctx || typeof ctx.fillRect !== 'function') {
            return;
        }
        const labels = Object.keys(this.images || {});
        const padding = 12;
        const widgetSpacing = 8;
        const widgetHeight = this.widgets ? this.widgets.length * LiteGraph.NODE_WIDGET_HEIGHT : 0;
        const x0 = padding;
        const y0 = LiteGraph.NODE_TITLE_HEIGHT + widgetHeight + widgetSpacing + padding;
        const w = Math.max(0, this.size[0] - padding * 2);
        const h = Math.max(0, this.size[1] - LiteGraph.NODE_TITLE_HEIGHT - widgetHeight - widgetSpacing - padding * 2);

        if (widgetHeight > 0) {
            ctx.strokeStyle = 'rgba(75, 85, 99, 0.2)';
            ctx.lineWidth = 1;
            ctx.beginPath();
            ctx.moveTo(x0, LiteGraph.NODE_TITLE_HEIGHT + widgetHeight + widgetSpacing / 2);
            ctx.lineTo(x0 + w, LiteGraph.NODE_TITLE_HEIGHT + widgetHeight + widgetSpacing / 2);
            ctx.stroke();
        }

        const centerX = x0 + w / 2;
        const centerY = y0 + h / 2;
        
        ctx.fillStyle = 'rgba(156, 163, 175, 0.6)';
        ctx.font = '12px Arial';
        ctx.textAlign = 'center';
        ctx.textBaseline = 'middle';
        
        if (labels.length > 0) {
            ctx.fillText(`Images available via output (${labels.length} chart${labels.length > 1 ? 's' : ''})`, centerX, centerY - 10);
            ctx.fillText('Connect to ImageDisplay node to view', centerX, centerY + 10);
        } else {
            ctx.fillText('No charts generated yet', centerX, centerY);
        }
    }
}

