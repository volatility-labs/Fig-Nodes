import BaseCustomNode from '../base/BaseCustomNode';
import { LiteGraph } from '@fig-node/litegraph';
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
    private scrollOffsetX: number = 0;
    private scrollOffsetY: number = 0;
    private gridScrollOffset: number = 0; // For multi-image grid vertical scrolling
    private gridScrollOffsetX: number = 0; // For multi-image grid horizontal scrolling
    private zoomLevel: number = 1.0; // Zoom level (1.0 = 100% original size, >1.0 = zoomed in, clamped between 1.0 and 5.0)

    constructor(title: string, data: any, serviceRegistry: any) {
        super(title, data, serviceRegistry);
        this.size = [500, 360];
        this.displayResults = false; // custom canvas rendering
        this.renderer = new ImageDisplayRenderer(this);
        
        // Add share button
        this.addWidget('button', '🔗 Share', '', () => {
            this.shareImages();
        });
        
        // Add clear chart button
        this.addWidget('button', '🗑️ Clear', '', () => {
            this.clearChart();
        });
    }

    // Override onMouseDown to ensure node can be selected properly
    // Return false to allow normal node selection behavior
    onMouseDown(event: any, pos: [number, number], canvas: any): boolean {
        // Allow normal node selection - don't interfere with it
        // Only handle if clicking on specific interactive areas (if needed in future)
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
     * Clear all images from the chart
     */
    clearChart(): void {
        this.images = {};
        this.loadedImages.clear();
        this.imageAspectRatios.clear();
        this.scrollOffsetX = 0;
        this.scrollOffsetY = 0;
        this.gridScrollOffset = 0;
        this.gridScrollOffsetX = 0;
        this.zoomLevel = 1.0;
        
        // Reset node size to default
        this.size = [500, 360];
        
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
        // Merge with existing images to support incremental updates
        const newImageCount = Object.keys(imgs).length;
        const existingImageCount = Object.keys(this.images).length;
        this.images = { ...this.images, ...imgs };
        
        // Only clear and reload if this is a full update (no existing images) or if we got all new images
        // For incremental updates, only load the new images
        const isIncrementalUpdate = existingImageCount > 0 && newImageCount < existingImageCount;
        
        if (!isIncrementalUpdate) {
            // Full update - clear everything
        this.loadedImages.clear();
        this.imageAspectRatios.clear();
        // Reset scroll offsets and zoom when new images are loaded
        this.scrollOffsetX = 0;
        this.scrollOffsetY = 0;
        this.gridScrollOffset = 0;
        this.gridScrollOffsetX = 0;
        this.zoomLevel = 1.0;
        }
        
        // Preload new images and calculate aspect ratios
        let allLoaded = 0;
        const totalImages = Object.keys(this.images).length;
        const imagesToLoad = isIncrementalUpdate ? imgs : this.images;
        
        Object.entries(imagesToLoad).forEach(([label, dataUrl]) => {
            // Skip if already loaded (for incremental updates)
            if (this.loadedImages.has(label)) {
                allLoaded++;
                if (allLoaded === totalImages) {
                    this.resizeNodeToMatchAspectRatio();
                }
                return;
            }
            
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
        // Apply zoom to grid cell sizes for multi-image grids
        const baseCellW = Math.floor((w - (cols - 1) * cellSpacing) / cols);
        const baseCellH = Math.floor((h - (rows - 1) * cellSpacing) / rows);
        const cellW = baseCellW * this.zoomLevel;
        const cellH = baseCellH * this.zoomLevel;
        
        // Calculate total grid dimensions (FINITE scrolling)
        const totalGridHeight = rows * cellH + (rows - 1) * cellSpacing;
        const totalGridWidth = cols * cellW + (cols - 1) * cellSpacing;
        
        // Clamp scroll offsets to prevent scrolling beyond content (FINITE scrolling)
        const maxScrollY = Math.max(0, totalGridHeight - h);
        const maxScrollX = Math.max(0, totalGridWidth - w);
        this.gridScrollOffset = Math.max(0, Math.min(maxScrollY, this.gridScrollOffset));
        this.gridScrollOffsetX = Math.max(0, Math.min(maxScrollX, this.gridScrollOffsetX));

        // Save the current context state before drawing grid
        ctx.save();
        
        // Set up clipping region for the content area only
        ctx.beginPath();
        ctx.rect(x0, y0, w, h);
        ctx.clip();

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

                // Draw subtle background for each symbol's chart group (StockCharts-style)
                ctx.fillStyle = '#fafafa'; // Very light gray background for separation
                ctx.fillRect(cx, cy, cellW, cellH);

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

                // Draw prominent border around each symbol's chart group (StockCharts-style grid separation)
                ctx.strokeStyle = '#d0d0d0'; // Medium gray border for clear separation
                ctx.lineWidth = 2; // Thicker border for better visibility
                ctx.strokeRect(cx + 0.5, cy + 0.5, cellW - 1, cellH - 1);
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
        
        // CHECK SHIFT KEY FIRST - Shift+scroll = zoom (for image zoom within node)
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
            // Multi-image grid scrolling with FINITE scrolling (no wrapping)
            const cols = Math.ceil(Math.sqrt(labels.length));
            const rows = Math.ceil(labels.length / cols);
            const cellSpacing = 2; // Small uniform spacing between images
            const baseCellW = Math.floor((contentWidth - (cols - 1) * cellSpacing) / cols);
            const baseCellH = Math.floor((contentHeight - (rows - 1) * cellSpacing) / rows);
            const cellW = baseCellW * this.zoomLevel;
            const cellH = baseCellH * this.zoomLevel;
            
            // Calculate total grid dimensions (FINITE scrolling - no buffers)
            const totalGridHeight = rows * cellH + (rows - 1) * cellSpacing;
            const totalGridWidth = cols * cellW + (cols - 1) * cellSpacing;
            
            // Calculate maximum scroll offsets (FINITE scrolling)
            const maxScrollY = Math.max(0, totalGridHeight - contentHeight);
            const maxScrollX = Math.max(0, totalGridWidth - contentWidth);
            
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
            
            // FINITE scrolling with clamping (no wrapping)
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

    /**
     * Share images to social media platforms (X/Twitter, etc.)
     */
    private async shareImages(): Promise<void> {
        const labels = Object.keys(this.images || {});
        if (!labels.length) {
            alert('No images to share');
            return;
        }

        try {
            // Create a share menu
            const shareMenu = document.createElement('div');
            shareMenu.style.cssText = `
                position: fixed;
                top: 50%;
                left: 50%;
                transform: translate(-50%, -50%);
                background: #1c2128;
                border: 1px solid #373e47;
                border-radius: 8px;
                padding: 16px;
                z-index: 10000;
                box-shadow: 0 4px 20px rgba(0, 0, 0, 0.5);
                min-width: 300px;
            `;

            const title = document.createElement('div');
            title.textContent = 'Share Images';
            title.style.cssText = 'color: #c9d1d9; font-size: 16px; font-weight: bold; margin-bottom: 12px;';
            shareMenu.appendChild(title);

            // Function to create share button
            const createShareButton = (platform: string, icon: string, action: () => void) => {
                const button = document.createElement('button');
                button.textContent = `${icon} Share to ${platform}`;
                button.style.cssText = `
                    width: 100%;
                    padding: 10px;
                    margin: 4px 0;
                    background: #21262d;
                    border: 1px solid #373e47;
                    border-radius: 4px;
                    color: #c9d1d9;
                    cursor: pointer;
                    font-size: 14px;
                    text-align: left;
                `;
                button.onmouseover = () => {
                    button.style.background = '#2d333b';
                };
                button.onmouseout = () => {
                    button.style.background = '#21262d';
                };
                button.onclick = () => {
                    action();
                    document.body.removeChild(shareMenu);
                };
                return button;
            };

            // Export images as data URLs (they're already base64 encoded)
            const exportImage = async (label: string): Promise<Blob> => {
                try {
                    const dataUrl = this.images[label];
                    if (!dataUrl) {
                        throw new Error(`No image data for ${label}`);
                    }
                    // Convert data URL to blob
                    const response = await fetch(dataUrl);
                    if (!response.ok) {
                        throw new Error(`Failed to fetch image: ${response.statusText}`);
                    }
                    const blob = await response.blob();
                    if (!blob || blob.size === 0) {
                        throw new Error('Image blob is empty');
                    }
                    return blob;
                } catch (error: any) {
                    console.error('Error exporting image:', error);
                    throw new Error(`Failed to export image: ${error?.message || 'Unknown error'}`);
                }
            };

            // Share to X/Twitter
            const shareToTwitter = async () => {
                try {
                    // For multiple images, share the first one
                    const label = labels[0];
                    
                    // Format symbol with $ prefix and remove USD suffix for crypto
                    // Examples: IRENUSD -> $IREN, IREN -> $IREN, $IREN -> $IREN
                    let formattedSymbol = label;
                    if (label.includes('USD')) {
                        formattedSymbol = `$${label.replace('USD', '')}`;
                    } else if (!label.startsWith('$')) {
                        formattedSymbol = `$${label}`;
                    }
                    
                    // Tweet text is just the symbol
                    const text = encodeURIComponent(formattedSymbol);
                    const url = `https://twitter.com/intent/tweet?text=${text}`;
                    
                    // Try to copy image to clipboard (don't fail if this doesn't work)
                    let clipboardSuccess = false;
                    try {
                        const blob = await exportImage(label);
                        if (typeof ClipboardItem !== 'undefined' && navigator.clipboard && navigator.clipboard.write) {
                            const item = new ClipboardItem({ 'image/png': blob });
                            await navigator.clipboard.write([item]);
                            clipboardSuccess = true;
                        }
                    } catch (clipboardError: any) {
                        console.log('Clipboard copy failed (this is OK):', clipboardError?.message || clipboardError);
                        clipboardSuccess = false;
                    }
                    
                    // Open Twitter (this should always work)
                    const twitterWindow = window.open(url, '_blank', 'width=550,height=420');
                    
                    if (!twitterWindow) {
                        alert('Popup blocked. Please allow popups for this site and try again.');
                        return;
                    }
                    
                    // Show helpful message based on clipboard success
                    setTimeout(() => {
                        if (clipboardSuccess) {
                            // Create a more helpful notification
                            const notification = document.createElement('div');
                            notification.style.cssText = `
                                position: fixed;
                                top: 20px;
                                right: 20px;
                                background: #1c2128;
                                border: 2px solid #4caf50;
                                border-radius: 8px;
                                padding: 16px;
                                color: #c9d1d9;
                                z-index: 10001;
                                box-shadow: 0 4px 20px rgba(0, 0, 0, 0.5);
                                max-width: 350px;
                                font-size: 14px;
                            `;
                            notification.innerHTML = `
                                <div style="font-weight: bold; margin-bottom: 8px; color: #4caf50;">✓ Image Copied!</div>
                                <div style="margin-bottom: 8px;">The chart image is in your clipboard.</div>
                                <div style="margin-bottom: 8px;"><strong>Next step:</strong> Click in the Twitter compose box and press <kbd style="background: #21262d; padding: 2px 6px; border-radius: 3px;">Ctrl+V</kbd> (or <kbd style="background: #21262d; padding: 2px 6px; border-radius: 3px;">Cmd+V</kbd> on Mac) to paste the image.</div>
                                <button onclick="this.parentElement.remove()" style="width: 100%; margin-top: 8px; padding: 6px; background: #21262d; border: 1px solid #373e47; border-radius: 4px; color: #c9d1d9; cursor: pointer;">Got it</button>
                            `;
                            document.body.appendChild(notification);
                            
                            // Auto-remove after 10 seconds
                            setTimeout(() => {
                                if (notification.parentElement) {
                                    notification.remove();
                                }
                            }, 10000);
                        } else {
                            alert('Twitter opened! To add the image, use the Download button first, then upload it to Twitter.');
                        }
                    }, 500);
                    
                } catch (error: any) {
                    console.error('Error sharing to Twitter:', error);
                    const errorMsg = error?.message || 'Unknown error';
                    
                    // Still try to open Twitter even if there was an error
                    try {
                        const label = labels[0];
                        let formattedSymbol = label || '';
                        if (label?.includes('USD')) {
                            formattedSymbol = `$${label.replace('USD', '')}`;
                        } else if (label && !label.startsWith('$')) {
                            formattedSymbol = `$${label}`;
                        }
                        const text = encodeURIComponent(formattedSymbol);
                        const url = `https://twitter.com/intent/tweet?text=${text}`;
                        window.open(url, '_blank', 'width=550,height=420');
                        alert(`Twitter opened! Error: ${errorMsg}\n\nUse the Download button to get the image, then upload it manually.`);
                    } catch (fallbackError) {
                        alert(`Failed to open Twitter: ${errorMsg}\n\nPlease use the Download button to save the image, then share it manually.`);
                    }
                }
            };

            // Share using Web Share API (if available)
            const shareNative = async () => {
                try {
                    if (!navigator.share) {
                        alert('Web Share API not supported in this browser');
                        return;
                    }

                    // For native share, we'll share the first image
                    const label = labels[0];
                    const blob = await exportImage(label);
                    
                    // Format symbol with $ prefix and remove USD suffix for crypto
                    let formattedSymbol = label;
                    if (label.includes('USD')) {
                        formattedSymbol = `$${label.replace('USD', '')}`;
                    } else if (!label.startsWith('$')) {
                        formattedSymbol = `$${label}`;
                    }
                    
                    const file = new File([blob], `${label}.png`, { type: 'image/png' });
                    
                    const shareData: any = {
                        title: formattedSymbol,
                        text: formattedSymbol,
                    };
                    
                    // Try to include file if supported
                    if (navigator.canShare && navigator.canShare({ files: [file] })) {
                        shareData.files = [file];
                    }

                    await navigator.share(shareData);
                } catch (error: any) {
                    if (error.name !== 'AbortError') {
                        console.error('Error sharing:', error);
                        alert('Failed to share');
                    }
                }
            };

            // Download images
            const downloadImages = async () => {
                try {
                    for (const label of labels) {
                        const blob = await exportImage(label);
                        const url = URL.createObjectURL(blob);
                        const a = document.createElement('a');
                        a.href = url;
                        a.download = `${label}.png`;
                        document.body.appendChild(a);
                        a.click();
                        document.body.removeChild(a);
                        URL.revokeObjectURL(url);
                    }
                } catch (error) {
                    console.error('Error downloading images:', error);
                    alert('Failed to download images');
                }
            };

            // Copy image to clipboard
            const copyToClipboard = async () => {
                try {
                    if (labels.length > 1) {
                        alert('Copy to clipboard works best with a single image');
                        return;
                    }
                    const label = labels[0];
                    const blob = await exportImage(label);
                    const item = new ClipboardItem({ 'image/png': blob });
                    await navigator.clipboard.write([item]);
                    alert('Image copied to clipboard!');
                } catch (error) {
                    console.error('Error copying to clipboard:', error);
                    alert('Failed to copy to clipboard. Your browser may not support this feature.');
                }
            };

            // Add share buttons
            if (navigator.share) {
                shareMenu.appendChild(createShareButton('Native Share', '📱', shareNative));
            }
            shareMenu.appendChild(createShareButton('X (Twitter)', '🐦', shareToTwitter));
            shareMenu.appendChild(createShareButton('Download', '💾', downloadImages));
            shareMenu.appendChild(createShareButton('Copy to Clipboard', '📋', copyToClipboard));

            // Close button
            const closeButton = document.createElement('button');
            closeButton.textContent = 'Cancel';
            closeButton.style.cssText = `
                width: 100%;
                padding: 8px;
                margin-top: 8px;
                background: #30363d;
                border: 1px solid #373e47;
                border-radius: 4px;
                color: #c9d1d9;
                cursor: pointer;
                font-size: 14px;
            `;
            closeButton.onclick = () => {
                document.body.removeChild(shareMenu);
            };
            shareMenu.appendChild(closeButton);

            // Add overlay
            const overlay = document.createElement('div');
            overlay.style.cssText = `
                position: fixed;
                top: 0;
                left: 0;
                width: 100%;
                height: 100%;
                background: rgba(0, 0, 0, 0.5);
                z-index: 9999;
            `;
            overlay.onclick = () => {
                document.body.removeChild(overlay);
                document.body.removeChild(shareMenu);
            };

            document.body.appendChild(overlay);
            document.body.appendChild(shareMenu);
        } catch (error) {
            console.error('Error in shareImages:', error);
            alert('Failed to open share menu');
        }
    }
}