/**
 * Canvas Scrollbars Manager
 * Adds scrollbars to the LiteGraph canvas for finite scrolling control
 */

import { LGraphCanvas } from '@fig-node/litegraph';

export class CanvasScrollbars {
    private canvas: LGraphCanvas;
    private container: HTMLElement;
    private horizontalScrollbar: HTMLElement;
    private verticalScrollbar: HTMLElement;
    private horizontalThumb: HTMLElement;
    private verticalThumb: HTMLElement;
    private isDraggingHorizontal: boolean = false;
    private isDraggingVertical: boolean = false;
    private dragStartX: number = 0;
    private dragStartY: number = 0;
    private dragStartOffsetX: number = 0;
    private dragStartOffsetY: number = 0;
    private updateAnimationFrame: number | null = null;
    private lastBoundsUpdate: number = 0;
    private cachedBounds: { minX: number; minY: number; maxX: number; maxY: number; width: number; height: number } | null = null;
    private cachedContainerRect: DOMRect | null = null;
    private cachedScrollbarRects: { h: DOMRect, v: DOMRect } | null = null;

    constructor(canvas: LGraphCanvas, container: HTMLElement) {
        this.canvas = canvas;
        this.container = container;
        
        // Create scrollbar elements
        this.createScrollbars();
        
        // Set up event listeners
        this.setupEventListeners();
        
        // Initialize cached rects
        this.updateCachedRects();
        window.addEventListener('resize', () => this.updateCachedRects());

        // Start update loop
        this.startUpdateLoop();
    }

    private updateCachedRects(): void {
        this.cachedContainerRect = this.container.getBoundingClientRect();
        this.cachedScrollbarRects = {
            h: this.horizontalScrollbar.getBoundingClientRect(),
            v: this.verticalScrollbar.getBoundingClientRect()
        };
    }

    private createScrollbars(): void {
        // Create horizontal scrollbar container
        this.horizontalScrollbar = document.createElement('div');
        this.horizontalScrollbar.className = 'canvas-scrollbar canvas-scrollbar-horizontal';
        this.horizontalScrollbar.style.cssText = `
            position: absolute;
            bottom: 0;
            left: 0;
            right: 16px;
            height: 16px;
            background: rgba(0, 0, 0, 0.3);
            z-index: 1000;
            cursor: pointer;
        `;

        // Create horizontal thumb
        this.horizontalThumb = document.createElement('div');
        this.horizontalThumb.className = 'canvas-scrollbar-thumb canvas-scrollbar-thumb-horizontal';
        this.horizontalThumb.style.cssText = `
            position: absolute;
            top: 2px;
            left: 0;
            width: 100px;
            height: 12px;
            background: rgba(255, 255, 255, 0.5);
            border-radius: 6px;
            cursor: grab;
            transition: background 0.2s;
        `;
        this.horizontalScrollbar.appendChild(this.horizontalThumb);

        // Create vertical scrollbar container
        this.verticalScrollbar = document.createElement('div');
        this.verticalScrollbar.className = 'canvas-scrollbar canvas-scrollbar-vertical';
        this.verticalScrollbar.style.cssText = `
            position: absolute;
            top: 0;
            right: 0;
            bottom: 16px;
            width: 16px;
            background: rgba(0, 0, 0, 0.3);
            z-index: 1000;
            cursor: pointer;
        `;

        // Create vertical thumb
        this.verticalThumb = document.createElement('div');
        this.verticalThumb.className = 'canvas-scrollbar-thumb canvas-scrollbar-thumb-vertical';
        this.verticalThumb.style.cssText = `
            position: absolute;
            top: 0;
            left: 2px;
            width: 12px;
            height: 100px;
            background: rgba(255, 255, 255, 0.5);
            border-radius: 6px;
            cursor: grab;
            transition: background 0.2s;
        `;
        this.verticalScrollbar.appendChild(this.verticalThumb);

        // Add scrollbars to container
        this.container.appendChild(this.horizontalScrollbar);
        this.container.appendChild(this.verticalScrollbar);

        // Add hover effects
        this.horizontalThumb.addEventListener('mouseenter', () => {
            this.horizontalThumb.style.background = 'rgba(255, 255, 255, 0.7)';
        });
        this.horizontalThumb.addEventListener('mouseleave', () => {
            if (!this.isDraggingHorizontal) {
                this.horizontalThumb.style.background = 'rgba(255, 255, 255, 0.5)';
            }
        });
        this.verticalThumb.addEventListener('mouseenter', () => {
            this.verticalThumb.style.background = 'rgba(255, 255, 255, 0.7)';
        });
        this.verticalThumb.addEventListener('mouseleave', () => {
            if (!this.isDraggingVertical) {
                this.verticalThumb.style.background = 'rgba(255, 255, 255, 0.5)';
            }
        });
    }

    private setupEventListeners(): void {
        // Horizontal scrollbar drag
        this.horizontalThumb.addEventListener('mousedown', (e) => {
            e.preventDefault();
            e.stopPropagation();
            this.isDraggingHorizontal = true;
            this.dragStartX = e.clientX;
            this.dragStartOffsetX = (this.canvas as any).ds?.offset?.[0] || 0;
            this.horizontalThumb.style.cursor = 'grabbing';
            this.horizontalThumb.style.background = 'rgba(255, 255, 255, 0.9)';
        });

        // Vertical scrollbar drag
        this.verticalThumb.addEventListener('mousedown', (e) => {
            e.preventDefault();
            e.stopPropagation();
            this.isDraggingVertical = true;
            this.dragStartY = e.clientY;
            this.dragStartOffsetY = (this.canvas as any).ds?.offset?.[1] || 0;
            this.verticalThumb.style.cursor = 'grabbing';
            this.verticalThumb.style.background = 'rgba(255, 255, 255, 0.9)';
        });

        // Horizontal scrollbar track click
        this.horizontalScrollbar.addEventListener('mousedown', (e) => {
            if (e.target === this.horizontalScrollbar) {
                const rect = this.horizontalScrollbar.getBoundingClientRect();
                const clickX = e.clientX - rect.left;
                const thumbWidth = this.horizontalThumb.offsetWidth;
                const trackWidth = rect.width;
                const thumbLeft = (clickX / trackWidth) * (trackWidth - thumbWidth);
                this.horizontalThumb.style.left = `${thumbLeft}px`;
                this.updateCanvasFromScrollbars();
            }
        });

        // Vertical scrollbar track click
        this.verticalScrollbar.addEventListener('mousedown', (e) => {
            if (e.target === this.verticalScrollbar) {
                const rect = this.verticalScrollbar.getBoundingClientRect();
                const clickY = e.clientY - rect.top;
                const thumbHeight = this.verticalThumb.offsetHeight;
                const trackHeight = rect.height;
                const thumbTop = (clickY / trackHeight) * (trackHeight - thumbHeight);
                this.verticalThumb.style.top = `${thumbTop}px`;
                this.updateCanvasFromScrollbars();
            }
        });

        // Global mouse move and up handlers
        document.addEventListener('mousemove', (e) => {
            if (this.isDraggingHorizontal) {
                const rect = this.cachedScrollbarRects?.h || this.horizontalScrollbar.getBoundingClientRect();
                const deltaX = e.clientX - this.dragStartX;
                const trackWidth = rect.width;
                const thumbWidth = this.horizontalThumb.offsetWidth;
                const maxLeft = trackWidth - thumbWidth;
                
                // Calculate new thumb position
                const currentLeft = parseFloat(this.horizontalThumb.style.left || '0');
                let newLeft = currentLeft + deltaX;
                newLeft = Math.max(0, Math.min(maxLeft, newLeft));
                this.horizontalThumb.style.left = `${newLeft}px`;
                
                // Update canvas offset
                this.updateCanvasFromScrollbars();
                
                this.dragStartX = e.clientX;
            }
            
            if (this.isDraggingVertical) {
                const rect = this.cachedScrollbarRects?.v || this.verticalScrollbar.getBoundingClientRect();
                const deltaY = e.clientY - this.dragStartY;
                const trackHeight = rect.height;
                const thumbHeight = this.verticalThumb.offsetHeight;
                const maxTop = trackHeight - thumbHeight;
                
                // Calculate new thumb position
                const currentTop = parseFloat(this.verticalThumb.style.top || '0');
                let newTop = currentTop + deltaY;
                newTop = Math.max(0, Math.min(maxTop, newTop));
                this.verticalThumb.style.top = `${newTop}px`;
                
                // Update canvas offset
                this.updateCanvasFromScrollbars();
                
                this.dragStartY = e.clientY;
            }
        });

        document.addEventListener('mouseup', () => {
            if (this.isDraggingHorizontal) {
                this.isDraggingHorizontal = false;
                this.horizontalThumb.style.cursor = 'grab';
                this.horizontalThumb.style.background = 'rgba(255, 255, 255, 0.5)';
            }
            if (this.isDraggingVertical) {
                this.isDraggingVertical = false;
                this.verticalThumb.style.cursor = 'grab';
                this.verticalThumb.style.background = 'rgba(255, 255, 255, 0.5)';
            }
        });
    }

    private getGraphBounds(): { minX: number; minY: number; maxX: number; maxY: number; width: number; height: number } {
        const now = Date.now();
        // Only recalculate bounds every 200ms unless dragging/interacting
        if (this.cachedBounds && (now - this.lastBoundsUpdate < 200) && !this.isDraggingHorizontal && !this.isDraggingVertical) {
            return this.cachedBounds;
        }

        const graph = (this.canvas as any).graph;
        const ds = (this.canvas as any).ds;
        const containerRect = this.cachedContainerRect || this.container.getBoundingClientRect();
        const scale = ds?.scale || 1;
        
        // Get all nodes from the graph
        const nodes = graph?.visible_nodes || graph?._nodes || [];
        
        // If no nodes, use viewport-based bounds as fallback
        if (!nodes || nodes.length === 0) {
            const viewportWidth = containerRect.width / scale;
            const viewportHeight = containerRect.height / scale;
            const currentOffsetX = ds?.offset?.[0] || 0;
            const currentOffsetY = ds?.offset?.[1] || 0;
            const viewportCenterX = -currentOffsetX / scale;
            const viewportCenterY = -currentOffsetY / scale;
            
            const bounds = {
                minX: viewportCenterX - viewportWidth,
                minY: viewportCenterY - viewportHeight,
                maxX: viewportCenterX + viewportWidth,
                maxY: viewportCenterY + viewportHeight,
                width: viewportWidth * 2,
                height: viewportHeight * 2
            };
            this.cachedBounds = bounds;
            this.lastBoundsUpdate = now;
            return bounds;
        }
        
        // Calculate bounds from actual node positions
        let minX = Infinity;
        let minY = Infinity;
        let maxX = -Infinity;
        let maxY = -Infinity;
        
        for (const node of nodes) {
            if (!node || !node.pos) continue;
            
            const [x, y] = node.pos;
            const [width, height] = node.size || [100, 100];
            
            minX = Math.min(minX, x);
            minY = Math.min(minY, y);
            maxX = Math.max(maxX, x + width);
            maxY = Math.max(maxY, y + height);
        }
        
        // Add padding around nodes (viewport size or minimum 500px, whichever is larger)
        const viewportWidth = containerRect.width / scale;
        const viewportHeight = containerRect.height / scale;
        const paddingX = Math.max(viewportWidth * 0.5, 500);
        const paddingY = Math.max(viewportHeight * 0.5, 500);
        
        minX -= paddingX;
        minY -= paddingY;
        maxX += paddingX;
        maxY += paddingY;
        
        // Ensure minimum bounds
        const width = maxX - minX;
        const height = maxY - minY;
        const minWidth = viewportWidth * 1.5;
        const minHeight = viewportHeight * 1.5;
        
        if (width < minWidth) {
            const centerX = (minX + maxX) / 2;
            minX = centerX - minWidth / 2;
            maxX = centerX + minWidth / 2;
        }
        
        if (height < minHeight) {
            const centerY = (minY + maxY) / 2;
            minY = centerY - minHeight / 2;
            maxY = centerY + minHeight / 2;
        }

        const bounds = {
            minX,
            minY,
            maxX,
            maxY,
            width: maxX - minX,
            height: maxY - minY
        };
        
        this.cachedBounds = bounds;
        this.lastBoundsUpdate = now;
        return bounds;
    }

    private updateCanvasFromScrollbars(): void {
        const ds = (this.canvas as any).ds;
        if (!ds || !ds.offset) return;

        const containerRect = this.cachedContainerRect || this.container.getBoundingClientRect();
        const scale = ds.scale || 1;
        const canvasWidth = containerRect.width;
        const canvasHeight = containerRect.height;
        
        // Get graph bounds (viewport-based)
        const bounds = this.getGraphBounds();
        
        // Get scrollbar positions
        const horizontalRect = this.cachedScrollbarRects?.h || this.horizontalScrollbar.getBoundingClientRect();
        const verticalRect = this.cachedScrollbarRects?.v || this.verticalScrollbar.getBoundingClientRect();
        
        const thumbLeft = parseFloat(this.horizontalThumb.style.left || '0');
        const thumbTop = parseFloat(this.verticalThumb.style.top || '0');
        
        const thumbWidth = this.horizontalThumb.offsetWidth;
        const thumbHeight = this.verticalThumb.offsetHeight;
        const trackWidth = horizontalRect.width;
        const trackHeight = verticalRect.height;
        
        // Calculate scroll position (0 to 1)
        const scrollX = thumbWidth < trackWidth ? thumbLeft / Math.max(1, trackWidth - thumbWidth) : 0;
        const scrollY = thumbHeight < trackHeight ? thumbTop / Math.max(1, trackHeight - thumbHeight) : 0;
        
        // Calculate content dimensions in screen space
        const contentWidth = bounds.width * scale;
        const contentHeight = bounds.height * scale;
        
        // Calculate offset range
        const maxOffsetX = Math.max(0, contentWidth - canvasWidth);
        const maxOffsetY = Math.max(0, contentHeight - canvasHeight);
        
        // Set canvas offset based on scroll position
        // Offset is negative because we're panning (moving content left/up)
        ds.offset[0] = -(bounds.minX * scale + maxOffsetX * scrollX);
        ds.offset[1] = -(bounds.minY * scale + maxOffsetY * scrollY);
        
        // Force redraw
        if ((this.canvas as any).graph && typeof (this.canvas as any).graph.change === 'function') {
            (this.canvas as any).graph.change();
        }
        if ((this.canvas as any).dirty_canvas !== undefined) {
            (this.canvas as any).dirty_canvas = true;
        }
    }

    private updateScrollbarsFromCanvas(): void {
        const ds = (this.canvas as any).ds;
        if (!ds || !ds.offset || !ds.scale) return;

        const containerRect = this.cachedContainerRect || this.container.getBoundingClientRect();
        const scale = ds.scale || 1;
        const offsetX = ds.offset[0] || 0;
        const offsetY = ds.offset[1] || 0;
        
        // Get viewport-based graph bounds
        const bounds = this.getGraphBounds();
        const canvasWidth = containerRect.width;
        const canvasHeight = containerRect.height;
        
        // Calculate content dimensions in screen space
        const contentWidth = bounds.width * scale;
        const contentHeight = bounds.height * scale;
        
        // Calculate scrollbar track dimensions
        const horizontalRect = this.cachedScrollbarRects?.h || this.horizontalScrollbar.getBoundingClientRect();
        const verticalRect = this.cachedScrollbarRects?.v || this.verticalScrollbar.getBoundingClientRect();
        const trackWidth = horizontalRect.width;
        const trackHeight = verticalRect.height;
        
        // Calculate thumb size based on visible area vs total content bounds
        // Thumb size represents how much of the content is currently
        const thumbWidth = Math.max(20, Math.min(trackWidth - 4, (canvasWidth / contentWidth) * trackWidth));
        const thumbHeight = Math.max(20, Math.min(trackHeight - 4, (canvasHeight / contentHeight) * trackHeight));
        
        // Update thumb sizes
        this.horizontalThumb.style.width = `${thumbWidth}px`;
        this.verticalThumb.style.height = `${thumbHeight}px`;
        
        // Calculate scroll position from offset
        // Offset is negative, so we need to convert it to a scroll position
        const maxOffsetX = Math.max(0, contentWidth - canvasWidth);
        const maxOffsetY = Math.max(0, contentHeight - canvasHeight);
        
        // Convert offset to scroll position (0 to 1)
        // offsetX = -(bounds.minX * scale + maxOffsetX * scrollX)
        // So: scrollX = (-offsetX - bounds.minX * scale) / maxOffsetX
        const scrollX = maxOffsetX > 0 
            ? Math.max(0, Math.min(1, (-offsetX - bounds.minX * scale) / maxOffsetX))
            : 0;
        const scrollY = maxOffsetY > 0
            ? Math.max(0, Math.min(1, (-offsetY - bounds.minY * scale) / maxOffsetY))
            : 0;
        
        // Update thumb positions
        const maxThumbLeft = Math.max(0, trackWidth - thumbWidth);
        const maxThumbTop = Math.max(0, trackHeight - thumbHeight);
        this.horizontalThumb.style.left = `${scrollX * maxThumbLeft}px`;
        this.verticalThumb.style.top = `${scrollY * maxThumbTop}px`;
    }

    private startUpdateLoop(): void {
        // Use requestAnimationFrame for smooth UI updates
        const loop = () => {
            if (!this.isDraggingHorizontal && !this.isDraggingVertical) {
                this.updateScrollbarsFromCanvas();
            }
            this.updateAnimationFrame = requestAnimationFrame(loop);
        };
        this.updateAnimationFrame = requestAnimationFrame(loop);
    }

    public destroy(): void {
        if (this.updateAnimationFrame !== null) {
            cancelAnimationFrame(this.updateAnimationFrame);
        }
        if (this.updateInterval !== null) {
            clearInterval(this.updateInterval);
        }
        window.removeEventListener('resize', () => this.updateCachedRects());
        this.horizontalScrollbar.remove();
        this.verticalScrollbar.remove();
    }
}

