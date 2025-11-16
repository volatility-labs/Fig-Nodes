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

    constructor(title: string, data: any, serviceRegistry: any) {
        super(title, data, serviceRegistry);
        this.size = [500, 360];
        this.displayResults = false; // custom canvas rendering
        this.renderer = new OHLCVPlotRenderer(this);
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
        const cellSpacing = 4;
        const cellW = Math.floor((w - (cols - 1) * cellSpacing) / cols);
        const cellH = Math.floor((h - (rows - 1) * cellSpacing) / rows);

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

                // Image - fit preserving aspect ratio
                if (img) {
                    const imageArea = this.fitImageToBounds(img.width, img.height, cellW - 2, cellH - 2);
                    ctx.drawImage(
                        img,
                        cx + 1 + imageArea.x,
                        cy + 1 + imageArea.y,
                        imageArea.width,
                        imageArea.height
                    );
                }

                // Very subtle border
                ctx.strokeStyle = 'rgba(75, 85, 99, 0.18)';
                ctx.lineWidth = 1;
                ctx.strokeRect(cx + 0.5, cy + 0.5, cellW - 1, cellH - 1);
            }
        }
        
        ctx.restore();
    }
}


