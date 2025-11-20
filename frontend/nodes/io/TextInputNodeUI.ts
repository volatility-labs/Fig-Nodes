import BaseCustomNode from '../base/BaseCustomNode';
import { LiteGraph } from '@fig-node/litegraph';

export default class TextInputNodeUI extends BaseCustomNode {
    private textareaEl: HTMLTextAreaElement | null = null;
    private lastCanvasRef: any = null;
    private positionUpdateId: number | null = null;
    private isTextareaFocused: boolean = false;

    constructor(title: string, data: any, serviceRegistry: any) {
        super(title, data, serviceRegistry);
        this.resizable = true;
        this.size = [360, 200];

        // Remove default widgets (incl. Title) and let inline textarea handle input
        this.widgets = [];

        if (!this.properties.value) {
            this.properties.value = '';
        }

        // Use default node theme colors for consistency with other nodes
        this.displayResults = false;
    }

    // Lifecycle: called by LiteGraph when node is added to graph
    onAdded() { this.ensureTextarea(); }

    onRemoved() {
        this.detachTextarea();
        if (this.positionUpdateId) {
            cancelAnimationFrame(this.positionUpdateId);
            this.positionUpdateId = null;
        }
    }

    onDeselected() {
        // Hide textarea when deselected unless it has focus
        if (!this.isTextareaFocused) {
            this.hideTextarea();
            this.setDirtyCanvas(true, true);
        } else {
            this.syncTextarea();
        }
    }

    onSelected() {
        // Show textarea when selected
        this.syncTextarea();
        this.setDirtyCanvas(true, true);
        
        // Always try to focus textarea after selection
        // Use multiple timeouts to ensure it happens after LiteGraph's event handling
        // and DOM updates
        requestAnimationFrame(() => {
            requestAnimationFrame(() => {
                setTimeout(() => {
                    if (this.textareaEl && this.textareaEl.style.display !== 'none') {
                        this.isTextareaFocused = true;
                        // Ensure pointer-events are enabled
                        this.textareaEl.style.pointerEvents = 'auto';
                        // Focus and place cursor at end
                        this.textareaEl.focus();
                        const textLength = this.textareaEl.value.length;
                        this.textareaEl.setSelectionRange(textLength, textLength);
                    }
                }, 10);
            });
        });
    }

    onResize(_size: [number, number]) {
        this.syncTextarea();
        this.setDirtyCanvas(true, true);
    }

    // Draw background and text (when textarea is hidden)
    onDrawForeground(ctx: CanvasRenderingContext2D) {
        if (this.flags?.collapsed) {
            this.hideTextarea();
            return;
        }

        const padding = 8;
        const x = padding;
        const y = LiteGraph.NODE_TITLE_HEIGHT + padding;
        const w = Math.max(0, this.size[0] - padding * 2);
        const h = Math.max(0, this.size[1] - LiteGraph.NODE_TITLE_HEIGHT - padding * 2);

        // Use theme-aware widget colors (set by ThemeManager)
        ctx.fillStyle = LiteGraph.WIDGET_BGCOLOR;
        ctx.fillRect(x, y, w, h);

        // Border using theme widget outline color
        ctx.strokeStyle = LiteGraph.WIDGET_OUTLINE_COLOR;
        ctx.lineWidth = 1;
        ctx.strokeRect(x + 0.5, y + 0.5, w - 1, h - 1);

        // Check if textarea should be visible
        const graph = this.graph;
        const canvas = graph && graph.list_of_graphcanvas && graph.list_of_graphcanvas[0];
        const selectedNodes = canvas?.selected_nodes || {};
        const isSelected = selectedNodes[this.id];
        const shouldShowTextarea = isSelected || this.isTextareaFocused;

        // If textarea should be hidden, render text on canvas
        if (!shouldShowTextarea) {
            this.drawTextOnCanvas(ctx, x, y, w, h);
        }

        // Schedule position update for textarea
        this.schedulePositionUpdate(x, y, w, h);
    }

    private drawTextOnCanvas(ctx: CanvasRenderingContext2D, x: number, y: number, w: number, h: number) {
        const text = String(this.properties.value || '');
        if (!text.trim()) return;

        // Save canvas context state to restore after drawing
        const savedFillStyle = ctx.fillStyle;
        const savedTextAlign = ctx.textAlign;
        const savedTextBaseline = ctx.textBaseline;

        ctx.font = '12px monospace';
        // Use theme-aware widget text color (set by ThemeManager)
        ctx.fillStyle = LiteGraph.WIDGET_TEXT_COLOR;
        ctx.textAlign = 'left';
        ctx.textBaseline = 'top';

        const lineHeight = 14;
        const maxLines = Math.floor(h / lineHeight);
        const padding = 8;
        const textX = x + padding;
        const textY = y + padding;
        const maxWidth = w - padding * 2;

        // Simple text wrapping
        const words = text.split(/\s+/);
        const lines: string[] = [];
        let currentLine = '';

        for (const word of words) {
            const testLine = currentLine ? `${currentLine} ${word}` : word;
            const metrics = ctx.measureText(testLine);
            if (metrics.width > maxWidth && currentLine) {
                lines.push(currentLine);
                currentLine = word;
            } else {
                currentLine = testLine;
            }
        }
        if (currentLine) {
            lines.push(currentLine);
        }

        // Draw lines (truncate if too many)
        const linesToDraw = lines.slice(0, maxLines);
        linesToDraw.forEach((line, index) => {
            ctx.fillText(line, textX, textY + index * lineHeight);
        });

        // Show ellipsis if truncated
        if (lines.length > maxLines) {
            ctx.fillText('...', textX, textY + maxLines * lineHeight);
        }

        // Restore canvas context state to prevent affecting output slot label positioning
        ctx.fillStyle = savedFillStyle;
        ctx.textAlign = savedTextAlign;
        ctx.textBaseline = savedTextBaseline;
    }

    // Override mouse handling to immediately focus textarea when clicking in textarea area
    onMouseDown(_e: any, pos: [number, number], _canvas: any): boolean {
        const padding = 8;
        const x = padding;
        const y = LiteGraph.NODE_TITLE_HEIGHT + padding;
        const w = Math.max(0, this.size[0] - padding * 2);
        const h = Math.max(0, this.size[1] - LiteGraph.NODE_TITLE_HEIGHT - padding * 2);

        // Check if click is within the textarea area (excluding title bar)
        // pos is relative to node position: [canvasX - node.pos[0], canvasY - node.pos[1]]
        const clickX = pos[0];
        const clickY = pos[1];

        if (clickX >= x && clickX <= x + w && clickY >= y && clickY <= y + h) {
            // Ensure textarea exists and is ready
            this.ensureTextarea();
            
            if (this.textareaEl) {
                // Mark as focused to keep it visible
                this.isTextareaFocused = true;
                
                // Sync value and position immediately
                const current = String(this.properties.value ?? '');
                if (this.textareaEl.value !== current) {
                    this.textareaEl.value = current;
                }
                
                // Position synchronously
                this.positionTextarea(x, y, w, h);
                
                // Focus the textarea immediately
                // Use requestAnimationFrame to ensure DOM is ready
                requestAnimationFrame(() => {
                    if (this.textareaEl && this.textareaEl.style.display !== 'none') {
                        this.textareaEl.focus();
                        const textLength = this.textareaEl.value.length;
                        this.textareaEl.setSelectionRange(textLength, textLength);
                    }
                });
            }
            
            // Return false to allow normal node selection behavior
            // The textarea will be focused via requestAnimationFrame
            return false;
        }

        // Not in textarea area - allow default behavior
        return false;
    }

    private schedulePositionUpdate(x: number, y: number, w: number, h: number) {
        if (this.positionUpdateId !== null) return;
        
        this.positionUpdateId = requestAnimationFrame(() => {
            this.positionUpdateId = null;
            this.ensureTextarea();
            this.positionTextarea(x, y, w, h);
        });
    }

    private ensureTextarea() {
        const graph = this.graph;
        if (!graph) return;
        const canvas = graph.list_of_graphcanvas && graph.list_of_graphcanvas[0];
        if (!canvas || !canvas.canvas) return;

        if (!this.textareaEl || this.lastCanvasRef !== canvas) {
            this.detachTextarea();
            this.lastCanvasRef = canvas;
            
            // Attach to canvas container (#main-content) instead of document.body
            const canvasContainer = canvas.canvas.parentElement;
            if (!canvasContainer) return;

            const ta = document.createElement('textarea');
            ta.className = 'inline-node-textarea monospace';
            ta.spellcheck = false;
            ta.value = String(this.properties.value || '');
            ta.style.padding = '8px';
            
            ta.addEventListener('input', () => {
                this.properties.value = ta.value;
                this.setDirtyCanvas(true, true);
            });
            
            ta.addEventListener('blur', () => {
                this.properties.value = ta.value;
                this.isTextareaFocused = false;
                const graph = this.graph;
                const canvas = graph && graph.list_of_graphcanvas && graph.list_of_graphcanvas[0];
                const selectedNodes = canvas?.selected_nodes || {};
                const isSelected = selectedNodes[this.id];
                if (!isSelected) {
                    this.hideTextarea();
                    this.setDirtyCanvas(true, true);
                }
            });
            
            ta.addEventListener('focus', () => {
                this.isTextareaFocused = true;
                this.syncTextarea();
                this.setDirtyCanvas(true, true);
            });
            
            ta.addEventListener('mousedown', (ev) => {
                // Stop propagation to prevent canvas from handling the click
                ev.stopPropagation();
                // Focus immediately when clicking directly on textarea
                setTimeout(() => {
                    if (this.textareaEl && document.activeElement !== this.textareaEl) {
                        this.textareaEl.focus();
                    }
                }, 0);
            });
            
            // Stop key events from bubbling to canvas shortcuts
            ta.addEventListener('keydown', (ev) => {
                ev.stopPropagation();
            });
            
            canvasContainer.appendChild(ta);
            this.textareaEl = ta;
        }
    }

    private detachTextarea() {
        if (this.textareaEl && this.textareaEl.parentElement) {
            this.textareaEl.parentElement.removeChild(this.textareaEl);
        }
        this.textareaEl = null;
        this.lastCanvasRef = null;
    }

    private hideTextarea() {
        if (this.textareaEl) {
            this.textareaEl.style.display = 'none';
            // Ensure pointer-events are disabled when hidden to prevent intercepting clicks
            this.textareaEl.style.pointerEvents = 'none';
        }
    }

    private syncTextarea() {
        if (!this.textareaEl) return;
        this.textareaEl.style.display = '';
        const current = String(this.properties.value ?? '');
        if (this.textareaEl.value !== current) {
            this.textareaEl.value = current;
        }
        // Ensure position up-to-date
        const padding = 8;
        const x = padding;
        const y = LiteGraph.NODE_TITLE_HEIGHT + padding;
        const w = Math.max(0, this.size[0] - padding * 2);
        const h = Math.max(0, this.size[1] - LiteGraph.NODE_TITLE_HEIGHT - padding * 2);
        this.positionTextarea(x, y, w, h);
    }

    private positionTextarea(localX: number, localY: number, localW: number, localH: number) {
        if (!this.textareaEl) return;
        const graph = this.graph;
        const canvas = graph && graph.list_of_graphcanvas && graph.list_of_graphcanvas[0];
        if (!canvas || !canvas.canvas) return;

        // Get canvas container
        const canvasContainer = canvas.canvas.parentElement;
        if (!canvasContainer) {
            this.textareaEl.style.display = 'none';
            return;
        }

        // Get canvas transform from LiteGraph's internal state
        const scale = (canvas as any).ds?.scale || (canvas as any).scale || 1;
        const offset = (canvas as any).ds?.offset || (canvas as any).offset || [0, 0];
        const offx = Array.isArray(offset) ? offset[0] : 0;
        const offy = Array.isArray(offset) ? offset[1] : 0;

        // Snapshot position to avoid race conditions
        const nodePos = [...this.pos] as [number, number];

        // Convert canvas coordinates to screen coordinates: (pos + offset) * scale
        const canvasX = (nodePos[0] + localX + offx) * scale;
        const canvasY = (nodePos[1] + localY + offy) * scale;
        const canvasW = localW * scale;
        const canvasH = localH * scale;

        // Get canvas element position on screen
        const canvasRect = canvas.canvas.getBoundingClientRect();
        const containerRect = canvasContainer.getBoundingClientRect();

        // Calculate position relative to canvas container
        // Since container has position: relative, we need relative coordinates
        const relativeX = canvasRect.left - containerRect.left + canvasX;
        const relativeY = canvasRect.top - containerRect.top + canvasY;

        // Position relative to canvas container (which has position: relative)
        const style = this.textareaEl.style;
        style.position = 'absolute';
        style.left = `${relativeX}px`;
        style.top = `${relativeY}px`;
        style.width = `${Math.max(0, canvasW)}px`;
        style.height = `${Math.max(0, canvasH)}px`;
        style.zIndex = '100'; // Lower than footer (1001) but above canvas

        // Match inline title editor behavior: scale font size with zoom
        style.fontSize = `${12 * scale}px`;

        // Check if node is selected
        const selectedNodes = canvas.selected_nodes || {};
        const isSelected = selectedNodes[this.id];

        // Only show textarea if selected or focused
        if (!isSelected && !this.isTextareaFocused) {
            this.textareaEl.style.display = 'none';
            return;
        }

        // Hide if too small or out of container bounds
        const containerWidth = containerRect.width;
        const containerHeight = containerRect.height;

        if (canvasW <= 2 || canvasH <= 2 || 
            relativeX + canvasW < 0 || relativeY + canvasH < 0 ||
            relativeX > containerWidth || relativeY > containerHeight) {
            this.textareaEl.style.display = 'none';
            this.textareaEl.style.pointerEvents = 'none';
        } else {
            this.textareaEl.style.display = '';
            // Only enable pointer-events when visible and selected/focused
            if (isSelected || this.isTextareaFocused) {
                this.textareaEl.style.pointerEvents = 'auto';
            } else {
                this.textareaEl.style.pointerEvents = 'none';
            }
        }
    }
}