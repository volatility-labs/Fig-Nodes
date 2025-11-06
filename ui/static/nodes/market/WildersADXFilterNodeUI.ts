import BaseCustomNode from '../base/BaseCustomNode';

export default class WildersADXFilterNodeUI extends BaseCustomNode {
    constructor(title: string, data: any, serviceRegistry: any) {
        super(title, data, serviceRegistry);
        this.size = [380, 140];
    }

    updateDisplay(result: any) {
        this.result = result;
        this.displayText = '';
        this.setDirtyCanvas(true, true);
    }
}


