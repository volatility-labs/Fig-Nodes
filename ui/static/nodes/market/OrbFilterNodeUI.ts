import BaseCustomNode from '../base/BaseCustomNode';

export default class OrbFilterNodeUI extends BaseCustomNode {
    constructor(title: string, data: any) {
        super(title, data);
        this.size = [360, 120];
        this.color = '#2c5530';  // Green theme for market data
        this.bgcolor = '#1a3320';
    }

    updateDisplay(result: any) {
        // Store result for other functionality but don't display in node
        this.result = result;
        this.displayText = '';
        this.setDirtyCanvas(true, true);
    }

    setProgress(progress: number, text?: string) {
        super.setProgress(progress, text);
        // Force immediate redraw to reflect progress updates
        this.setDirtyCanvas(true, true);
    }
}
