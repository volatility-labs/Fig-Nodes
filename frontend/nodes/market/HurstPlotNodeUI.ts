import BaseCustomNode from '../base/BaseCustomNode';

export default class HurstPlotNodeUI extends BaseCustomNode {
    constructor(title: string, data: any, serviceRegistry: any) {
        super(title, data, serviceRegistry);
        this.size = [500, 480];
        this.displayResults = false;
    }

    updateDisplay(_result: any) {
        // Receive data but do not render images
        // Images are handled by ImageDisplayNodeUI
    }
}
