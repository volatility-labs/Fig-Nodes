import { LGraphNode, LiteGraph } from '@fig-node/litegraph';
import type { BodyWidget, ResultWidget } from '@fig-node/core';

// Extended node type with Option B properties
export interface RenderableNode extends LGraphNode {
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
    // Option B additions
    bodyWidgets?: BodyWidget[];
    resultWidget?: ResultWidget;
    getDataSourceValue?: (name: string) => unknown;
}

export class NodeRenderer {
    protected node: RenderableNode;

    constructor(node: RenderableNode) {
        this.node = node;
    }

    wrapText(text: string, maxWidth: number, ctx: CanvasRenderingContext2D): string[] {
        if (typeof text !== 'string') return [];
        const lines: string[] = [];
        const paragraphs = text.split('\n');
        for (const p of paragraphs) {
            const words = p.split(' ');
            let currentLine = words[0] || '';
            for (let i = 1; i < words.length; i++) {
                const word = words[i];
                const testLine = currentLine ? `${currentLine} ${word}` : word;
                const testWidth = ctx.measureText(testLine).width;
                
                if (testWidth > maxWidth) {
                    // If current line has content, push it and start new line
                    if (currentLine) {
                        lines.push(currentLine);
                        currentLine = '';
                    }
                    
                    // Handle word that's longer than maxWidth by breaking it
                    const wordWidth = ctx.measureText(word).width;
                    if (wordWidth > maxWidth) {
                        // Break long word into chunks
                        let remainingWord = word;
                        while (remainingWord) {
                            let chunk = '';
                            for (let j = 0; j < remainingWord.length; j++) {
                                const testChunk = chunk + remainingWord[j];
                                if (ctx.measureText(testChunk).width > maxWidth && chunk) {
                                    break;
                                }
                                chunk = testChunk;
                            }
                            if (chunk) {
                                lines.push(chunk);
                                remainingWord = remainingWord.slice(chunk.length);
                            } else {
                                // Single character is wider than maxWidth (shouldn't happen, but handle gracefully)
                                lines.push(remainingWord[0] || '');
                                remainingWord = remainingWord.slice(1);
                            }
                        }
                        currentLine = '';
                    } else {
                        // Word fits on its own line
                        currentLine = word;
                    }
                } else {
                    currentLine = testLine;
                }
            }
            if (currentLine) lines.push(currentLine);
        }
        return lines;
    }

    /**
     * Convert hex color to RGB array
     */
    private hexToRgb(hex: string): [number, number, number] | null {
        const result = /^#?([a-f\d]{2})([a-f\d]{2})([a-f\d]{2})$/i.exec(hex);
        return result ? [
            parseInt(result[1], 16),
            parseInt(result[2], 16),
            parseInt(result[3], 16)
        ] : null;
    }

    /**
     * Easing function for smooth animation (ease-out cubic)
     */
    private easeOutCubic(t: number): number {
        return 1 - Math.pow(1 - t, 3);
    }

    onDrawForeground(ctx: CanvasRenderingContext2D) {
        this.drawHighlight(ctx);
        this.drawProgressBar(ctx);
        this.drawBodyWidgets(ctx);  // Option B: Draw body widgets
        this.drawContent(ctx);
        this.drawError(ctx);
    }

    // ============ Option B: Body Widget Rendering ============

    /**
     * Get the Y position where body content starts (after title, progress bar, and param widgets)
     */
    protected getBodyStartY(): number {
        let y = LiteGraph.NODE_TITLE_HEIGHT + 4;
        if (this.node.progress >= 0) y += 9;
        const nodeWithWidgets = this.node as { widgets?: unknown[] };
        if (nodeWithWidgets.widgets) {
            y += nodeWithWidgets.widgets.length * LiteGraph.NODE_WIDGET_HEIGHT;
        }
        return y + 5;
    }

    /**
     * Draw all body widgets configured in uiConfig.body
     */
    protected drawBodyWidgets(ctx: CanvasRenderingContext2D) {
        const nodeWithFlags = this.node as { flags?: { collapsed?: boolean }; size: [number, number] };
        if (nodeWithFlags.flags?.collapsed) return;
        if (!this.node.bodyWidgets?.length) return;

        let y = this.getBodyStartY();
        const x = 10;
        const width = nodeWithFlags.size[0] - 20;

        for (const widget of this.node.bodyWidgets) {
            // Check showIf condition
            if (widget.showIf && !this.evaluateCondition(widget.showIf)) {
                continue;
            }

            y = this.renderBodyWidget(ctx, widget, x, y, width);
        }
    }

    /**
     * Render a single body widget and return the new Y position
     */
    protected renderBodyWidget(
        ctx: CanvasRenderingContext2D,
        widget: BodyWidget,
        x: number,
        y: number,
        width: number
    ): number {
        switch (widget.type) {
            case 'textarea':
                // DOM widget - skip canvas rendering, space is reserved via widget.computedHeight
                // The actual element is positioned by LGraphCanvas.updateDOMWidgetPositions()
                return y + ((widget.options as { height?: number })?.height ?? 100);
            case 'text':
                return this.renderTextBodyWidget(ctx, widget, x, y, width);
            case 'status':
                return this.renderStatusWidget(ctx, widget, x, y, width);
            case 'progress':
                return this.renderProgressWidget(ctx, widget, x, y, width);
            case 'table':
                return this.renderTableWidget(ctx, widget, x, y, width);
            case 'json':
                return this.renderJsonWidget(ctx, widget, x, y, width);
            case 'chart':
                return this.renderChartWidget(ctx, widget, x, y, width);
            default:
                return y;
        }
    }

    /**
     * Render a text body widget
     */
    protected renderTextBodyWidget(
        ctx: CanvasRenderingContext2D,
        widget: BodyWidget,
        x: number,
        y: number,
        width: number
    ): number {
        ctx.font = '12px Arial';
        ctx.fillStyle = LiteGraph.NODE_TEXT_COLOR || '#AAA';
        ctx.textAlign = 'left';

        let text = '';

        // Handle template binding
        if (widget.options?.template && widget.bind === 'params') {
            text = this.interpolateTemplate(
                widget.options.template as string,
                this.node.properties
            );
        } else if (widget.bind) {
            text = String(this.resolveBinding(widget.bind) ?? '');
        }

        if (widget.label) {
            text = `${widget.label}: ${text}`;
        }

        const lines = this.wrapText(text, width, ctx);
        lines.forEach((line, i) => {
            ctx.fillText(line, x, y + i * 15);
        });

        return y + Math.max(lines.length, 1) * 15 + 5;
    }

    /**
     * Render a status indicator widget
     */
    protected renderStatusWidget(
        ctx: CanvasRenderingContext2D,
        widget: BodyWidget,
        x: number,
        y: number,
        _width: number
    ): number {
        const status = String(this.resolveBinding(widget.bind ?? '') ?? 'unknown');
        const colors: Record<string, string> = {
            connected: '#4CAF50',
            disconnected: '#f44336',
            pending: '#ff9800',
            ok: '#4CAF50',
            error: '#f44336',
            unknown: '#9e9e9e',
        };

        // Draw status dot
        ctx.beginPath();
        ctx.arc(x + 6, y + 6, 5, 0, Math.PI * 2);
        ctx.fillStyle = colors[status.toLowerCase()] ?? colors.unknown;
        ctx.fill();

        // Draw label
        ctx.font = '12px Arial';
        ctx.fillStyle = LiteGraph.NODE_TEXT_COLOR || '#AAA';
        ctx.fillText(widget.label ?? status, x + 16, y + 10);

        return y + 20;
    }

    /**
     * Render a progress bar widget
     */
    protected renderProgressWidget(
        ctx: CanvasRenderingContext2D,
        widget: BodyWidget,
        x: number,
        y: number,
        width: number
    ): number {
        const value = Number(this.resolveBinding(widget.bind ?? '') ?? 0);
        const percent = Math.max(0, Math.min(100, value));

        // Background
        ctx.fillStyle = 'rgba(0, 0, 0, 0.2)';
        ctx.fillRect(x, y, width, 8);

        // Fill
        ctx.fillStyle = (widget.options?.color as string) ?? '#2196f3';
        ctx.fillRect(x, y, (width * percent) / 100, 8);

        // Label
        if (widget.label) {
            ctx.font = '10px Arial';
            ctx.fillStyle = LiteGraph.NODE_TEXT_COLOR || '#AAA';
            ctx.textAlign = 'left';
            ctx.fillText(`${widget.label}: ${percent.toFixed(0)}%`, x, y + 18);
            return y + 25;
        }

        return y + 15;
    }

    /**
     * Render a table widget
     */
    protected renderTableWidget(
        ctx: CanvasRenderingContext2D,
        widget: BodyWidget,
        x: number,
        y: number,
        width: number
    ): number {
        const data = this.resolveBinding(widget.bind ?? '') as unknown[];
        if (!Array.isArray(data) || data.length === 0) return y;

        const columns = (widget.options?.columns as Array<{ key: string; label: string }>) ?? [];
        const maxRows = (widget.options?.maxRows as number) ?? 5;
        const rowHeight = 16;

        ctx.font = '10px Arial';

        // Header
        ctx.fillStyle = '#666';
        let colX = x;
        const colWidth = width / Math.max(columns.length, 1);
        for (const col of columns) {
            ctx.fillText(col.label, colX, y);
            colX += colWidth;
        }
        y += rowHeight;

        // Rows
        ctx.fillStyle = LiteGraph.NODE_TEXT_COLOR || '#AAA';
        const rows = data.slice(0, maxRows);
        for (const row of rows) {
            colX = x;
            for (const col of columns) {
                const value = (row as Record<string, unknown>)[col.key];
                ctx.fillText(String(value ?? ''), colX, y);
                colX += colWidth;
            }
            y += rowHeight;
        }

        if (data.length > maxRows) {
            ctx.fillStyle = '#666';
            ctx.fillText(`... ${data.length - maxRows} more`, x, y);
            y += rowHeight;
        }

        return y + 5;
    }

    /**
     * Render a JSON viewer widget
     */
    protected renderJsonWidget(
        ctx: CanvasRenderingContext2D,
        widget: BodyWidget,
        x: number,
        y: number,
        width: number
    ): number {
        const data = this.resolveBinding(widget.bind ?? '');
        const json = JSON.stringify(data, null, 2);
        const maxLines = (widget.options?.maxLines as number) ?? 10;
        const maxChars = Math.floor(width / 6); // Approximate char width

        ctx.font = '10px monospace';
        ctx.fillStyle = '#8be9fd';

        const lines = json.split('\n').slice(0, maxLines);
        for (const line of lines) {
            const truncated = line.length > maxChars ? line.slice(0, maxChars - 3) + '...' : line;
            ctx.fillText(truncated, x, y);
            y += 12;
        }

        return y + 5;
    }

    /**
     * Render a simple sparkline chart widget
     */
    protected renderChartWidget(
        ctx: CanvasRenderingContext2D,
        widget: BodyWidget,
        x: number,
        y: number,
        width: number
    ): number {
        const data = this.resolveBinding(widget.bind ?? '') as number[];
        if (!Array.isArray(data) || data.length === 0) return y;

        const height = (widget.options?.height as number) ?? 40;
        const min = Math.min(...data);
        const max = Math.max(...data);
        const range = max - min || 1;

        // Draw sparkline
        ctx.beginPath();
        ctx.strokeStyle = (widget.options?.color as string) ?? '#4CAF50';
        ctx.lineWidth = 1;

        data.forEach((value, i) => {
            const px = x + (i / (data.length - 1)) * width;
            const py = y + height - ((value - min) / range) * height;
            if (i === 0) ctx.moveTo(px, py);
            else ctx.lineTo(px, py);
        });

        ctx.stroke();

        return y + height + 10;
    }

    // ============ Helper Methods ============

    /**
     * Resolve a binding path like 'params.min_rsi' or 'result.count'
     */
    protected resolveBinding(path: string): unknown {
        if (!path) return undefined;

        const parts = path.split('.');
        let value: unknown = this.node;

        for (const part of parts) {
            if (value === null || value === undefined) return undefined;
            value = (value as Record<string, unknown>)[part];
        }

        return value;
    }

    /**
     * Interpolate {{param}} placeholders in a template string
     */
    protected interpolateTemplate(template: string, data: Record<string, unknown>): string {
        return template.replace(/\{\{(\w+)\}\}/g, (_, key) => {
            return String(data[key] ?? '');
        });
    }

    /**
     * Evaluate a simple condition like 'showChart === true'
     */
    protected evaluateCondition(condition: string): boolean {
        const match = condition.match(/(\w+)\s*(===|!==|>|<|>=|<=)\s*(.+)/);
        if (!match) return true;

        const [, param, op, rawValue] = match;
        const actual = this.node.properties[param];

        let expected: unknown;
        try {
            expected = JSON.parse(rawValue);
        } catch {
            expected = rawValue;
        }

        switch (op) {
            case '===': return actual === expected;
            case '!==': return actual !== expected;
            case '>': return (actual as number) > (expected as number);
            case '<': return (actual as number) < (expected as number);
            case '>=': return (actual as number) >= (expected as number);
            case '<=': return (actual as number) <= (expected as number);
            default: return true;
        }
    }

    protected drawHighlight(ctx: CanvasRenderingContext2D) {
        // Continuous pulsing while executing, or single pulse if not executing but has timestamp
        if (this.node.isExecuting || this.node.highlightStartTs !== null) {
            const now = performance.now();
            let elapsed: number;
            let easedPulse: number;
            
            if (this.node.isExecuting) {
                // Continuous pulsing: use modulo to create repeating cycle
                if (this.node.highlightStartTs === null) {
                    this.node.highlightStartTs = now;
                }
                elapsed = (now - this.node.highlightStartTs) % this.node.pulseCycleMs;
                const cycleProgress = elapsed / this.node.pulseCycleMs;
                // Use sine wave for smooth pulsing effect (0 to 1)
                const pulseIntensity = (Math.sin(cycleProgress * Math.PI * 2) + 1) / 2;
                // Apply slight easing for smoother feel on continuous pulse
                easedPulse = Math.pow(pulseIntensity, 0.8);
            } else {
                // Single pulse: use elapsed time directly with ease-out
                elapsed = now - (this.node.highlightStartTs || now);
                if (elapsed >= this.node.highlightDurationMs) {
                    this.node.highlightStartTs = null;
                    return;
                }
                // For single pulse, use ease-out curve directly (no additional easing needed)
                const t = elapsed / this.node.highlightDurationMs;
                easedPulse = 1 - this.easeOutCubic(t);
            }
            
            // Get theme color (connecting link color is appropriate for executing nodes)
            const highlightColor = LiteGraph.CONNECTING_LINK_COLOR || '#3fb950';
            const rgb = this.hexToRgb(highlightColor);
            
            if (rgb) {
                // Alpha pulses from 0.3 (min) to 0.8 (max) with fade
                const baseAlpha = 0.3;
                const peakAlpha = 0.8;
                const alpha = baseAlpha + (peakAlpha - baseAlpha) * easedPulse;
                
                // Glow intensity pulses from 3 to 10
                const minGlow = 3;
                const maxGlow = 10;
                const glow = minGlow + (maxGlow - minGlow) * easedPulse;
                
                // Add subtle color fade effect (slightly brighter at peak)
                const fadeMultiplier = 0.95 + (0.1 * easedPulse); // 0.95 to 1.05
                const fadedR = Math.min(255, Math.floor(rgb[0] * fadeMultiplier));
                const fadedG = Math.min(255, Math.floor(rgb[1] * fadeMultiplier));
                const fadedB = Math.min(255, Math.floor(rgb[2] * fadeMultiplier));
                
                ctx.save();
                ctx.strokeStyle = `rgba(${fadedR}, ${fadedG}, ${fadedB}, ${alpha.toFixed(3)})`;
                ctx.lineWidth = 2;
                (ctx as { shadowColor: string; shadowBlur: number }).shadowColor = `rgba(${fadedR}, ${fadedG}, ${fadedB}, ${(alpha * 0.7).toFixed(3)})`;
                (ctx as { shadowColor: string; shadowBlur: number }).shadowBlur = glow;
                
                const nodeWithSize = this.node as { size: [number, number] };
                const titleHeight = LiteGraph.NODE_TITLE_HEIGHT;
                
                // Draw rectangle that includes title bar (title bar is above y=0 in LiteGraph's coordinate system)
                // Start from top of title bar, include full node height
                ctx.strokeRect(
                    1, 
                    -titleHeight + 1, 
                    nodeWithSize.size[0] - 2, 
                    nodeWithSize.size[1] + titleHeight - 2
                );
                ctx.restore();
                this.node.setDirtyCanvas(true, true);
            } else {
                // Fallback if color parsing fails
                const baseAlpha = 0.3;
                const peakAlpha = 0.8;
                const alpha = baseAlpha + (peakAlpha - baseAlpha) * easedPulse;
                const minGlow = 3;
                const maxGlow = 10;
                const glow = minGlow + (maxGlow - minGlow) * easedPulse;
                
                ctx.save();
                ctx.strokeStyle = `rgba(63, 185, 80, ${alpha.toFixed(3)})`;
                ctx.lineWidth = 2;
                (ctx as { shadowColor: string; shadowBlur: number }).shadowColor = `rgba(63, 185, 80, ${(alpha * 0.7).toFixed(3)})`;
                (ctx as { shadowColor: string; shadowBlur: number }).shadowBlur = glow;
                const nodeWithSize = this.node as { size: [number, number] };
                const titleHeight = LiteGraph.NODE_TITLE_HEIGHT;
                ctx.strokeRect(1, -titleHeight + 1, nodeWithSize.size[0] - 2, nodeWithSize.size[1] + titleHeight - 2);
                ctx.restore();
                this.node.setDirtyCanvas(true, true);
            }
        }
    }

    drawProgressBar(ctx: CanvasRenderingContext2D) {
        const nodeWithFlags = this.node as { flags?: { collapsed?: boolean }; size: [number, number] };
        if (nodeWithFlags.flags?.collapsed) {
            return;
        }
        
        if (this.node.progress >= 0) {
            const barHeight = 5;
            const barY = 2;
            const nodeWithSize = this.node as { size: [number, number] };
            const barWidth = Math.max(0, nodeWithSize.size[0] - 16);
            const barX = 8;

            // Background bar
            ctx.fillStyle = 'rgba(0, 0, 0, 0.2)';
            ctx.fillRect(barX, barY, barWidth, barHeight);

            // Inner background
            ctx.fillStyle = 'rgba(255, 255, 255, 0.05)';
            ctx.fillRect(barX + 1, barY + 1, barWidth - 2, barHeight - 2);

            // Progress fill
            const clampedPercent = Math.max(0, Math.min(100, this.node.progress));
            const progressWidth = Math.max(0, Math.min(barWidth - 2, ((barWidth - 2) * clampedPercent) / 100));

            if (progressWidth > 0) {
                ctx.fillStyle = '#2196f3';
                ctx.fillRect(barX + 1, barY + 1, progressWidth, barHeight - 2);
            }

            // Progress text
            if (this.node.progressText) {
                ctx.save();
                ctx.fillStyle = '#ffffff';
                ctx.font = 'bold 10px Arial';
                ctx.textAlign = 'right';
                ctx.textBaseline = 'middle';

                ctx.shadowColor = 'rgba(0, 0, 0, 0.7)';
                ctx.shadowBlur = 1;
                ctx.shadowOffsetX = 0;
                ctx.shadowOffsetY = 1;

                ctx.fillText(this.node.progressText, barX + barWidth - 3, barY + barHeight / 2);
                ctx.restore();
            }
        }
    }

    protected drawContent(ctx: CanvasRenderingContext2D) {
        const nodeWithFlags = this.node as { flags?: { collapsed?: boolean }; size: [number, number] };
        if (nodeWithFlags.flags?.collapsed || !this.node.displayResults || !this.node.displayText) {
            return;
        }

        const maxWidth = nodeWithFlags.size[0] - 20;

        const tempCanvas = document.createElement('canvas');
        const tempCtx = tempCanvas.getContext('2d');
        if (!tempCtx) return;

        tempCtx.font = '12px Arial';
        const lines = this.wrapText(this.node.displayText, maxWidth, tempCtx);

        let y = LiteGraph.NODE_TITLE_HEIGHT + 4 + (this.node.progress >= 0 ? 9 : 0);
        const nodeWithWidgets = this.node as { widgets?: unknown[] };
        if (nodeWithWidgets.widgets) {
            y += nodeWithWidgets.widgets.length * LiteGraph.NODE_WIDGET_HEIGHT;
        }

        const hasContent = lines.length > 0;
        if (hasContent) {
            y += 10;
        }

        const contentHeight = lines.length * 15;
        let neededHeight = y + contentHeight;
        if (hasContent) {
            neededHeight += 10;
        }

        if (Math.abs(nodeWithFlags.size[1] - neededHeight) > 1) {
            nodeWithFlags.size[1] = neededHeight;
            this.node.setDirtyCanvas(true, true);
            return;
        }

        ctx.font = '12px Arial';
        ctx.fillStyle = LiteGraph.NODE_TEXT_COLOR || '#AAA';
        ctx.textAlign = 'left';

        lines.forEach((line, index) => {
            ctx.fillText(line, 10, y + index * 15);
        });
    }

    protected drawError(ctx: CanvasRenderingContext2D) {
        if (this.node.error) {
            ctx.fillStyle = '#FF0000';
            ctx.font = 'bold 12px Arial';
            const errorY = this.calculateErrorY();
            ctx.fillText(`Error: ${this.node.error}`, 10, errorY);
            const nodeWithSize = this.node as { size: [number, number] };
            nodeWithSize.size[1] = Math.max(nodeWithSize.size[1], errorY + 20);
        }
    }

    private calculateErrorY(): number {
        const baseY = LiteGraph.NODE_TITLE_HEIGHT + 4 + (this.node.progress >= 0 ? 9 : 0);
        const nodeWithWidgets = this.node as { widgets?: unknown[]; size: [number, number] };
        const widgetOffset = nodeWithWidgets.widgets ? nodeWithWidgets.widgets.length * LiteGraph.NODE_WIDGET_HEIGHT : 0;
        const contentOffset = this.node.displayText ? this.wrapText(this.node.displayText, nodeWithWidgets.size[0] - 20, { measureText: () => ({ width: 0 }) } as unknown as CanvasRenderingContext2D).length * 15 + 10 : 0;
        return baseY + widgetOffset + contentOffset;
    }

    setProgress(progress: number, text?: string) {
        this.node.progress = Math.max(-1, Math.min(100, progress));
        // Only update progressText if text is explicitly provided and non-empty
        if (text !== undefined && text !== '') {
            this.node.progressText = text;
        }
        this.node.setDirtyCanvas(true, true);
    }

    clearProgress() {
        this.node.progress = -1;
        this.node.progressText = '';
        this.node.setDirtyCanvas(true, true);
    }

    pulseHighlight() {
        // Start or continue execution highlighting
        if (this.node.highlightStartTs === null) {
            this.node.highlightStartTs = performance.now();
        }
        this.node.isExecuting = true;
        this.node.setDirtyCanvas(true, true);
    }

    clearHighlight() {
        // Stop execution highlighting
        this.node.isExecuting = false;
        this.node.highlightStartTs = null;
        this.node.setDirtyCanvas(true, true);
    }

}
