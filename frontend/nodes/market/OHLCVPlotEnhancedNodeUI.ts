import BaseCustomNode from '../base/BaseCustomNode';

export default class OHLCVPlotEnhancedNodeUI extends BaseCustomNode {
    constructor(title: string, data: any, serviceRegistry: any) {
        super(title, data, serviceRegistry);
        this.displayResults = false; 
        this.size = [300, 360];
    }
}

