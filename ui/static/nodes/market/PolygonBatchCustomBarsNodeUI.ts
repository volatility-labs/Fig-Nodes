import BaseCustomNode from '../base/BaseCustomNode';

type DataStatus = 'real-time' | 'delayed' | 'market-closed' | null;

export default class PolygonBatchCustomBarsNodeUI extends BaseCustomNode {
    dataStatus: DataStatus = null;
    statusInfo: Record<string, any> = {};

    constructor(title: string, data: any, serviceRegistry: any) {
        super(title, data, serviceRegistry);
        this.size = [300, 150];
    }

    updateDisplay(result: any) {
        this.result = result;
        this.displayText = '';
        
        // Extract status info
        if (result?.status_info) {
            // For batch, get status from first symbol or aggregate
            const statusInfos = Object.values(result.status_info) as any[];
            if (statusInfos.length > 0) {
                const firstStatus = statusInfos[0];
                this.dataStatus = firstStatus.status || null;
                this.statusInfo = firstStatus;
            }
        }
        
        this.setDirtyCanvas(true, true);
    }

    onDrawForeground(ctx: CanvasRenderingContext2D) {
        super.onDrawForeground(ctx);
        this.drawStatusBadge(ctx);
    }

    private drawStatusBadge(ctx: CanvasRenderingContext2D) {
        if (!this.dataStatus) return;

        const badgeSize = 20;
        const padding = 8;
        const nodeSize = this.size as [number, number];
        const x = nodeSize[0] - badgeSize - padding;
        const y = padding;

        // Color coding
        let color: string;
        let label: string;
        
        switch (this.dataStatus) {
            case 'real-time':
                color = '#4caf50'; // Green
                label = 'RT';
                break;
            case 'delayed':
                color = '#ff9800'; // Orange
                label = 'DEL';
                break;
            case 'market-closed':
                color = '#757575'; // Gray
                label = 'CLOSED';
                break;
            default:
                return;
        }

        // Draw badge background
        ctx.save();
        ctx.fillStyle = color;
        ctx.beginPath();
        ctx.roundRect(x, y, badgeSize, badgeSize, 4);
        ctx.fill();

        // Draw label
        ctx.fillStyle = '#ffffff';
        ctx.font = 'bold 9px Arial';
        ctx.textAlign = 'center';
        ctx.textBaseline = 'middle';
        ctx.fillText(label, x + badgeSize / 2, y + badgeSize / 2);
        ctx.restore();
    }

    setProgress(progress: number, text?: string) {
        super.setProgress(progress, text);
        this.setDirtyCanvas(true, true);
    }
}
