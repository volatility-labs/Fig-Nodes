import BaseCustomNode from '../base/BaseCustomNode';
import { LiteGraph, LGraphNode } from '@fig-node/litegraph';
import { NodeRenderer } from '../utils/NodeRenderer';

class ImageDisplayRenderer extends NodeRenderer {
    onDrawForeground(ctx: CanvasRenderingContext2D) {
        const node = this.node as unknown as ImageDisplayNodeUI;
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
    private gridScrollOffset: number = 0;
    private gridScrollOffsetX: number = 0;
    private zoomLevel: number = 1.0;

    constructor(title: string, data: any, serviceRegistry: any) {
        super(title, data, serviceRegistry);
        this.size = [500, 360];
        this.displayResults = false;
        this.renderer = new ImageDisplayRenderer(this as unknown as LGraphNode & {
            displayResults: boolean;
            result: unknown;
            displayText: string;
            error: string;
            highlightStartTs: number | null;
            isExecuting: boolean;
            readonly highlightDurationMs: number;
            readonly pulseCycleMs: number;
            progress: number;
            progressText: string;
            properties: { [key: string]: unknown };
        });
    }

    onMouseDown(_event: any, _pos: [number, number], _canvas: any): boolean {
        return false;
    }

    updateDisplay(result: any) {
        const imgs = (result && result.images) || {};
        this.images = imgs;
        this.loadedImages.clear();
        this.imageAspectRatios.clear();
        this.scrollOffsetX = 0;
        this.scrollOffsetY = 0;
        this.gridScrollOffset = 0;
        this.gridScrollOffsetX = 0;
        this.zoomLevel = 1.0;

        let allLoaded = 0;
        const totalImages = Object.keys(imgs).length;

        Object.entries(imgs).forEach(([label, dataUrl]) => {
            const img = new Image();
            img.onload = () => {
                this.loadedImages.set(label, img);
                this.imageAspectRatios.set(label, img.width / img.height);
                allLoaded++;
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
            const label = labels[0];
            if (!label) return;
            const aspectRatio = this.imageAspectRatios.get(label);
            if (!aspectRatio) return;

            const contentWidth = Math.max(minWidth, Math.min(maxWidth, 500));
            const contentHeight = contentWidth / aspectRatio;
            const totalHeight = headerHeight + padding * 2 + contentHeight;

            this.size[0] = contentWidth + padding * 2;
            this.size[1] = Math.max(minHeight + headerHeight, totalHeight);
        } else {
            const cols = Math.ceil(Math.sqrt(labels.length));
            const rows = Math.ceil(labels.length / cols);
            const aspectRatios = Array.from(this.imageAspectRatios.values());
            const avgAspectRatio = aspectRatios.reduce((sum, ar) => sum + ar, 0) / aspectRatios.length;
            const cellSpacing = 2;
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

        if (widgetHeight > 0) {
            ctx.strokeStyle = 'rgba(75, 85, 99, 0.2)';
            ctx.lineWidth = 1;
            ctx.beginPath();
            ctx.moveTo(x0, LiteGraph.NODE_TITLE_HEIGHT + widgetHeight + widgetSpacing / 2);
            ctx.lineTo(x0 + w, LiteGraph.NODE_TITLE_HEIGHT + widgetHeight + widgetSpacing / 2);
            ctx.stroke();
        }

        ctx.save();
        ctx.beginPath();
        ctx.rect(x0, y0, w, h);
        ctx.clip();

        ctx.fillStyle = LiteGraph.WIDGET_BGCOLOR || '#0f1419';
        ctx.fillRect(x0, y0, w, h);

        if (!labels.length) {
            const centerX = x0 + w / 2;
            const centerY = y0 + h / 2;
            ctx.fillStyle = LiteGraph.WIDGET_SECONDARY_TEXT_COLOR || 'rgba(156, 163, 175, 0.4)';
            ctx.font = '12px Arial';
            ctx.textAlign = 'center';
            ctx.textBaseline = 'middle';
            ctx.fillText('No images to display', centerX, centerY);
            ctx.restore();
            return;
        }

        if (labels.length === 1) {
            const label = labels[0];
            if (!label) {
                ctx.restore();
                return;
            }
            const img = this.loadedImages.get(label);
            if (img) {
                const baseImageArea = this.fitImageToBounds(img.width, img.height, w, h);
                const zoomedWidth = baseImageArea.width * this.zoomLevel;
                const zoomedHeight = baseImageArea.height * this.zoomLevel;
                const centerX = x0 + w / 2;
                const centerY = y0 + h / 2;
                const drawX = centerX - zoomedWidth / 2;
                const drawY = centerY - zoomedHeight / 2;
                const maxScrollX = Math.max(0, zoomedWidth - w);
                const maxScrollY = Math.max(0, zoomedHeight - h);

                this.scrollOffsetX = Math.max(0, Math.min(maxScrollX, this.scrollOffsetX));
                this.scrollOffsetY = Math.max(0, Math.min(maxScrollY, this.scrollOffsetY));

                ctx.drawImage(img, drawX - this.scrollOffsetX, drawY - this.scrollOffsetY, zoomedWidth, zoomedHeight);
            } else {
                const centerX = x0 + w / 2;
                const centerY = y0 + h / 2;
                ctx.fillStyle = LiteGraph.WIDGET_SECONDARY_TEXT_COLOR || 'rgba(156, 163, 175, 0.5)';
                ctx.font = '12px Arial';
                ctx.textAlign = 'center';
                ctx.textBaseline = 'middle';
                ctx.fillText('Loading...', centerX, centerY);
            }
            ctx.restore();
            return;
        }

        const cols = Math.ceil(Math.sqrt(labels.length));
        const rows = Math.ceil(labels.length / cols);
        const cellSpacing = 2;
        const baseCellW = Math.floor((w - (cols - 1) * cellSpacing) / cols);
        const baseCellH = Math.floor((h - (rows - 1) * cellSpacing) / rows);
        
        // Calculate cell sizes maintaining aspect ratios for each image
        const cellSizes: Array<{ width: number; height: number }> = [];
        let maxCellW = 0;
        let maxCellH = 0;
        
        for (let idx = 0; idx < labels.length; idx++) {
            const label = labels[idx];
            if (!label) continue;
            const img = this.loadedImages.get(label);
            if (!img) continue;
            
            const fitted = this.fitImageToBounds(img.width, img.height, baseCellW, baseCellH);
            const zoomedW = fitted.width * this.zoomLevel;
            const zoomedH = fitted.height * this.zoomLevel;
            
            cellSizes.push({ width: zoomedW, height: zoomedH });
            maxCellW = Math.max(maxCellW, zoomedW);
            maxCellH = Math.max(maxCellH, zoomedH);
        }
        
        const totalGridHeight = rows * maxCellH + (rows - 1) * cellSpacing;
        const totalGridWidth = cols * maxCellW + (cols - 1) * cellSpacing;
        
        // Only enable infinite scrolling if content exceeds viewport
        const needsVerticalScroll = totalGridHeight > h;
        const needsHorizontalScroll = totalGridWidth > w;
        
        const scrollBuffer = needsVerticalScroll ? Math.max(50, totalGridHeight * 0.1) : 0;
        const scrollableHeight = needsVerticalScroll ? totalGridHeight + scrollBuffer : totalGridHeight;
        const scrollBufferX = needsHorizontalScroll ? Math.max(50, totalGridWidth * 0.1) : 0;
        const scrollableWidth = needsHorizontalScroll ? totalGridWidth + scrollBufferX : totalGridWidth;

        // Only apply scroll offset modulo if infinite scrolling is enabled
        if (needsVerticalScroll && scrollableHeight > 0) {
            this.gridScrollOffset = ((this.gridScrollOffset % scrollableHeight) + scrollableHeight) % scrollableHeight;
        } else {
            // Reset scroll offset if content fits
            this.gridScrollOffset = 0;
        }
        
        if (needsHorizontalScroll && scrollableWidth > 0) {
            this.gridScrollOffsetX = ((this.gridScrollOffsetX % scrollableWidth) + scrollableWidth) % scrollableWidth;
        } else {
            // Reset scroll offset if content fits
            this.gridScrollOffsetX = 0;
        }

        ctx.save();
        ctx.beginPath();
        ctx.rect(x0, y0, w, h);
        ctx.clip();

        // Only create copies if infinite scrolling is needed
        const copiesNeededY = needsVerticalScroll ? Math.ceil(h / scrollableHeight) + 2 : 0;
        const copiesNeededX = needsHorizontalScroll ? Math.ceil(w / scrollableWidth) + 2 : 0;

        for (let copyY = needsVerticalScroll ? -1 : 0; copyY <= copiesNeededY; copyY++) {
            const copyOffsetY = copyY * scrollableHeight;
            const baseY = y0 - this.gridScrollOffset + copyOffsetY;

            for (let copyX = needsHorizontalScroll ? -1 : 0; copyX <= copiesNeededX; copyX++) {
                const copyOffsetX = copyX * scrollableWidth;
                const baseX = x0 - this.gridScrollOffsetX + copyOffsetX;

                let idx = 0;
                for (let r = 0; r < rows; r++) {
                    for (let c = 0; c < cols; c++) {
                        if (idx >= labels.length) break;
                        const label = labels[idx];
                        if (!label) {
                            idx++;
                            continue;
                        }
                        const img = this.loadedImages.get(label);
                        if (!img) {
                            idx++;
                            continue;
                        }
                        
                        const cellSize = cellSizes[idx];
                        if (!cellSize) {
                            idx++;
                            continue;
                        }
                        
                        const cellW = cellSize.width;
                        const cellH = cellSize.height;
                        const cellCenterX = baseX + c * (maxCellW + cellSpacing) + maxCellW / 2;
                        const cellCenterY = baseY + r * (maxCellH + cellSpacing) + maxCellH / 2;
                        const drawX = cellCenterX - cellW / 2;
                        const drawY = cellCenterY - cellH / 2;

                        if (drawY + cellH < y0 || drawY > y0 + h || drawX + cellW < x0 || drawX > x0 + w) {
                            idx++;
                            continue;
                        }

                        ctx.drawImage(img, drawX, drawY, cellW, cellH);
                        idx++;
                    }
                }
            }
        }

        ctx.restore();
        ctx.restore();
    }

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
        const isSelected = nodeWithFlags.selected || (canvas?.selected_nodes && canvas.selected_nodes[this.id]);
        const shiftPressed = event.shiftKey || (event.getModifierState && event.getModifierState('Shift'));

        if (shiftPressed) {
            const zoomBoundsMargin = 200;
            const isInBounds = pos[0] >= -zoomBoundsMargin && pos[0] <= nodeWithFlags.size[0] + zoomBoundsMargin &&
                pos[1] >= startY - zoomBoundsMargin && pos[1] <= nodeWithFlags.size[1] + zoomBoundsMargin;

            if (isInBounds || isSelected) {
                const zoomSpeed = event.deltaMode === 0 ? 0.03 : 0.01;
                const zoomDelta = -event.deltaY * zoomSpeed;
                this.zoomLevel = Math.max(1.0, Math.min(5.0, this.zoomLevel + zoomDelta));
                this.setDirtyCanvas(true, true);
                if (this.graph) {
                    this.graph.setDirtyCanvas(true);
                }
                requestAnimationFrame(() => {
                    this.setDirtyCanvas(true, true);
                    if (this.graph) {
                        this.graph.setDirtyCanvas(true);
                    }
                });
                return true;
            }
            return true;
        }

        const boundsMargin = 100;
        const isInScrollBounds = pos[0] >= -boundsMargin && pos[0] <= nodeWithFlags.size[0] + boundsMargin &&
            pos[1] >= startY - boundsMargin && pos[1] <= nodeWithFlags.size[1] + boundsMargin;

        if (!isInScrollBounds && !isSelected) {
            return false;
        }

        const labels = Object.keys(this.images);

        if (labels.length !== 1) {
            const cols = Math.ceil(Math.sqrt(labels.length));
            const rows = Math.ceil(labels.length / cols);
            const cellSpacing = 2;
            const baseCellW = Math.floor((contentWidth - (cols - 1) * cellSpacing) / cols);
            const baseCellH = Math.floor((contentHeight - (rows - 1) * cellSpacing) / rows);
            
            // Calculate max cell dimensions maintaining aspect ratios
            let maxCellW = 0;
            let maxCellH = 0;
            for (const label of labels) {
                if (!label) continue;
                const img = this.loadedImages.get(label);
                if (!img) continue;
                
                const aspectRatio = this.imageAspectRatios.get(label) || (img.width / img.height);
                const fitted = this.fitImageToBounds(img.width, img.height, baseCellW, baseCellH);
                const zoomedW = fitted.width * this.zoomLevel;
                const zoomedH = fitted.height * this.zoomLevel;
                
                maxCellW = Math.max(maxCellW, zoomedW);
                maxCellH = Math.max(maxCellH, zoomedH);
            }
            
            const totalGridHeight = rows * maxCellH + (rows - 1) * cellSpacing;
            const totalGridWidth = cols * maxCellW + (cols - 1) * cellSpacing;
            
            // Only enable scrolling if content exceeds viewport
            const needsVerticalScroll = totalGridHeight > contentHeight;
            const needsHorizontalScroll = totalGridWidth > contentWidth;
            
            const scrollBuffer = needsVerticalScroll ? Math.max(50, totalGridHeight * 0.1) : 0;
            const scrollableHeight = needsVerticalScroll ? totalGridHeight + scrollBuffer : totalGridHeight;
            const scrollBufferX = needsHorizontalScroll ? Math.max(50, totalGridWidth * 0.1) : 0;
            const scrollableWidth = needsHorizontalScroll ? totalGridWidth + scrollBufferX : totalGridWidth;
            
            // If content fits, disable scrolling
            if (!needsVerticalScroll && !needsHorizontalScroll) {
                return false;
            }
            const hasHorizontalDelta = Math.abs(event.deltaX) > 5;
            const hasVerticalDelta = Math.abs(event.deltaY) > 5;
            const isHorizontal = hasHorizontalDelta && Math.abs(event.deltaX) > Math.abs(event.deltaY);

            let scrollAmountX = 0;
            let scrollAmountY = 0;

            if (event.deltaMode === 0) {
                scrollAmountX = event.deltaX * 1.2;
                scrollAmountY = event.deltaY * 1.2;
            } else if (event.deltaMode === 1) {
                scrollAmountX = event.deltaX * 30;
                scrollAmountY = event.deltaY * 30;
            } else {
                scrollAmountX = event.deltaX * contentWidth * 0.1;
                scrollAmountY = event.deltaY * contentHeight * 0.1;
            }

            if (needsHorizontalScroll && scrollableWidth > 0 && (hasHorizontalDelta || isHorizontal)) {
                this.gridScrollOffsetX = ((this.gridScrollOffsetX + scrollAmountX) % scrollableWidth + scrollableWidth) % scrollableWidth;
            }

            if (needsVerticalScroll && scrollableHeight > 0 && (hasVerticalDelta || !isHorizontal)) {
                this.gridScrollOffset = ((this.gridScrollOffset + scrollAmountY) % scrollableHeight + scrollableHeight) % scrollableHeight;
            }

            this.setDirtyCanvas(true, true);
            return true;
        }

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
            return false;
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
