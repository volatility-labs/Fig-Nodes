import BaseCustomNode from '../base/BaseCustomNode';

export default class PolygonBatchCustomBarsNodeUI extends BaseCustomNode {
    constructor(title: string, data: any, serviceRegistry: any) {
        super(title, data, serviceRegistry);
        this.size = [200, 180];
        this.displayResults = false; // Store results but don't display in node
    }

    // Custom override to prevent display of results in node
    updateDisplay(result: any) {
        this.result = result;
        this.displayText = '';
        this.setDirtyCanvas(true, true);
    }

    setProgress(progress: number, text?: string) {
        super.setProgress(progress, text);
        this.setDirtyCanvas(true, true);  // Force immediate redraw to reflect progress updates
    }

}
