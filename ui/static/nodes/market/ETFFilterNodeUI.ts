import BaseCustomNode from '../base/BaseCustomNode';

export default class ETFFilterNodeUI extends BaseCustomNode {
    constructor(title: string, data: any, serviceRegistry: any) {
        super(title, data, serviceRegistry);
        this.size = [360, 160];
        this.color = '#2c5530';  // Green theme for market data
        this.bgcolor = '#1a3320';
    }

    updateDisplay(result: any) {
        // Store result for other functionality but don't display in node
        this.result = result;
        this.displayText = '';
        this.setDirtyCanvas(true, true);
    }

    displayFilteredPreview() {
        // Trigger execution to get fresh data for preview
        if (this.graph && this.graph.onExecuteStep) {
            this.graph.onExecuteStep();
        }
    }
}

