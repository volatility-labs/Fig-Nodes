import BaseCustomNode from '../base/BaseCustomNode';

export default class WideningEMAsFilterNodeUI extends BaseCustomNode {
    constructor(title: string, data: any, serviceRegistry: any) {
        super(title, data, serviceRegistry);
        this.size = [240, 120];
        // Don't display results - filter nodes pass data through
        // Results should only show in LoggingNode or downstream nodes
        this.displayResults = false;
    }
}

