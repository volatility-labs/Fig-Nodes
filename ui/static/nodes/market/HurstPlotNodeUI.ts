import BaseCustomNode from '../base/BaseCustomNode';
import { LiteGraph } from '@comfyorg/litegraph';
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
        // Expect { images: { label: dataUrl } }
        const imgs = (result && result.images) || {};
        this.images = imgs;
        this.loadedImages.clear();
        this.imageAspectRatios.clear();
        // Reset scroll offsets when new images are loaded
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
        const minHeight = 300;
        const maxWidth = 800;

        if (labels.length === 1) {
            // Single image: set fixed visible area, allow scrolling if image is larger
            const label = labels[0];
            if (!label) return;
            const img = this.loadedImages.get(label);
            if (!img) return;

            // Set visible area size (fixed)
            const visibleWidth = Math.max(minWidth, Math.min(maxWidth, 500));
            const visibleHeight = Math.max(minHeight, 600); // Max height for scrolling
            
            this.maxVisibleWidth = visibleWidth;
            this.maxVisibleHeight = visibleHeight;
            
            this.size[0] = visibleWidth + padding * 2;
            this.size[1] = headerHeight + padding * 2 + visibleHeight;
        } else {
            // Multiple images: use grid layout
            const cols = Math.ceil(Math.sqrt(labels.length));
            const rows = Math.ceil(labels.length / cols);
            
            const aspectRatios = Array.from(this.imageAspectRatios.values());
            const avgAspectRatio = aspectRatios.reduce((sum, ar) => sum + ar, 0) / aspectRatios.length;
            
            const cellSpacing = 4;
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
            width = maxWidth;
            height = maxWidth / imgAspectRatio;
        } else {
            height = maxHeight;
            width = maxHeight * imgAspectRatio;
        }

        const x = (maxWidth - width) / 2;
        const y = (maxHeight - height) / 2;

        return { width, height, x, y };
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
        
        // Update max visible dimensions
        this.maxVisibleWidth = w;
        this.maxVisibleHeight = h;

        // Draw separator line between widgets and content
        if (widgetHeight > 0) {
            ctx.strokeStyle = 'rgba(75, 85, 99, 0.2)';
            ctx.lineWidth = 1;
            ctx.beginPath();
            ctx.moveTo(x0, LiteGraph.NODE_TITLE_HEIGHT + widgetHeight + widgetSpacing / 2);
            ctx.lineTo(x0 + w, LiteGraph.NODE_TITLE_HEIGHT + widgetHeight + widgetSpacing / 2);
            ctx.stroke();
        }

        // Clip to node bounds
        ctx.save();
        ctx.beginPath();
        ctx.rect(x0, y0, w, h);
        ctx.clip();

        // Background
        ctx.fillStyle = '#0f1419';
        ctx.fillRect(x0, y0, w, h);
        
        // Border
        ctx.strokeStyle = 'rgba(75, 85, 99, 0.2)';
        ctx.lineWidth = 1;
        ctx.strokeRect(x0 + 0.5, y0 + 0.5, w - 1, h - 1);

        if (!labels.length) {
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

        // Single image: full space with aspect ratio preservation and scrolling
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
                const centerX = x0 + w / 2;
                const centerY = y0 + h / 2;
                
                ctx.fillStyle = 'rgba(156, 163, 175, 0.5)';
                ctx.font = '12px Arial';
                ctx.textAlign = 'center';
                ctx.textBaseline = 'middle';
                ctx.fillText('Loading...', centerX, centerY);
            }
            ctx.restore();
            
            // Draw scrollbars outside clipped area so they're always visible
            if (img) {
                const baseImageArea = this.fitImageToBounds(img.width, img.height, w, h);
                const zoomedWidth = baseImageArea.width * this.zoomLevel;
                const zoomedHeight = baseImageArea.height * this.zoomLevel;
                const contentWidth = zoomedWidth;
                const contentHeight = zoomedHeight;
                const maxScrollX = Math.max(0, contentWidth - w);
                const maxScrollY = Math.max(0, contentHeight - h);
                
                if (maxScrollX > 0) {
                    this.drawHorizontalScrollbar(ctx, x0, y0 + h, w, h, contentWidth, w);
                }
                if (maxScrollY > 0) {
                    this.drawVerticalScrollbar(ctx, x0 + w, y0, w, h, contentHeight, h);
                }
            }
            return;
        }

        // Grid layout for multiple images - StockCharts-style with clear separation
        // Calculate optimal grid dimensions for true symmetry
        const cols = Math.ceil(Math.sqrt(labels.length));
        const rows = Math.ceil(labels.length / cols);
        const cellSpacing = 12; // Increased spacing for better visual separation between symbols
        
        // Calculate cell dimensions ensuring true symmetry - all cells same size
        // Use floor to ensure integer pixel values for clean borders
        const totalSpacingW = (cols - 1) * cellSpacing;
        const totalSpacingH = (rows - 1) * cellSpacing;
        let cellW = Math.floor((w - totalSpacingW) / cols);
        let cellH = Math.floor((h - totalSpacingH) / rows);
        
        // Ensure minimum cell size for readability
        const minCellW = 200;
        const minCellH = 150;
        if (cellW < minCellW) {
            cellW = minCellW;
        }
        if (cellH < minCellH) {
            cellH = minCellH;
        }

        // Calculate total grid dimensions (same logic as onMouseWheel)
        const totalGridHeight = rows * cellH + (rows - 1) * cellSpacing;
        const scrollBuffer = Math.max(50, totalGridHeight * 0.1); // At least 50px or 10% of grid height
        const scrollableHeight = totalGridHeight + scrollBuffer;
        
        const totalGridWidth = cols * cellW + (cols - 1) * cellSpacing;
        const scrollBufferX = Math.max(50, totalGridWidth * 0.1); // At least 50px or 10% of grid width
        const scrollableWidth = totalGridWidth + scrollBufferX;
        
        // Wrap scroll offsets for infinite scrolling (handles negative and overflow values)
        if (scrollableHeight > 0) {
            this.gridScrollOffset = ((this.gridScrollOffset % scrollableHeight) + scrollableHeight) % scrollableHeight;
        }
        if (scrollableWidth > 0) {
            this.gridScrollOffsetX = ((this.gridScrollOffsetX % scrollableWidth) + scrollableWidth) % scrollableWidth;
        }

        // Save the current context state before drawing grid
        ctx.save();
        
        // Set up clipping region for the content area only
        ctx.beginPath();
        ctx.rect(x0, y0, w, h);
        ctx.clip();

        // Draw grid with infinite scrolling support - draw multiple copies for seamless wrapping
        // Calculate how many copies we need to fill the visible area (both directions)
        const copiesNeededY = Math.ceil(h / scrollableHeight) + 2; // +2 for safety margin
        const copiesNeededX = Math.ceil(w / scrollableWidth) + 2; // +2 for safety margin
        
        // Draw grid copies in both directions for infinite scrolling
        for (let copyY = -1; copyY <= copiesNeededY; copyY++) {
            const copyOffsetY = copyY * scrollableHeight;
            const baseY = y0 - this.gridScrollOffset + copyOffsetY;
            
            for (let copyX = -1; copyX <= copiesNeededX; copyX++) {
                const copyOffsetX = copyX * scrollableWidth;
                const baseX = x0 - this.gridScrollOffsetX + copyOffsetX;
                
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
            }
        }
        
        // Restore context state to remove clipping (restores the grid save)
        ctx.restore();
        
        // Draw scrollbars for grid (always show for multi-image grids with infinite scrolling)
        if (labels.length > 1) {
            if (scrollableHeight > 0) {
                this.drawGridScrollbar(ctx, x0 + w, y0, h, scrollableHeight, h);
            }
            if (scrollableWidth > 0) {
                this.drawGridHorizontalScrollbar(ctx, x0, y0 + h, scrollableWidth, w);
            }
        }
        
        // Restore the initial clipping save
        ctx.restore();
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

    private drawGridScrollbar(ctx: CanvasRenderingContext2D, scrollbarX: number, startY: number, visibleHeight: number, totalHeight: number, viewportHeight: number) {
        const scrollbarWidth = 8;
        const scrollbarHeight = viewportHeight;
        
        // Scrollbar track
        ctx.fillStyle = 'rgba(100, 100, 100, 0.3)';
        ctx.fillRect(scrollbarX, startY, scrollbarWidth, scrollbarHeight);

        // Scrollbar thumb
        const maxScroll = Math.max(0, totalHeight - viewportHeight);
        if (maxScroll <= 0) return;
        
        const thumbHeight = Math.max(20, (viewportHeight / totalHeight) * scrollbarHeight);
        const scrollRatio = maxScroll > 0 ? this.gridScrollOffset / maxScroll : 0;
        const thumbY = startY + scrollRatio * (scrollbarHeight - thumbHeight);
        
        ctx.fillStyle = 'rgba(150, 150, 150, 0.7)';
        ctx.fillRect(scrollbarX, thumbY, scrollbarWidth, thumbHeight);
    }

    private drawGridHorizontalScrollbar(ctx: CanvasRenderingContext2D, startX: number, scrollbarY: number, totalWidth: number, viewportWidth: number) {
        const scrollbarHeight = 8;
        const scrollbarWidth = viewportWidth;
        
        // Scrollbar track
        ctx.fillStyle = 'rgba(100, 100, 100, 0.3)';
        ctx.fillRect(startX, scrollbarY, scrollbarWidth, scrollbarHeight);

        // Scrollbar thumb
        const maxScroll = Math.max(0, totalWidth - viewportWidth);
        if (maxScroll <= 0) return;
        
        const thumbWidth = Math.max(20, (viewportWidth / totalWidth) * scrollbarWidth);
        const scrollRatio = maxScroll > 0 ? this.gridScrollOffsetX / maxScroll : 0;
        const thumbX = startX + scrollRatio * (scrollbarWidth - thumbWidth);
        
        ctx.fillStyle = 'rgba(150, 150, 150, 0.7)';
        ctx.fillRect(thumbX, scrollbarY, thumbWidth, scrollbarHeight);
    }

    // Handle mouse wheel events for scrolling (works with both mouse and trackpad)
    onMouseWheel(event: WheelEvent, pos: [number, number], _canvas: any): boolean {
        console.log('[HurstPlot] onMouseWheel called', { deltaY: event.deltaY, deltaMode: event.deltaMode, pos });
        
        // CHECK SHIFT KEY IMMEDIATELY - BEFORE ANY OTHER LOGIC
        const shiftPressed = event.shiftKey || (event.getModifierState && event.getModifierState('Shift'));
        console.log('🔍🔍🔍 [HurstPlot] SHIFT CHECK AT START', { 
            shiftKey: event.shiftKey, 
            getModifierState: event.getModifierState ? event.getModifierState('Shift') : 'N/A',
            shiftPressed,
            eventType: event.type,
            allModifiers: { shift: event.shiftKey, alt: event.altKey, ctrl: event.ctrlKey, meta: event.metaKey }
        });
        
        const nodeWithFlags = this as { flags?: { collapsed?: boolean }; size: [number, number] };
        
        if (nodeWithFlags.flags?.collapsed || !this.images || Object.keys(this.images).length === 0) {
            console.log('[HurstPlot] Early return: collapsed or no images');
            return false;
        }

        const padding = 12;
        const widgetSpacing = 8;
        const widgetHeight = this.widgets ? this.widgets.length * LiteGraph.NODE_WIDGET_HEIGHT : 0;
        const startY = LiteGraph.NODE_TITLE_HEIGHT + widgetHeight + widgetSpacing + padding;
        const contentWidth = Math.max(0, nodeWithFlags.size[0] - padding * 2);
        const contentHeight = Math.max(0, nodeWithFlags.size[1] - LiteGraph.NODE_TITLE_HEIGHT - widgetHeight - widgetSpacing - padding * 2);

        // Check if Shift is held FIRST - before bounds check, so zoom works even if mouse is slightly outside
        // Use getModifierState for better Mac trackpad compatibility
        console.log('🔍 [HurstPlot] SHIFT KEY CHECK (BEFORE BOUNDS)', { 
            shiftPressed,
            pos,
            size: nodeWithFlags.size,
            startY
        });
        
        if (shiftPressed) {
            // Zoom mode: use scroll delta to adjust zoom level
            // Only zoom if mouse is roughly within node bounds (more lenient check)
            const isRoughlyInBounds = pos[0] >= -50 && pos[0] <= nodeWithFlags.size[0] + 50 && 
                                     pos[1] >= startY - 50 && pos[1] <= nodeWithFlags.size[1] + 50;
            
            if (isRoughlyInBounds) {
                const zoomSpeed = 0.001; // Adjust this to control zoom sensitivity
                const zoomDelta = event.deltaY * zoomSpeed;
                const oldZoom = this.zoomLevel;
                this.zoomLevel = Math.max(0.1, Math.min(5.0, this.zoomLevel - zoomDelta)); // Clamp between 10% and 500%
                
                console.log('✅ [HurstPlot] ZOOM UPDATED', { oldZoom, newZoom: this.zoomLevel, deltaY: event.deltaY });
                this.setDirtyCanvas(true, true);
                return true; // Event handled - prevent scrolling
            } else {
                console.log('[HurstPlot] Shift pressed but mouse too far outside bounds');
            }
        }

        // Check if mouse is within node bounds (for scrolling)
        if (pos[0] < 0 || pos[0] > nodeWithFlags.size[0] || pos[1] < startY || pos[1] > nodeWithFlags.size[1]) {
            console.log('[HurstPlot] Mouse out of bounds', { pos, size: nodeWithFlags.size, startY });
            return false;
        }

        const labels = Object.keys(this.images);
        console.log('[HurstPlot] Labels count:', labels.length);
        
        if (labels.length !== 1) {
            // Multi-image grid - use grid scrolling
            const cols = Math.ceil(Math.sqrt(labels.length));
            const rows = Math.ceil(labels.length / cols);
            const cellSpacing = 4;
            const cellW = Math.floor((contentWidth - (cols - 1) * cellSpacing) / cols);
            const cellH = Math.floor((contentHeight - (rows - 1) * cellSpacing) / rows);
            
            // Calculate actual total height based on image aspect ratios
            // Images preserve aspect ratio, so they might be taller than cells
            let actualTotalHeight = 0;
            let loadedImageCount = 0;
            let idx = 0;
            for (let r = 0; r < rows; r++) {
                let maxRowHeight = 0;
                for (let c = 0; c < cols; c++) {
                    if (idx >= labels.length) break;
                    const label = labels[idx++];
                    if (!label) continue;
                    const img = this.loadedImages.get(label);
                    if (img) {
                        loadedImageCount++;
                        const imageArea = this.fitImageToBounds(img.width, img.height, cellW - 2, cellH - 2);
                        maxRowHeight = Math.max(maxRowHeight, imageArea.height + 2); // +2 for padding
                    } else {
                        maxRowHeight = Math.max(maxRowHeight, cellH);
                    }
                }
                actualTotalHeight += maxRowHeight;
                if (r < rows - 1) actualTotalHeight += cellSpacing;
            }
            
            // Use the larger of cell-based height or actual image height
            const cellBasedHeight = rows * cellH + (rows - 1) * cellSpacing;
            const totalGridHeight = Math.max(cellBasedHeight, actualTotalHeight);
            
            // Always allow scrolling for multi-image grids - users may want to scroll even if grid "fits"
            // Add a buffer to ensure scrolling is always available for navigation
            const scrollBuffer = Math.max(50, totalGridHeight * 0.1); // At least 50px or 10% of grid height
            const scrollableHeight = totalGridHeight + scrollBuffer;
            
            const totalGridWidth = cols * cellW + (cols - 1) * cellSpacing;
            const scrollBufferX = Math.max(50, totalGridWidth * 0.1); // At least 50px or 10% of grid width
            const scrollableWidth = totalGridWidth + scrollBufferX;
            
            // Always enable scrolling for grids with multiple images (even if they appear to "fit")
            // This allows users to navigate through images smoothly
            if (scrollableHeight <= 0 && labels.length <= 1) {
                return false; // Only disable scrolling for single images that fit
            }
            
            // Determine scroll direction: horizontal delta for horizontal scrolling
            // NOTE: Don't use Shift key here - it's reserved for zoom when node is selected
            const isHorizontal = !event.shiftKey && Math.abs(event.deltaX) > Math.abs(event.deltaY);
            
            // Handle grid scrolling (both vertical and horizontal) with infinite scrolling
            let scrollAmount: number;
            if (event.deltaMode === 0) {
                // Pixel mode (trackpad)
                scrollAmount = isHorizontal ? event.deltaX * 0.8 : event.deltaY * 0.8;
            } else if (event.deltaMode === 1) {
                // Line mode (mouse wheel)
                scrollAmount = isHorizontal ? event.deltaX * 20 : event.deltaY * 20;
            } else {
                // Page mode
                scrollAmount = isHorizontal ? event.deltaX * contentWidth : event.deltaY * contentHeight;
            }
            
            // Infinite scrolling: allow any scroll offset, wrap using modulo
            if (isHorizontal) {
                const oldOffsetX = this.gridScrollOffsetX;
                this.gridScrollOffsetX = this.gridScrollOffsetX + scrollAmount;
                
                // Wrap the horizontal scroll offset
                if (scrollableWidth > 0) {
                    const normalized = ((this.gridScrollOffsetX % scrollableWidth) + scrollableWidth) % scrollableWidth;
                    this.gridScrollOffsetX = normalized;
                }
                
                console.log('[HurstPlot] Grid scroll updated (horizontal infinite)', { oldOffsetX, newOffsetX: this.gridScrollOffsetX, scrollAmount, scrollableWidth });
            } else {
                const oldOffset = this.gridScrollOffset;
                this.gridScrollOffset = this.gridScrollOffset + scrollAmount;
                
                // Wrap the vertical scroll offset
                if (scrollableHeight > 0) {
                    const normalized = ((this.gridScrollOffset % scrollableHeight) + scrollableHeight) % scrollableHeight;
                    this.gridScrollOffset = normalized;
                }
                
                console.log('[HurstPlot] Grid scroll updated (vertical infinite)', { oldOffset, newOffset: this.gridScrollOffset, scrollAmount, scrollableHeight });
            }
            this.setDirtyCanvas(true, true);
            return true; // Event handled
        }

        const label = labels[0];
        if (!label) {
            console.log('[HurstPlot] No label');
            return false;
        }
        const img = this.loadedImages.get(label);
        if (!img) {
            console.log('[HurstPlot] Image not loaded yet');
            return false;
        }

        // Calculate image display dimensions
        const imageArea = this.fitImageToBounds(img.width, img.height, contentWidth, contentHeight);
        const maxScrollX = Math.max(0, imageArea.width - contentWidth);
        const maxScrollY = Math.max(0, imageArea.height - contentHeight);

        console.log('[HurstPlot] Single image scroll check', { 
            imageSize: { w: img.width, h: img.height },
            imageArea: { w: imageArea.width, h: imageArea.height },
            contentSize: { w: contentWidth, h: contentHeight },
            maxScrollX, maxScrollY
        });

        if (maxScrollX <= 0 && maxScrollY <= 0) {
            console.log('[HurstPlot] No scrolling needed - image fits');
            return false; // No scrolling needed
        }

        // Handle different delta modes (pixel, line, page) - same as logging node
        // Trackpads typically use deltaMode = 0 (pixels), mouse wheels use deltaMode = 1 (lines)
        let scrollAmount: number;
        
        // Determine scroll direction: horizontal delta for horizontal scrolling
        // NOTE: Don't use Shift key here - it's reserved for zoom when node is selected
        const isHorizontal = !event.shiftKey && Math.abs(event.deltaX) > Math.abs(event.deltaY);
        
        if (event.deltaMode === 0) {
            // Pixel mode (trackpad) - use delta directly with slight scaling (same as logging node)
            scrollAmount = isHorizontal ? event.deltaX * 0.8 : event.deltaY * 0.8;
        } else if (event.deltaMode === 1) {
            // Line mode (mouse wheel) - convert to pixels
            scrollAmount = isHorizontal ? event.deltaX * 20 : event.deltaY * 20;
        } else {
            // Page mode - scroll by page size
            scrollAmount = isHorizontal ? event.deltaX * contentWidth : event.deltaY * contentHeight;
        }

        if (isHorizontal && maxScrollX > 0) {
            const oldX = this.scrollOffsetX;
            this.scrollOffsetX = Math.max(0, Math.min(maxScrollX, this.scrollOffsetX + scrollAmount));
            console.log('[HurstPlot] Horizontal scroll', { oldX, newX: this.scrollOffsetX, scrollAmount, maxScrollX });
        } else if (!isHorizontal && maxScrollY > 0) {
            const oldY = this.scrollOffsetY;
            this.scrollOffsetY = Math.max(0, Math.min(maxScrollY, this.scrollOffsetY + scrollAmount));
            console.log('[HurstPlot] Vertical scroll', { oldY, newY: this.scrollOffsetY, scrollAmount, maxScrollY });
        } else {
            console.log('[HurstPlot] Scroll attempted but no valid direction', { isHorizontal, maxScrollX, maxScrollY });
        }

        this.setDirtyCanvas(true, true);
        return true; // Event handled
    }

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

