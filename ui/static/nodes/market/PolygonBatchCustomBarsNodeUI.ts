import BaseCustomNode from '../base/BaseCustomNode';

export default class PolygonBatchCustomBarsNodeUI extends BaseCustomNode {
    constructor(title: string, data: any, serviceRegistry: any) {
        super(title, data, serviceRegistry);
        this.size = [200, 150];
    }

    updateDisplay(result: any) {
        // Store result for other functionality but don't display in node
        this.result = result;
        this.displayText = '';
        this.setDirtyCanvas(true, true);
    }

    setProgress(progress: number, text?: string) {
        super.setProgress(progress, text);
        this.setDirtyCanvas(true, true);  // Force immediate redraw
    }

}
