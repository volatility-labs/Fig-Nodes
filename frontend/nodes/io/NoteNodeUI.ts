import BaseCustomNode from '../base/BaseCustomNode';
import { LiteGraph } from '@fig-node/litegraph';

export default class NoteNodeUI extends BaseCustomNode {
    constructor(title: string = 'Note', data: any, serviceRegistry: any) {
        // Ensure data has no inputs/outputs to avoid BaseCustomNode adding them
        const noteData = {
            ...data,
            inputs: {},
            outputs: {},
            params: data.params || []
        };
        
        super(title, noteData, serviceRegistry);
        
        // Override default size
        this.size = [240, 160];
        
        // Make resizable
        this.resizable = true;
        
        // Disable collapse
        this.collapsable = false;
        
        // Clear any widgets that might have been added
        this.widgets = [];
        
        // Set default color (matches ComfyUI's note style)
        const color = (this.properties.color as string) || '#334';
        this.properties.color = color;
        this.color = color;
        this.bgcolor = color;
        
        // Set default text
        if (!this.properties.text) {
            this.properties.text = 'Note';
        }
        
        // Ensure no inputs or outputs
        this.inputs = [];
        this.outputs = [];

        // Set order to a very low value and lock it using a property descriptor
        // This prevents LiteGraph from modifying the order when nodes are selected
        const lockedOrder = -10000;
        Object.defineProperty(this, 'order', {
            get: () => lockedOrder,
            set: (_value: number) => {
                // Always ignore attempts to modify order - note nodes stay in background
            },
            enumerable: true,
            configurable: false
        });
        
        this.title = this.properties.text || 'Note';
        this.className = 'note-node';
    }

    // Override onDrawBackground to draw the colored rectangle (title bar + body same color)
    onDrawBackground(ctx: CanvasRenderingContext2D, canvas: any, pos: [number, number]) {
        if (this.flags?.collapsed) {
            super.onDrawBackground(ctx, canvas, pos);
            return;
        }

        const color = (this.properties.color as string) || '#334';
        
        // Draw the entire node (title bar + body) with the same color
        // This matches ComfyUI's note style where title bar and body share the same background
        ctx.save();
        ctx.fillStyle = color;
        ctx.beginPath();
        // Use rounded rectangle for ComfyUI-style appearance
        const radius = 4;
        const x = 0;
        const y = 0;
        const w = this.size[0];
        const h = this.size[1];
        
        ctx.roundRect(x, y, w, h, radius);
        ctx.fill();
        
        // Draw subtle border (lighter version of the color)
        ctx.strokeStyle = this.lightenColor(color, 0.15);
        ctx.lineWidth = 1;
        ctx.stroke();
        
        ctx.restore();
        
        // LiteGraph will draw the title text separately in its own rendering cycle

        // In onDrawBackground, after drawing the rectangle and border, add:
        ctx.save();
        ctx.fillStyle = '#ffffff';
        ctx.font = 'bold 14px Arial'; // Match ComfyUI title style
        ctx.textAlign = 'center';
        ctx.textBaseline = 'middle';

        const titleY = (LiteGraph.NODE_TITLE_HEIGHT / 2) - 2; // Slight adjustment for vertical centering
        const titleX = this.size[0] / 2;
        ctx.fillText(this.title, titleX, titleY);

        ctx.restore();
    }

    // Override onDblClick to edit title if click is in title area
    onDblClick(event: MouseEvent, pos: [number, number], canvas: any): boolean {
        // Check if click is in title area (top 30px)
        if (pos[1] < LiteGraph.NODE_TITLE_HEIGHT) {
            const newTitle = LiteGraph.prompt('Edit Title', this.title, { multiline: false });
            if (newTitle !== null && newTitle !== undefined) {
                this.title = newTitle;
                this.properties.text = newTitle; // Sync to properties if needed
                this.setDirtyCanvas(true, true);
            }
            return true;
        }
        return false;
    }

    // Handle property changes (e.g., color changes)
    onPropertyChanged(name: string, value: any) {
        if (name === 'color') {
            this.color = value;
            this.bgcolor = value;
            this.setDirtyCanvas(true, true);
        }
    }

    // Helper to lighten color for border
    private lightenColor(color: string, amount: number): string {
        const hex = color.replace('#', '');
        const num = parseInt(hex, 16);
        let r = Math.min(255, ((num >> 16) & 0xFF) + Math.round(255 * amount));
        let g = Math.min(255, ((num >> 8) & 0xFF) + Math.round(255 * amount));
        let b = Math.min(255, (num & 0xFF) + Math.round(255 * amount));
        return `#${((r << 16) | (g << 8) | b).toString(16).padStart(6, '0')}`;
    }
}

