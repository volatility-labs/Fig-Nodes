import BaseCustomNode from '../base/BaseCustomNode';

export default class IndicatorDataSynthesizerNodeUI extends BaseCustomNode {
    constructor(title: string, data: any, serviceRegistry: any) {
        super(title, data, serviceRegistry);
        this.size = [320, 200];
        this.displayResults = false; // Don't display results in node UI
    }
}

