import BaseCustomNode from '../base/BaseCustomNode';
import { LiteGraph } from '@comfyorg/litegraph';

export default class StockChartsViewerNodeUI extends BaseCustomNode {
    private urls: string[] = [];
    private statusMessage: string = '';
    private chartCount: number = 0;

    constructor(title: string, data: any, serviceRegistry: any) {
        super(title, data, serviceRegistry);

        // Set appropriate size for displaying status and URLs
        this.size = [350, 150];

        // Disable default canvas text rendering - we'll show custom status
        this.displayResults = false;
    }

    updateDisplay(result: any) {
        if (result && typeof result === 'object') {
            this.urls = Array.isArray(result.urls) ? result.urls : [];
            this.statusMessage = result.status || '';
            this.chartCount = typeof result.count === 'number' ? result.count : 0;

            // Show brief success highlight for successful openings
            if (this.statusMessage.includes('Successfully opened') ||
                this.statusMessage.includes('Generated')) {
                this.pulseHighlight();
            }
        } else {
            this.statusMessage = 'Waiting for symbols...';
            this.urls = [];
            this.chartCount = 0;
        }

        this.setDirtyCanvas(true, true);
    }

    onDrawForeground(ctx: CanvasRenderingContext2D) {
        if (this.flags?.collapsed) {
            return;
        }

        const padding = 8;
        const maxWidth = this.size[0] - padding * 2;
        const startY = LiteGraph.NODE_TITLE_HEIGHT + padding;

        ctx.font = '12px Arial';
        ctx.fillStyle = '#ffffff';
        ctx.textAlign = 'left';

        // Draw status message
        if (this.statusMessage) {
            const lines = this.wrapText(this.statusMessage, maxWidth, ctx);
            let y = startY;

            lines.forEach((line, index) => {
                // Color code based on status
                if (this.statusMessage.includes('Successfully opened')) {
                    ctx.fillStyle = '#4CAF50'; // Green for success
                } else if (this.statusMessage.includes('failed') ||
                          this.statusMessage.includes('Error') ||
                          this.statusMessage.includes('No symbols')) {
                    ctx.fillStyle = '#f44336'; // Red for error
                } else if (this.statusMessage.includes('Generated')) {
                    ctx.fillStyle = '#2196F3'; // Blue for generated
                } else {
                    ctx.fillStyle = '#ffffff'; // White for neutral
                }

                ctx.fillText(line, padding, y + index * 15);
                y += 15;
            });
        }

        // Draw chart count and URLs
        let contentY = startY + (this.statusMessage ? 45 : 0);

        if (this.chartCount > 0) {
            // Show chart count
            ctx.font = '11px Arial';
            ctx.fillStyle = '#FFD700'; // Gold color
            ctx.fillText(`📊 Charts: ${this.chartCount}`, padding, contentY);
            contentY += 20;

            // Show first few URLs (truncated)
            ctx.font = '9px monospace';
            ctx.fillStyle = '#888888';

            const maxUrlsToShow = 2;
            for (let i = 0; i < Math.min(this.urls.length, maxUrlsToShow); i++) {
                const url = this.urls[i];
                if (url) {
                    // Extract just the symbol from URL
                    const symbolMatch = url.match(/[?&]s=([^&]+)/);
                    const symbol = symbolMatch ? symbolMatch[1] : url;

                    const urlText = `🔗 ${symbol}`;
                    const truncatedUrl = this.wrapText(urlText, maxWidth, ctx)[0];

                    if (truncatedUrl) {
                        ctx.fillText(truncatedUrl, padding + 10, contentY);
                        contentY += 12;
                    }
                }
            }

            // Show ellipsis if there are more URLs
            if (this.urls.length > maxUrlsToShow) {
                ctx.fillText(`... and ${this.urls.length - maxUrlsToShow} more`, padding + 10, contentY);
            }
        }
    }

    // Reset status when execution starts
    onExecutionStart() {
        this.statusMessage = 'Opening charts...';
        this.urls = [];
        this.chartCount = 0;
        this.setDirtyCanvas(true, true);
    }

    // Handle execution errors
    onExecutionError(error: string) {
        this.statusMessage = `❌ Error: ${error}`;
        this.urls = [];
        this.chartCount = 0;
        this.setDirtyCanvas(true, true);
    }

    // Clean up when node is reset/cleared
    reset() {
        this.urls = [];
        this.statusMessage = 'Waiting for symbols...';
        this.chartCount = 0;
        this.setDirtyCanvas(true, true);
    }

    // Helper method to wrap text
    private wrapText(text: string, maxWidth: number, ctx: CanvasRenderingContext2D): string[] {
        const words = text.split(' ');
        const lines: string[] = [];
        let currentLine = '';

        for (const word of words) {
            const testLine = currentLine + (currentLine ? ' ' : '') + word;
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

        return lines;
    }
}
