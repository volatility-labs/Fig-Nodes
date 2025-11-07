import BaseCustomNode from '../base/BaseCustomNode';

export default class KucoinTraderNodeUI extends BaseCustomNode {
    constructor(title: string, data: any, serviceRegistry: any) {
        super(title, data, serviceRegistry);
        this.size = [420, 140];
    }

    updateDisplay(result: any) {
        this.result = result;
        this.displayText = '';
        this.setDirtyCanvas(true, true);
    }
}


