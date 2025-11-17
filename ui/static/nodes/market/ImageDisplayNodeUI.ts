import BaseCustomNode from '../base/BaseCustomNode';
import { LiteGraph } from '@comfyorg/litegraph';
import { NodeRenderer } from '../utils/NodeRenderer';

class ImageDisplayRenderer extends NodeRenderer {
    onDrawForeground(ctx: CanvasRenderingContext2D) {
        const node = this.node as ImageDisplayNodeUI;
        node.drawPlots(ctx);
        this.drawHighlight(ctx);
        this.drawProgressBar(ctx);
        this.drawError(ctx);
    }
}

export default class ImageDisplayNodeUI extends BaseCustomNode {
    private images: { [label: string]: string } = {};
    private loadedImages: Map<string, HTMLImageElement> = new Map();
    private imageAspectRatios: Map<string, number> = new Map();

    constructor(title: string, data: any, serviceRegistry: any) {
        super(title, data, serviceRegistry);
        this.size = [500, 360];
        this.displayResults = false; // custom canvas rendering
        this.renderer = new ImageDisplayRenderer(this);
    }

    updateDisplay(result: any) {
        // Expect { images: { label: dataUrl } }
        const imgs = (result && result.images) || {};
        this.images = imgs;
        this.loadedImages.clear();
        this.imageAspectRatios.clear();
        
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

        // White background for uniform appearance
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
            ctx.fillText('No images to display', centerX, centerY);
            
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

        // Compute grid for multiple images
        const cols = Math.ceil(Math.sqrt(labels.length));
        const rows = Math.ceil(labels.length / cols);
        const cellSpacing = 2; // Small uniform spacing between images
        // Apply zoom to grid cell sizes for multi-image grids
        const baseCellW = Math.floor((w - (cols - 1) * cellSpacing) / cols);
        const baseCellH = Math.floor((h - (rows - 1) * cellSpacing) / rows);
        const cellW = baseCellW * this.zoomLevel;
        const cellH = baseCellH * this.zoomLevel;
        
        // Calculate total grid dimensions for infinite scrolling
        const totalGridHeight = rows * cellH + (rows - 1) * cellSpacing;
        const scrollBuffer = Math.max(50, totalGridHeight * 0.1);
        const scrollableHeight = totalGridHeight + scrollBuffer;
        
        const totalGridWidth = cols * cellW + (cols - 1) * cellSpacing;
        const scrollBufferX = Math.max(50, totalGridWidth * 0.1);
        const scrollableWidth = totalGridWidth + scrollBufferX;
        
        // Wrap scroll offsets for infinite scrolling
        if (scrollableHeight > 0) {
            this.gridScrollOffset = ((this.gridScrollOffset % scrollableHeight) + scrollableHeight) % scrollableHeight;
        }
        if (scrollableWidth > 0) {
            this.gridScrollOffsetX = ((this.gridScrollOffsetX % scrollableWidth) + scrollableWidth) % scrollableWidth;
        }

        // Draw each image into a cell
        let idx = 0;
        for (let r = 0; r < rows; r++) {
            for (let c = 0; c < cols; c++) {
                if (idx >= labels.length) break;
                const label = labels[idx++];
                if (!label) continue;
                const img = this.loadedImages.get(label);

                const cx = x0 + c * (cellW + cellSpacing);
                const cy = y0 + r * (cellH + cellSpacing);

                // Skip drawing if cell is completely outside visible area
                if (cy + cellH < y0 || cy > y0 + h || cx + cellW < x0 || cx > x0 + w) continue;

                // Image - stretch to fill entire cell for uniform grid appearance
                if (img) {
                    // Stretch image to fill cell completely (ignore aspect ratio for grid uniformity)
                    ctx.drawImage(
                        img,
                        cx,
                        cy,
                        cellW,
                        cellH
                    );
                }
                // No borders - seamless grid appearance
            }
        }
        
        ctx.restore();
    }

    // Handle mouse wheel events for zoom and scrolling
    onMouseWheel(event: WheelEvent, pos: [number, number], _canvas: any): boolean {
        const nodeWithFlags = this as { flags?: { collapsed?: boolean }; size: [number, number] };
        
        if (nodeWithFlags.flags?.collapsed || !this.images || Object.keys(this.images).length === 0) {
            return false;
        }

        const padding = 12;
        const widgetSpacing = 8;
        const widgetHeight = this.widgets ? this.widgets.length * LiteGraph.NODE_WIDGET_HEIGHT : 0;
        const startY = LiteGraph.NODE_TITLE_HEIGHT + widgetHeight + widgetSpacing + padding;
        const contentWidth = Math.max(0, nodeWithFlags.size[0] - padding * 2);
        const contentHeight = Math.max(0, nodeWithFlags.size[1] - LiteGraph.NODE_TITLE_HEIGHT - widgetHeight - widgetSpacing - padding * 2);

        // CHECK SHIFT KEY FIRST - Shift+scroll = zoom (for image zoom within node)
        const shiftPressed = event.shiftKey || (event.getModifierState && event.getModifierState('Shift'));
        
        if (shiftPressed) {
            // Zoom mode: use scroll delta to adjust zoom level
            // Check if mouse is within node bounds (more lenient for zoom)
            const isInBounds = pos[0] >= -100 && pos[0] <= nodeWithFlags.size[0] + 100 && 
                              pos[1] >= startY - 100 && pos[1] <= nodeWithFlags.size[1] + 100;
            
            if (isInBounds) {
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
            return true; // Still return true to prevent default scrolling behavior when Shift is held
        }

        // Check if mouse is within node bounds (for scrolling)
        if (pos[0] < 0 || pos[0] > nodeWithFlags.size[0] || pos[1] < startY || pos[1] > nodeWithFlags.size[1]) {
            return false;
        }

        const labels = Object.keys(this.images);
        
        if (labels.length !== 1) {
            // Multi-image grid scrolling with infinite scroll
            const cols = Math.ceil(Math.sqrt(labels.length));
            const rows = Math.ceil(labels.length / cols);
            const cellSpacing = 2; // Small uniform spacing between images
            const baseCellW = Math.floor((contentWidth - (cols - 1) * cellSpacing) / cols);
            const baseCellH = Math.floor((contentHeight - (rows - 1) * cellSpacing) / rows);
            const cellW = baseCellW * this.zoomLevel;
            const cellH = baseCellH * this.zoomLevel;
            
            const totalGridHeight = rows * cellH + (rows - 1) * cellSpacing;
            const scrollBuffer = Math.max(50, totalGridHeight * 0.1);
            const scrollableHeight = totalGridHeight + scrollBuffer;
            
            const totalGridWidth = cols * cellW + (cols - 1) * cellSpacing;
            const scrollBufferX = Math.max(50, totalGridWidth * 0.1);
            const scrollableWidth = totalGridWidth + scrollBufferX;
            
            // Determine scroll direction
            const isHorizontal = Math.abs(event.deltaX) > Math.abs(event.deltaY);
            
            let scrollAmount: number;
            if (event.deltaMode === 0) {
                scrollAmount = isHorizontal ? event.deltaX * 0.8 : event.deltaY * 0.8;
            } else if (event.deltaMode === 1) {
                scrollAmount = isHorizontal ? event.deltaX * 20 : event.deltaY * 20;
            } else {
                scrollAmount = isHorizontal ? event.deltaX * contentWidth : event.deltaY * contentHeight;
            }
            
            // Infinite scrolling with wrapping
            if (isHorizontal && scrollableWidth > 0) {
                this.gridScrollOffsetX = ((this.gridScrollOffsetX + scrollAmount) % scrollableWidth + scrollableWidth) % scrollableWidth;
            } else if (!isHorizontal && scrollableHeight > 0) {
                this.gridScrollOffset = ((this.gridScrollOffset + scrollAmount) % scrollableHeight + scrollableHeight) % scrollableHeight;
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
>>>>>>> Stashed changes
    }
}


