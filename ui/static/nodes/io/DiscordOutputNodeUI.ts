import BaseCustomNode from '../base/BaseCustomNode';
import { LiteGraph } from '@comfyorg/litegraph';

export default class DiscordOutputNodeUI extends BaseCustomNode {
    private statusMessage: string = '';
    private symbolCount: number = 0;

    constructor(title: string, data: any, serviceRegistry: any) {
        super(title, data, serviceRegistry);

        // Set appropriate size for displaying status
        this.size = [320, 140];
        this.color = '#5865F2'; // Discord brand color
        this.bgcolor = '#23272A'; // Discord dark background

        // Disable default canvas text rendering
        this.displayResults = false;
    }

    updateDisplay(result: any) {
        if (result && typeof result === 'object' && result.status) {
            const status = result.status;
            
            if (status.startsWith('Success')) {
                // Extract count from status
                const match = status.match(/(\d+)/);
                if (match) {
                    this.symbolCount = parseInt(match[1], 10);
                }
                this.statusMessage = `✅ ${status}`;
                this.pulseHighlight();
            } else if (status.startsWith('Skipped')) {
                this.statusMessage = `⏭️ ${status}`;
            } else if (status.startsWith('Error')) {
                this.statusMessage = `❌ ${status}`;
            } else {
                this.statusMessage = status;
            }
        } else {
            this.statusMessage = '⏳ Waiting for symbols...';
        }

        this.setDirtyCanvas(true, true);
    }

    onDrawForeground(ctx: CanvasRenderingContext2D) {
        if (this.flags?.collapsed) {
            return;
        }

        const padding = 10;
        const maxWidth = this.size[0] - padding * 2;
        const startY = LiteGraph.NODE_TITLE_HEIGHT + padding;

        ctx.textAlign = 'left';

        // Draw Discord logo/title
        ctx.font = 'bold 13px Arial';
        ctx.fillStyle = '#5865F2';
        ctx.fillText('📨 Discord Webhook', padding, startY);

        // Draw status message
        if (this.statusMessage) {
            ctx.font = '12px Arial';
            const lines = this.wrapText(this.statusMessage, maxWidth, ctx);
            let y = startY + 25;

            lines.forEach((line, index) => {
                // Color code based on status
                if (this.statusMessage.startsWith('✅')) {
                    ctx.fillStyle = '#57F287'; // Discord green
                } else if (this.statusMessage.startsWith('❌')) {
                    ctx.fillStyle = '#ED4245'; // Discord red
                } else if (this.statusMessage.startsWith('⏭️')) {
                    ctx.fillStyle = '#FEE75C'; // Discord yellow
                } else {
                    ctx.fillStyle = '#B9BBBE'; // Discord gray
                }

                ctx.fillText(line, padding, y + index * 16);
            });
        }

        // Draw helpful hint if webhook not configured
        if (this.statusMessage.includes('no webhook')) {
            ctx.font = '10px Arial';
            ctx.fillStyle = '#72767d';
            const hintY = this.size[1] - padding - 10;
            ctx.fillText('💡 Set DISCORD_WEBHOOK_URL in settings', padding, hintY);
        }
    }

    // Reset status when execution starts
    onExecutionStart() {
        this.statusMessage = '📤 Sending to Discord...';
        this.setDirtyCanvas(true, true);
    }

    // Handle execution errors
    onExecutionError(error: string) {
        this.statusMessage = `❌ Error: ${error}`;
        this.setDirtyCanvas(true, true);
    }

    // Clean up when node is reset/cleared
    reset() {
        this.statusMessage = '⏳ Waiting for symbols...';
        this.symbolCount = 0;
        this.setDirtyCanvas(true, true);
    }
}

