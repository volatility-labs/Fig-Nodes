import BaseCustomNode from '../base/BaseCustomNode';

export default class MultiIndicatorChartNodeUI extends BaseCustomNode {
    constructor(title: string, data: any, serviceRegistry: any) {
        super(title, data, serviceRegistry);
        // Disable text display - images are displayed via ImageDisplayNodeUI
        // debug_info should go to LoggingNodeUI, not displayed here
        this.displayResults = false;
    }
}

