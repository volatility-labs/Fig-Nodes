import BaseCustomNode from '../base/BaseCustomNode';
import { LiteGraph } from '@fig-node/litegraph';
import { NodeRenderer } from '../utils/NodeRenderer';

class OHLCVPlotRenderer extends NodeRenderer {
    onDrawForeground(ctx: CanvasRenderingContext2D) {
        const node = this.node as OHLCVPlotNodeUI;
        node.drawPlots(ctx);
        this.drawHighlight(ctx);
        this.drawProgressBar(ctx);
        this.drawError(ctx);
    }
}

export default class OHLCVPlotNodeUI extends BaseCustomNode {
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
        this.renderer = new OHLCVPlotRenderer(this);
    }

    // Override onMouseDown to ensure node can be selected properly
    // Return false to allow normal node selection behavior
    onMouseDown(event: any, pos: [number, number], canvas: any): boolean {
        // Allow normal node selection - don't interfere with it
        return false;
    }

    /**
     * Reset chart view to default zoom and scroll position
     */
    resetChartView(): void {
        this.zoomLevel = 1.0;
        this.scrollOffsetX = 0;
        this.scrollOffsetY = 0;
        this.gridScrollOffset = 0;
        this.gridScrollOffsetX = 0;
        this.setDirtyCanvas(true, true);
        if (this.graph) {
            this.graph.setDirtyCanvas(true);
        }
    }

    /**
     * Override getMenuOptions to add "Reset chart view" option
     */
    getMenuOptions(canvas: any): any[] {
        const baseOptions = super.getMenuOptions ? super.getMenuOptions(canvas) : [];
        return [
            {
                content: "Reset chart view",
                callback: () => {
                    this.resetChartView();
                },
            },
            ...(baseOptions.length > 0 ? [null, ...baseOptions] : baseOptions),
        ];
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
            const cellSpacing = 4;
            
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

        // White background for uniform appearance (like ImageDisplay)
        ctx.fillStyle = '#ffffff';
        ctx.fillRect(x0, y0, w, h);

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
                // Fit image preserving aspect ratio
                const imageArea = this.fitImageToBounds(img.width, img.height, w, h);
                ctx.drawImage(img, x0 + imageArea.x, y0 + imageArea.y, imageArea.width, imageArea.height);
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

        // Multi-image grid with finite scrolling and zooming
        const cols = Math.ceil(Math.sqrt(labels.length));
        const rows = Math.ceil(labels.length / cols);
        const cellSpacing = 4;
        const baseCellW = Math.floor((w - (cols - 1) * cellSpacing) / cols);
        const baseCellH = Math.floor((h - (rows - 1) * cellSpacing) / rows);

        // Apply zoom to cell dimensions
        const cellW = baseCellW * this.zoomLevel;
        const cellH = baseCellH * this.zoomLevel;
        
        // Calculate total grid dimensions (FINITE scrolling)
        const totalGridHeight = rows * cellH + (rows - 1) * cellSpacing;
        const totalGridWidth = cols * cellW + (cols - 1) * cellSpacing;
        
        // Clamp scroll offsets to prevent scrolling beyond content
        const maxScrollY = Math.max(0, totalGridHeight - h);
        const maxScrollX = Math.max(0, totalGridWidth - w);
        this.gridScrollOffset = Math.max(0, Math.min(maxScrollY, this.gridScrollOffset));
        this.gridScrollOffsetX = Math.max(0, Math.min(maxScrollX, this.gridScrollOffsetX));

        // Draw grid with finite scrolling
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

                // Draw subtle background for each chart (like ImageDisplay)
                ctx.fillStyle = '#fafafa'; // Very light gray background for separation
                ctx.fillRect(cx, cy, cellW, cellH);

                // Image - fit preserving aspect ratio
                if (img) {
                    // Add padding inside the cell for better visual separation
                    const padding = 4;
                    const imageArea = this.fitImageToBounds(img.width, img.height, cellW - padding * 2, cellH - padding * 2);
                    ctx.drawImage(
                        img,
                        cx + padding + imageArea.x,
                        cy + padding + imageArea.y,
                        imageArea.width,
                        imageArea.height
                    );
                }

                // Draw border around each chart (like ImageDisplay)
                ctx.strokeStyle = '#d0d0d0'; // Medium gray border for clear separation
                ctx.lineWidth = 2; // Thicker border for better visibility
                ctx.strokeRect(cx + 0.5, cy + 0.5, cellW - 1, cellH - 1);
            }
        }
        
        // Draw scrollbars for grid if needed
        if (maxScrollY > 0) {
            this.drawVerticalScrollbar(ctx, x0 + w, y0, w, h, totalGridHeight, h);
        }
        if (maxScrollX > 0) {
            this.drawHorizontalScrollbar(ctx, x0, y0 + h, w, h, totalGridWidth, w);
        }
        
        ctx.restore();
    }

    // Handle mouse wheel events for scrolling and zooming
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

        // Check for zoom (Shift key held)
        const isSelected = nodeWithFlags.selected || false;
        const shiftPressed = event.shiftKey;
        
        if (shiftPressed && isSelected) {
            // Zoom mode
            const zoomSpeed = 0.001;
            const zoomDelta = event.deltaY * zoomSpeed;
            this.zoomLevel = Math.max(1.0, Math.min(5.0, this.zoomLevel - zoomDelta));
            this.setDirtyCanvas(true, true);
            return true;
        }

        // Check if mouse is within node bounds
        if (pos[0] < 0 || pos[0] > nodeWithFlags.size[0] || pos[1] < startY || pos[1] > nodeWithFlags.size[1]) {
            return false;
        }

        const labels = Object.keys(this.images);
        
        if (labels.length !== 1) {
            // Multi-image grid scrolling
            const cols = Math.ceil(Math.sqrt(labels.length));
            const rows = Math.ceil(labels.length / cols);
            const cellSpacing = 4;
            const baseCellW = Math.floor((contentWidth - (cols - 1) * cellSpacing) / cols);
            const baseCellH = Math.floor((contentHeight - (rows - 1) * cellSpacing) / rows);
            const cellW = baseCellW * this.zoomLevel;
            const cellH = baseCellH * this.zoomLevel;
            
            const totalGridHeight = rows * cellH + (rows - 1) * cellSpacing;
            const totalGridWidth = cols * cellW + (cols - 1) * cellSpacing;
            
            const maxScrollY = Math.max(0, totalGridHeight - contentHeight);
            const maxScrollX = Math.max(0, totalGridWidth - contentWidth);
            
            const isHorizontal = Math.abs(event.deltaX) > Math.abs(event.deltaY);
            let scrollAmount = event.deltaMode === 0 ? (isHorizontal ? event.deltaX * 0.8 : event.deltaY * 0.8) : 
                             event.deltaMode === 1 ? (isHorizontal ? event.deltaX * 20 : event.deltaY * 20) :
                             (isHorizontal ? event.deltaX * contentWidth : event.deltaY * contentHeight);
            
            if (isHorizontal && maxScrollX > 0) {
                this.gridScrollOffsetX = Math.max(0, Math.min(maxScrollX, this.gridScrollOffsetX + scrollAmount));
            } else if (!isHorizontal && maxScrollY > 0) {
                this.gridScrollOffset = Math.max(0, Math.min(maxScrollY, this.gridScrollOffset + scrollAmount));
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
        let scrollAmount = event.deltaMode === 0 ? (isHorizontal ? event.deltaX * 0.8 : event.deltaY * 0.8) : 
                         event.deltaMode === 1 ? (isHorizontal ? event.deltaX * 20 : event.deltaY * 20) :
                         (isHorizontal ? event.deltaX * contentWidth : event.deltaY * contentHeight);

        if (isHorizontal && maxScrollX > 0) {
            this.scrollOffsetX = Math.max(0, Math.min(maxScrollX, this.scrollOffsetX + scrollAmount));
        } else if (!isHorizontal && maxScrollY > 0) {
            this.scrollOffsetY = Math.max(0, Math.min(maxScrollY, this.scrollOffsetY + scrollAmount));
        }

        this.setDirtyCanvas(true, true);
        return true;
    }

    private drawVerticalScrollbar(ctx: CanvasRenderingContext2D, scrollbarX: number, startY: number, visibleWidth: number, visibleHeight: number, totalHeight: number, viewportHeight: number) {
        const scrollbarWidth = 8;
        const scrollbarHeight = viewportHeight;
        
        // Scrollbar track
        ctx.fillStyle = 'rgba(100, 100, 100, 0.3)';
        ctx.fillRect(scrollbarX, startY, scrollbarWidth, scrollbarHeight);

        // Scrollbar thumb
        const maxScroll = Math.max(0, totalHeight - viewportHeight);
        if (maxScroll <= 0) return;
        
        const thumbHeight = Math.max(20, (viewportHeight / totalHeight) * scrollbarHeight);
        const scrollRatio = maxScroll > 0 ? this.scrollOffsetY / maxScroll : 0;
        const thumbY = startY + scrollRatio * (scrollbarHeight - thumbHeight);
        
        ctx.fillStyle = 'rgba(150, 150, 150, 0.7)';
        ctx.fillRect(scrollbarX, thumbY, scrollbarWidth, thumbHeight);
    }

    private drawHorizontalScrollbar(ctx: CanvasRenderingContext2D, startX: number, scrollbarY: number, visibleWidth: number, visibleHeight: number, totalWidth: number, viewportWidth: number) {
        const scrollbarHeight = 8;
        const scrollbarWidth = viewportWidth;
        
        // Scrollbar track
        ctx.fillStyle = 'rgba(100, 100, 100, 0.3)';
        ctx.fillRect(startX, scrollbarY, scrollbarWidth, scrollbarHeight);

        // Scrollbar thumb
        const maxScroll = Math.max(0, totalWidth - viewportWidth);
        if (maxScroll <= 0) return;
        
        const thumbWidth = Math.max(20, (viewportWidth / totalWidth) * scrollbarWidth);
        const scrollRatio = maxScroll > 0 ? this.scrollOffsetX / maxScroll : 0;
        const thumbX = startX + scrollRatio * (scrollbarWidth - thumbWidth);
        
        ctx.fillStyle = 'rgba(150, 150, 150, 0.7)';
        ctx.fillRect(thumbX, scrollbarY, thumbWidth, scrollbarHeight);
    }
}


