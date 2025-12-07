import BaseCustomNode from '../base/BaseCustomNode';
import { LiteGraph } from '@fig-node/litegraph';
import { NodeRenderer } from '../utils/NodeRenderer';

class FractalResonancePlotRenderer extends NodeRenderer {
    onDrawForeground(ctx: CanvasRenderingContext2D) {
        const node = this.node as FractalResonancePlotNodeUI;
        node.drawPlots(ctx);
        this.drawHighlight(ctx);
        this.drawProgressBar(ctx);
        this.drawError(ctx);
    }
}

export default class FractalResonancePlotNodeUI extends BaseCustomNode {
    private images: { [label: string]: string } = {};
    private loadedImages: Map<string, HTMLImageElement> = new Map();
    private imageAspectRatios: Map<string, number> = new Map();
    private scrollOffsetX: number = 0;
    private scrollOffsetY: number = 0;
    private maxVisibleWidth: number = 500;
    private maxVisibleHeight: number = 480;
    private gridScrollOffset: number = 0;
    private gridScrollOffsetX: number = 0;
    private zoomLevel: number = 1.0;

    constructor(title: string, data: any, serviceRegistry: any) {
        super(title, data, serviceRegistry);
        this.size = [500, 480];
        this.displayResults = false;
        this.renderer = new FractalResonancePlotRenderer(this);
        this.maxVisibleWidth = 500;
        this.maxVisibleHeight = 480;
        
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
        // Find the "images" output slot and set its data
        const imagesOutputIndex = this.findOutputSlotIndex('images');
        if (imagesOutputIndex >= 0 && nodeData.images) {
            // Set output data so connected nodes can receive it
            this.setOutputData(imagesOutputIndex, nodeData.images);
            
            // Manually propagate to connected nodes (like ImageDisplay)
            // This is needed because standalone execution doesn't automatically trigger connected nodes
            if (this.graph && this.outputs && this.outputs[imagesOutputIndex]) {
                const outputSlot = this.outputs[imagesOutputIndex];
                if (outputSlot.links) {
                    for (const linkId of outputSlot.links) {
                        const link = this.graph._links.get(linkId);
                        if (link) {
                            const targetNode = this.graph.getNodeById(link.target_id);
                            if (targetNode && typeof (targetNode as any).updateDisplay === 'function') {
                                // Call updateDisplay on the connected node with the images data
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

    onMouseWheel(event: WheelEvent, pos: [number, number], _canvas: any): boolean {
        return false;
    }

    onMouseDown(event: any, pos: [number, number], canvas: any): boolean {
        if (!this.resizable) {
            return super.onMouseDown?.(event, pos, canvas) ?? false;
        }

        const RESIZE_HANDLE_SIZE = 30;
        const nodeWidth = this.size[0];
        const nodeHeight = this.size[1];
        
        const inTopLeft = pos[0] <= RESIZE_HANDLE_SIZE && pos[1] <= RESIZE_HANDLE_SIZE;
        const inTopRight = pos[0] >= nodeWidth - RESIZE_HANDLE_SIZE && pos[1] <= RESIZE_HANDLE_SIZE;
        const inBottomLeft = pos[0] <= RESIZE_HANDLE_SIZE && pos[1] >= nodeHeight - RESIZE_HANDLE_SIZE;
        const inBottomRight = pos[0] >= nodeWidth - RESIZE_HANDLE_SIZE && pos[1] >= nodeHeight - RESIZE_HANDLE_SIZE;
        
        if (inTopLeft || inTopRight || inBottomLeft || inBottomRight) {
            const adjustedPos: [number, number] = [
                inTopLeft || inBottomLeft ? 0 : (inTopRight || inBottomRight ? nodeWidth : pos[0]),
                inTopLeft || inTopRight ? 0 : (inBottomLeft || inBottomRight ? nodeHeight : pos[1])
            ];
            return super.onMouseDown?.(event, adjustedPos, canvas) ?? false;
        }
        
        return super.onMouseDown?.(event, pos, canvas) ?? false;
    }
}

