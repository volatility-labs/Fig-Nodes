import BaseCustomNode from '../base/BaseCustomNode';

export default class DuplicateSymbolFilterNodeUI extends BaseCustomNode {
    constructor(title: string, data: any, serviceRegistry: any) {
        super(title, data, serviceRegistry);
        this.size = [250, 120];
    }

    updateDisplay(result: any) {
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

