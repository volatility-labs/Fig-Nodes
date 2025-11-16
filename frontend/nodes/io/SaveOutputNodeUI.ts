import BaseCustomNode from '../base/BaseCustomNode';
import { LiteGraph } from '@fig-node/litegraph';

export default class SaveOutputNodeUI extends BaseCustomNode {
    private savedFilePath: string = '';
    private statusMessage: string = '';

    constructor(title: string, data: any, serviceRegistry: any) {
        super(title, data, serviceRegistry);

        // Set appropriate size for displaying status
        this.size = [300, 120];

        // Disable default canvas text rendering - we'll show custom status
        this.displayResults = false;
    }

    updateDisplay(result: any) {
        if (result && typeof result === 'object' && result.filepath) {
            this.savedFilePath = result.filepath;
            this.statusMessage = `✅ Saved to: ${this.savedFilePath.split('/').pop()}`;

            // Show brief success highlight
            this.pulseHighlight();
        } else {
            this.statusMessage = 'Waiting for data...';
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
            const y = startY;

            lines.forEach((line, index) => {
                // Color code based on status
                if (this.statusMessage.startsWith('✅')) {
                    ctx.fillStyle = '#4CAF50'; // Green for success
                } else if (this.statusMessage.startsWith('❌')) {
                    ctx.fillStyle = '#f44336'; // Red for error
                } else {
                    ctx.fillStyle = '#ffffff'; // White for neutral
                }

                ctx.fillText(line, padding, y + index * 15);
            });
        }

        // Draw file path if available (smaller font, different color)
        if (this.savedFilePath) {
            const pathY = startY + (this.statusMessage ? 45 : 0);
            ctx.font = '10px monospace';
            ctx.fillStyle = '#888888';

            // Show just the filename, not full path
            const filename = this.savedFilePath.split('/').pop() || this.savedFilePath;
            const pathText = `📁 ${filename}`;

            // Truncate if too long
            const truncatedPath = this.wrapText(pathText, maxWidth, ctx)[0];
            if (truncatedPath && truncatedPath.length < pathText.length) {
                ctx.fillText(truncatedPath.substring(0, truncatedPath.length - 3) + '...', padding, pathY);
            } else if (truncatedPath) {
                ctx.fillText(truncatedPath, padding, pathY);
            }
        }
    }

    // Reset status when execution starts
    onExecutionStart() {
        this.statusMessage = 'Saving...';
        this.setDirtyCanvas(true, true);
    }

    // Handle execution errors
    onExecutionError(error: string) {
        this.statusMessage = `❌ Error: ${error}`;
        this.setDirtyCanvas(true, true);
    }

    // Clean up when node is reset/cleared
    reset() {
        this.savedFilePath = '';
        this.statusMessage = 'Waiting for data...';
        this.setDirtyCanvas(true, true);
    }
}
