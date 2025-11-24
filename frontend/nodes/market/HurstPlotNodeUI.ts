import BaseCustomNode from '../base/BaseCustomNode';
import { LiteGraph } from '@fig-node/litegraph';
import { NodeRenderer } from '../utils/NodeRenderer';

class HurstPlotRenderer extends NodeRenderer {
    onDrawForeground(ctx: CanvasRenderingContext2D) {
        const node = this.node as HurstPlotNodeUI;
        node.drawPlots(ctx);
        this.drawHighlight(ctx);
        this.drawProgressBar(ctx);
        this.drawError(ctx);
    }
}

export default class HurstPlotNodeUI extends BaseCustomNode {
    private images: { [label: string]: string } = {};
    private loadedImages: Map<string, HTMLImageElement> = new Map();
    private imageAspectRatios: Map<string, number> = new Map();
    private scrollOffsetX: number = 0;
    private scrollOffsetY: number = 0;
    private maxVisibleWidth: number = 500;
    private maxVisibleHeight: number = 480;
    private gridScrollOffset: number = 0; // For multi-image grid vertical scrolling
    private gridScrollOffsetX: number = 0; // For multi-image grid horizontal scrolling
    private zoomLevel: number = 1.0; // Zoom level (1.0 = 100%, >1.0 = zoomed in, <1.0 = zoomed out)

    constructor(title: string, data: any, serviceRegistry: any) {
        super(title, data, serviceRegistry);
        this.size = [500, 480]; // Taller for 2-panel chart (price + waves)
        this.displayResults = false; // custom canvas rendering
        this.renderer = new HurstPlotRenderer(this);
        this.maxVisibleWidth = 500;
        this.maxVisibleHeight = 480;
        
        // Enable resizing with larger corner handles
        this.resizable = true;
    }

    updateDisplay(result: any) {
        // Images are only available via output - don't load or display them here
        const imgs = (result && result.images) || {};
        this.images = imgs; // Store for status message only
        this.loadedImages.clear(); // Don't load images since we're not displaying them
        this.imageAspectRatios.clear();
        
        // Just update the display to show status message
        this.setDirtyCanvas(true, true);
    }

    // Removed resizeNodeToMatchAspectRatio and fitImageToBounds - images are not displayed in this node

    drawPlots(ctx: CanvasRenderingContext2D) {
        if (!ctx || typeof ctx.fillRect !== 'function') {
            return;
        }
        // Images are only available via the "images" output - connect to ImageDisplay node to view
        const labels = Object.keys(this.images || {});
        const padding = 12;
        const widgetSpacing = 8;
        const widgetHeight = this.widgets ? this.widgets.length * LiteGraph.NODE_WIDGET_HEIGHT : 0;
        const x0 = padding;
        const y0 = LiteGraph.NODE_TITLE_HEIGHT + widgetHeight + widgetSpacing + padding;
        const w = Math.max(0, this.size[0] - padding * 2);
        const h = Math.max(0, this.size[1] - LiteGraph.NODE_TITLE_HEIGHT - widgetHeight - widgetSpacing - padding * 2);

        // Draw separator line between widgets and content
        if (widgetHeight > 0) {
            ctx.strokeStyle = 'rgba(75, 85, 99, 0.2)';
            ctx.lineWidth = 1;
            ctx.beginPath();
            ctx.moveTo(x0, LiteGraph.NODE_TITLE_HEIGHT + widgetHeight + widgetSpacing / 2);
            ctx.lineTo(x0 + w, LiteGraph.NODE_TITLE_HEIGHT + widgetHeight + widgetSpacing / 2);
            ctx.stroke();
        }

        // Show status message - no background/border needed, node background is already drawn
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

    // Disable mouse wheel handling since images are not displayed in this node
    onMouseWheel(event: WheelEvent, pos: [number, number], _canvas: any): boolean {
        // Images are only available via output - no scrolling/zooming needed here
            return false;
        }

    // Removed unused scrollbar drawing methods - images are displayed via ImageDisplay node

    // Override onMouseDown to make resize handles easier to click (larger corner area)
    onMouseDown(event: any, pos: [number, number], canvas: any): boolean {
        if (!this.resizable) {
            return super.onMouseDown?.(event, pos, canvas) ?? false;
        }

        const RESIZE_HANDLE_SIZE = 30; // Larger resize handle area (default is ~10-15px)
        const nodeWidth = this.size[0];
        const nodeHeight = this.size[1];
        
        // Check if click is in any corner resize area
        const inTopLeft = pos[0] <= RESIZE_HANDLE_SIZE && pos[1] <= RESIZE_HANDLE_SIZE;
        const inTopRight = pos[0] >= nodeWidth - RESIZE_HANDLE_SIZE && pos[1] <= RESIZE_HANDLE_SIZE;
        const inBottomLeft = pos[0] <= RESIZE_HANDLE_SIZE && pos[1] >= nodeHeight - RESIZE_HANDLE_SIZE;
        const inBottomRight = pos[0] >= nodeWidth - RESIZE_HANDLE_SIZE && pos[1] >= nodeHeight - RESIZE_HANDLE_SIZE;
        
        // If clicking in a corner, adjust the position to be closer to the actual corner
        // This helps LiteGraph's built-in resize detection work better
        if (inTopLeft || inTopRight || inBottomLeft || inBottomRight) {
            const adjustedPos: [number, number] = [
                inTopLeft || inBottomLeft ? 0 : (inTopRight || inBottomRight ? nodeWidth : pos[0]),
                inTopLeft || inTopRight ? 0 : (inBottomLeft || inBottomRight ? nodeHeight : pos[1])
            ];
            return super.onMouseDown?.(event, adjustedPos, canvas) ?? false;
        }
        
        // For non-corner clicks, use normal handling
        return super.onMouseDown?.(event, pos, canvas) ?? false;
    }
}

