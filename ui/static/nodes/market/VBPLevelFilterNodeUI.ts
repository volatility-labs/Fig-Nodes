import BaseCustomNode from '../base/BaseCustomNode';

export default class VBPLevelFilterNodeUI extends BaseCustomNode {
    constructor(title: string, data: any, serviceRegistry: any) {
        super(title, data, serviceRegistry);
        this.size = [360, 140];
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

