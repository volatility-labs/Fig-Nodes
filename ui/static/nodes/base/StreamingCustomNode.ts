import BaseCustomNode from '../base/BaseCustomNode';

export default class StreamingCustomNode extends BaseCustomNode {
    isStreaming: boolean = true;
    status: string = 'Idle';

    constructor(title: string, data: any) {
        super(title, data);
        this.color = '#FF00FF'; // Purple for streaming nodes
    }

    onStreamUpdate(data: any) {
        this.result = data;
        this.displayText = JSON.stringify(data, null, 2);
        this.setDirtyCanvas(true, true);
    }

    onDrawForeground(ctx: CanvasRenderingContext2D) {
        super.onDrawForeground(ctx);
        ctx.fillStyle = '#FFFFFF';
        ctx.font = '12px Arial';
        ctx.fillText(`Status: ${this.status}`, 10, this.size[1] - 10);
    }
}
