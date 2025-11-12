import BaseCustomNode from '../base/BaseCustomNode';

export default class OHLCVPlotEnhancedNodeUI extends BaseCustomNode {
    constructor(title: string, data: any, serviceRegistry: any) {
        super(title, data, serviceRegistry);
        this.displayResults = false; // Don't display results - ImageDisplay node will handle it
        this.size = [300, 360];
    }
}

