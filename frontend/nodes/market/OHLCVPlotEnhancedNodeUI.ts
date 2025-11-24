import BaseCustomNode from '../base/BaseCustomNode';
import { LiteGraph } from '@fig-node/litegraph';
import { NodeRenderer } from '../utils/NodeRenderer';

class OHLCVPlotEnhancedRenderer extends NodeRenderer {
    onDrawForeground(ctx: CanvasRenderingContext2D) {
        const node = this.node as OHLCVPlotEnhancedNodeUI;
        node.drawPlots(ctx);
        this.drawHighlight(ctx);
        this.drawProgressBar(ctx);
        this.drawError(ctx);
    }
}

export default class OHLCVPlotEnhancedNodeUI extends BaseCustomNode {
    private images: { [label: string]: string } = {};
    private loadedImages: Map<string, HTMLImageElement> = new Map();
    private imageAspectRatios: Map<string, number> = new Map();
    private scrollOffsetX: number = 0;
    private scrollOffsetY: number = 0;
    private gridScrollOffset: number = 0; // For multi-image grid vertical scrolling
    private gridScrollOffsetX: number = 0; // For multi-image grid horizontal scrolling
    private zoomLevel: number = 1.0; // Zoom level (1.0 = 100% original size, >1.0 = zoomed in, clamped between 1.0 and 5.0)

    constructor(title: string, data: any, serviceRegistry: any) {
        super(title, data, serviceRegistry);
        this.size = [500, 360];
        this.displayResults = false; // custom canvas rendering
        this.renderer = new OHLCVPlotEnhancedRenderer(this);
    }

    // Override onMouseDown to ensure node can be selected properly
    // Return false to allow normal node selection behavior
    onMouseDown(event: any, pos: [number, number], canvas: any): boolean {
        // Allow normal node selection - don't interfere with it
        return false;
    }

    updateDisplay(result: any) {
        // Expect { images: { label: dataUrl } }
        const imgs = (result && result.images) || {};
        this.images = imgs;
        this.loadedImages.clear();
        this.imageAspectRatios.clear();
        // Reset scroll offsets and zoom when new images are loaded
        this.scrollOffsetX = 0;
        this.scrollOffsetY = 0;
        this.gridScrollOffset = 0;
        this.gridScrollOffsetX = 0;
        this.zoomLevel = 1.0;
        
        // Preload all images and calculate aspect ratios
        let allLoaded = 0;
        const totalImages = Object.keys(imgs).length;
        
        Object.entries(imgs).forEach(([label, dataUrl]) => {
            const img = new Image();
            img.onload = () => {
                this.loadedImages.set(label, img);
                const aspectRatio = img.width / img.height;
                this.imageAspectRatios.set(label, aspectRatio);
                allLoaded++;
                
                // Resize node when all images are loaded
                if (allLoaded === totalImages) {
                    this.resizeNodeToMatchAspectRatio();
                }
                
                this.setDirtyCanvas(true, true);
            };
            img.src = dataUrl as string;
        });
        
        this.setDirtyCanvas(true, true);
    }

    private resizeNodeToMatchAspectRatio() {
        const labels = Object.keys(this.images || {});
        if (!labels.length) return;

        const widgetHeight = this.widgets ? this.widgets.length * LiteGraph.NODE_WIDGET_HEIGHT : 0;
        const padding = 12;
        const widgetSpacing = 8;
        const headerHeight = LiteGraph.NODE_TITLE_HEIGHT + widgetHeight + widgetSpacing;
        const minWidth = 400;
        const minHeight = 200;
        const maxWidth = 800;

        if (labels.length === 1) {
            // Single image: resize node to match image aspect ratio
            const label = labels[0];
            if (!label) return;
            const aspectRatio = this.imageAspectRatios.get(label);
            if (!aspectRatio) return;

            // Calculate content area dimensions
            const contentWidth = Math.max(minWidth, Math.min(maxWidth, 500));
            const contentHeight = contentWidth / aspectRatio;
            const totalHeight = headerHeight + padding * 2 + contentHeight;

            this.size[0] = contentWidth + padding * 2;
            this.size[1] = Math.max(minHeight + headerHeight, totalHeight);
        } else {
            // Multiple images: use grid layout, calculate optimal size
            const cols = Math.ceil(Math.sqrt(labels.length));
            const rows = Math.ceil(labels.length / cols);
            
            // Get average aspect ratio of all images
            const aspectRatios = Array.from(this.imageAspectRatios.values());
            const avgAspectRatio = aspectRatios.reduce((sum, ar) => sum + ar, 0) / aspectRatios.length;
            
            // Calculate cell dimensions based on average aspect ratio
            const cellSpacing = 2; // Small uniform spacing for clean grid
            
            // Target: fit cells with proper aspect ratio
            const targetCellWidth = Math.max(150, Math.min(250, 200));
            const targetCellHeight = targetCellWidth / avgAspectRatio;
            
            const contentWidth = cols * targetCellWidth + (cols - 1) * cellSpacing;
            const contentHeight = rows * targetCellHeight + (rows - 1) * cellSpacing;
            const totalHeight = headerHeight + padding * 2 + contentHeight;

            this.size[0] = Math.max(minWidth, Math.min(maxWidth, contentWidth + padding * 2));
            this.size[1] = Math.max(minHeight + headerHeight, totalHeight);
        }

        this.setDirtyCanvas(true, true);
    }

    private fitImageToBounds(
        imgWidth: number,
        imgHeight: number,
        maxWidth: number,
        maxHeight: number
    ): { width: number; height: number; x: number; y: number } {
        const imgAspectRatio = imgWidth / imgHeight;
        const containerAspectRatio = maxWidth / maxHeight;

        let width: number;
        let height: number;

        if (imgAspectRatio > containerAspectRatio) {
            // Image is wider - fit to width
            width = maxWidth;
            height = maxWidth / imgAspectRatio;
        } else {
            // Image is taller - fit to height
            height = maxHeight;
            width = maxHeight * imgAspectRatio;
        }

        // Center the image
        const x = (maxWidth - width) / 2;
        const y = (maxHeight - height) / 2;

        return { width, height, x, y };
    }

    drawPlots(ctx: CanvasRenderingContext2D) {
        // In jsdom test environments, canvas.getContext('2d') may return null.
        // Guard to no-op when a real 2D context is not available.
        if (!ctx || typeof ctx.fillRect !== 'function') {
            return;
        }
        const labels = Object.keys(this.images || {});
        const padding = 12;
        const widgetSpacing = 8; // Extra space after widgets
        const widgetHeight = this.widgets ? this.widgets.length * LiteGraph.NODE_WIDGET_HEIGHT : 0;
        const x0 = padding;
        const y0 = LiteGraph.NODE_TITLE_HEIGHT + widgetHeight + widgetSpacing + padding;
        const w = Math.max(0, this.size[0] - padding * 2);
        const h = Math.max(0, this.size[1] - LiteGraph.NODE_TITLE_HEIGHT - widgetHeight - widgetSpacing - padding * 2);

        // Draw subtle separator line between widgets and content
        if (widgetHeight > 0) {
            ctx.strokeStyle = 'rgba(75, 85, 99, 0.2)';
            ctx.lineWidth = 1;
            ctx.beginPath();
            ctx.moveTo(x0, LiteGraph.NODE_TITLE_HEIGHT + widgetHeight + widgetSpacing / 2);
            ctx.lineTo(x0 + w, LiteGraph.NODE_TITLE_HEIGHT + widgetHeight + widgetSpacing / 2);
            ctx.stroke();
        }

        // Clip to node bounds to prevent rendering outside
        ctx.save();
        ctx.beginPath();
        ctx.rect(x0, y0, w, h);
        ctx.clip();

        // Minimal flat background
        ctx.fillStyle = '#0f1419';
        ctx.fillRect(x0, y0, w, h);
        
        // Subtle rounded inner border
        ctx.strokeStyle = 'rgba(75, 85, 99, 0.2)';
        ctx.lineWidth = 1;
        ctx.strokeRect(x0 + 0.5, y0 + 0.5, w - 1, h - 1);

        if (!labels.length) {
            // Minimal empty state
            const centerX = x0 + w / 2;
            const centerY = y0 + h / 2;
            
            ctx.fillStyle = 'rgba(156, 163, 175, 0.4)';
            ctx.font = '12px Arial';
            ctx.textAlign = 'center';
            ctx.textBaseline = 'middle';
            ctx.fillText('No charts to display', centerX, centerY);
            
            ctx.restore();
            return;
        }

        // For single image, use full space with aspect ratio preservation
        if (labels.length === 1) {
            const label = labels[0];
            if (!label) {
                ctx.restore();
                return;
            }
            const img = this.loadedImages.get(label);
            if (img) {
                // Calculate actual image display size (preserving aspect ratio)
                const baseImageArea = this.fitImageToBounds(img.width, img.height, w, h);
                
                // Apply zoom: scale the image dimensions
                const zoomedWidth = baseImageArea.width * this.zoomLevel;
                const zoomedHeight = baseImageArea.height * this.zoomLevel;
                
                // Center the zoomed image
                const centerX = x0 + w / 2;
                const centerY = y0 + h / 2;
                const drawX = centerX - zoomedWidth / 2;
                const drawY = centerY - zoomedHeight / 2;
                
                // Calculate scrollable content dimensions
                const contentWidth = zoomedWidth;
                const contentHeight = zoomedHeight;
                const maxScrollX = Math.max(0, contentWidth - w);
                const maxScrollY = Math.max(0, contentHeight - h);
                
                // Clamp scroll offsets
                this.scrollOffsetX = Math.max(0, Math.min(maxScrollX, this.scrollOffsetX));
                this.scrollOffsetY = Math.max(0, Math.min(maxScrollY, this.scrollOffsetY));
                
                // Draw image with scroll offset and zoom
                ctx.drawImage(img, drawX - this.scrollOffsetX, drawY - this.scrollOffsetY, zoomedWidth, zoomedHeight);
            } else {
                // Minimal loading state
                const centerX = x0 + w / 2;
                const centerY = y0 + h / 2;
                
                ctx.fillStyle = 'rgba(156, 163, 175, 0.5)';
                ctx.font = '12px Arial';
                ctx.textAlign = 'center';
                ctx.textBaseline = 'middle';
                ctx.fillText('Loading...', centerX, centerY);
            }
            ctx.restore();
            return;
        }

        // Compute grid for multiple images
        const cols = Math.ceil(Math.sqrt(labels.length));
        const rows = Math.ceil(labels.length / cols);
        const cellSpacing = 2; // Small uniform spacing between images
        
        // Use the same target cell dimensions as calculated in resizeNodeToMatchAspectRatio
        // This ensures consistency between node sizing and drawing
        const aspectRatios = Array.from(this.imageAspectRatios.values());
        const avgAspectRatio = aspectRatios.reduce((sum, ar) => sum + ar, 0) / aspectRatios.length;
        const targetCellWidth = Math.max(150, Math.min(250, 200));
        const targetCellHeight = targetCellWidth / avgAspectRatio;
        
        // Apply zoom to the target dimensions
        const cellW = targetCellWidth * this.zoomLevel;
        const cellH = targetCellHeight * this.zoomLevel;
        
        // Calculate total grid dimensions
        const totalGridHeight = rows * cellH + (rows - 1) * cellSpacing;
        const totalGridWidth = cols * cellW + (cols - 1) * cellSpacing;
        
        // Clamp scroll offsets to valid ranges
        const maxScrollX = Math.max(0, totalGridWidth - w);
        const maxScrollY = Math.max(0, totalGridHeight - h);
        this.gridScrollOffsetX = Math.max(0, Math.min(maxScrollX, this.gridScrollOffsetX));
        this.gridScrollOffset = Math.max(0, Math.min(maxScrollY, this.gridScrollOffset));

        // Save the current context state before drawing grid
        ctx.save();
        
        // Set up clipping region for the content area only
        ctx.beginPath();
        ctx.rect(x0, y0, w, h);
        ctx.clip();

        // Draw grid with scroll offset (simple clamped scrolling)
        const baseX = x0 - this.gridScrollOffsetX;
        const baseY = y0 - this.gridScrollOffset;
        
        // Draw each image into a cell with scroll offset
        let idx = 0;
        for (let r = 0; r < rows; r++) {
            for (let c = 0; c < cols; c++) {
                if (idx >= labels.length) break;
                const label = labels[idx++];
                if (!label) continue;
                const img = this.loadedImages.get(label);

                const cx = baseX + c * (cellW + cellSpacing);
                const cy = baseY + r * (cellH + cellSpacing);

                // Skip drawing if cell is completely outside visible area
                if (cy + cellH < y0 || cy > y0 + h || cx + cellW < x0 || cx > x0 + w) continue;

                // Image - fit within cell preserving aspect ratio
                if (img) {
                    // Fit image within cell while preserving aspect ratio
                    const imageArea = this.fitImageToBounds(img.width, img.height, cellW, cellH);
                    ctx.drawImage(
                        img,
                        cx + imageArea.x,
                        cy + imageArea.y,
                        imageArea.width,
                        imageArea.height
                    );
                }
                // No borders - seamless grid appearance
            }
        }
        
        // Restore context state to remove clipping
        ctx.restore();
        
        // Restore the initial clipping save
        ctx.restore();
    }

    // Handle mouse wheel events for zoom and scrolling
    onMouseWheel(event: WheelEvent, pos: [number, number], canvas: any): boolean {
        const nodeWithFlags = this as { flags?: { collapsed?: boolean }; size: [number, number]; selected?: boolean };
        
        if (nodeWithFlags.flags?.collapsed || !this.images || Object.keys(this.images).length === 0) {
            return false;
        }

        const padding = 12;
        const widgetSpacing = 8;
        const widgetHeight = this.widgets ? this.widgets.length * LiteGraph.NODE_WIDGET_HEIGHT : 0;
        const startY = LiteGraph.NODE_TITLE_HEIGHT + widgetHeight + widgetSpacing + padding;
        const contentWidth = Math.max(0, nodeWithFlags.size[0] - padding * 2);
        const contentHeight = Math.max(0, nodeWithFlags.size[1] - LiteGraph.NODE_TITLE_HEIGHT - widgetHeight - widgetSpacing - padding * 2);

        // Check if node is selected (for zoom when selected)
        const isSelected = nodeWithFlags.selected || (canvas?.selected_nodes && canvas.selected_nodes[this.id]);
        
        // CHECK SHIFT KEY FIRST - Shift+scroll = zoom (for chart zoom within node)
        // Allow zoom if Shift is held AND (mouse is over node OR node is selected)
        const shiftPressed = event.shiftKey || (event.getModifierState && event.getModifierState('Shift'));
        
        if (shiftPressed) {
            // Zoom mode: use scroll delta to adjust zoom level
            // Allow zoom if mouse is over node OR node is selected (for zoom when selected)
            // Use larger bounds for Mac trackpad - check if mouse is anywhere near the node
            const zoomBoundsMargin = 200; // Very large margin for Mac trackpad
            const isInBounds = pos[0] >= -zoomBoundsMargin && pos[0] <= nodeWithFlags.size[0] + zoomBoundsMargin && 
                              pos[1] >= startY - zoomBoundsMargin && pos[1] <= nodeWithFlags.size[1] + zoomBoundsMargin;
            
            // Always allow zoom if node is selected, regardless of mouse position
            if (isInBounds || isSelected) {
                // Use deltaY for zoom (scroll up = zoom in, scroll down = zoom out)
                // Reduced sensitivity for smoother, more controlled zooming
                const zoomSpeed = event.deltaMode === 0 ? 0.03 : 0.01; // Reduced sensitivity for both trackpad and mouse wheel
                const zoomDelta = -event.deltaY * zoomSpeed; // Negative so scroll up zooms in
                // Limit zoom: minimum 1.0 (original size), maximum 5.0 (500% zoom)
                this.zoomLevel = Math.max(1.0, Math.min(5.0, this.zoomLevel + zoomDelta));
                
                // Force immediate redraw with multiple methods to ensure it works
                this.setDirtyCanvas(true, true);
                
                // Also trigger canvas/graph updates
                if (this.graph) {
                    this.graph.setDirtyCanvas(true);
                }
                
                // Force redraw via requestAnimationFrame as fallback
                requestAnimationFrame(() => {
                    this.setDirtyCanvas(true, true);
                    if (this.graph) {
                        this.graph.setDirtyCanvas(true);
                    }
                });
                
                return true; // Event handled - prevent scrolling
            }
            // If Shift is held but not in bounds and not selected, still prevent canvas pan
            return true;
        }

        // For scrolling: check if mouse is within node bounds OR node is selected
        // Use very lenient bounds for Mac trackpad
        const boundsMargin = 100; // Very large margin for Mac trackpad
        const isInScrollBounds = pos[0] >= -boundsMargin && pos[0] <= nodeWithFlags.size[0] + boundsMargin && 
                                 pos[1] >= startY - boundsMargin && pos[1] <= nodeWithFlags.size[1] + boundsMargin;
        
        // Always allow scrolling if node is selected, regardless of mouse position
        if (!isInScrollBounds && !isSelected) {
            return false;
        }

        const labels = Object.keys(this.images);
        
        if (labels.length !== 1) {
            // Multi-image grid scrolling
            const cols = Math.ceil(Math.sqrt(labels.length));
            const rows = Math.ceil(labels.length / cols);
            const cellSpacing = 2; // Small uniform spacing between images
            const baseCellW = Math.floor((contentWidth - (cols - 1) * cellSpacing) / cols);
            const baseCellH = Math.floor((contentHeight - (rows - 1) * cellSpacing) / rows);
            const cellW = baseCellW * this.zoomLevel;
            const cellH = baseCellH * this.zoomLevel;
            
            const totalGridHeight = rows * cellH + (rows - 1) * cellSpacing;
            const totalGridWidth = cols * cellW + (cols - 1) * cellSpacing;
            
            // Determine scroll direction - prioritize vertical scrolling for trackpad
            const hasHorizontalDelta = Math.abs(event.deltaX) > 5;
            const hasVerticalDelta = Math.abs(event.deltaY) > 5;
            const isHorizontal = hasHorizontalDelta && Math.abs(event.deltaX) > Math.abs(event.deltaY);
            
            // Calculate scroll amounts with better sensitivity
            let scrollAmountX = 0;
            let scrollAmountY = 0;
            
            if (event.deltaMode === 0) {
                // Pixel mode (trackpad/mouse wheel)
                scrollAmountX = event.deltaX * 1.2; // Increased sensitivity
                scrollAmountY = event.deltaY * 1.2; // Increased sensitivity
            } else if (event.deltaMode === 1) {
                // Line mode
                scrollAmountX = event.deltaX * 30;
                scrollAmountY = event.deltaY * 30;
            } else {
                // Page mode
                scrollAmountX = event.deltaX * contentWidth * 0.1;
                scrollAmountY = event.deltaY * contentHeight * 0.1;
            }
            
            // Apply scrolling - allow both horizontal and vertical simultaneously
            const maxScrollX = Math.max(0, totalGridWidth - contentWidth);
            const maxScrollY = Math.max(0, totalGridHeight - contentHeight);
            
            if (maxScrollX > 0 && (hasHorizontalDelta || isHorizontal)) {
                this.gridScrollOffsetX = Math.max(0, Math.min(maxScrollX, this.gridScrollOffsetX + scrollAmountX));
            }
            
            if (maxScrollY > 0 && (hasVerticalDelta || !isHorizontal)) {
                this.gridScrollOffset = Math.max(0, Math.min(maxScrollY, this.gridScrollOffset + scrollAmountY));
            }
            
            this.setDirtyCanvas(true, true);
            return true;
        }

        // Single image scrolling
        const label = labels[0];
        if (!label) return false;
        const img = this.loadedImages.get(label);
        if (!img) return false;

        const baseImageArea = this.fitImageToBounds(img.width, img.height, contentWidth, contentHeight);
        const zoomedWidth = baseImageArea.width * this.zoomLevel;
        const zoomedHeight = baseImageArea.height * this.zoomLevel;
        const maxScrollX = Math.max(0, zoomedWidth - contentWidth);
        const maxScrollY = Math.max(0, zoomedHeight - contentHeight);

        if (maxScrollX <= 0 && maxScrollY <= 0) {
            return false; // No scrolling needed
        }

        const isHorizontal = Math.abs(event.deltaX) > Math.abs(event.deltaY);
        
        let scrollAmount: number;
        if (event.deltaMode === 0) {
            scrollAmount = isHorizontal ? event.deltaX * 0.8 : event.deltaY * 0.8;
        } else if (event.deltaMode === 1) {
            scrollAmount = isHorizontal ? event.deltaX * 20 : event.deltaY * 20;
        } else {
            scrollAmount = isHorizontal ? event.deltaX * contentWidth : event.deltaY * contentHeight;
        }

        if (isHorizontal && maxScrollX > 0) {
            this.scrollOffsetX = Math.max(0, Math.min(maxScrollX, this.scrollOffsetX + scrollAmount));
        } else if (!isHorizontal && maxScrollY > 0) {
            this.scrollOffsetY = Math.max(0, Math.min(maxScrollY, this.scrollOffsetY + scrollAmount));
        }

        this.setDirtyCanvas(true, true);
        return true;
    }
}
