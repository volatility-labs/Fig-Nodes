import BaseCustomNode from '../base/BaseCustomNode';

export default class TextToLLMMessageNodeUI extends BaseCustomNode {
    constructor(title: string, data: any, serviceRegistry: any) {
        super(title, data, serviceRegistry);
        this.size = [280, 120];
        this.displayResults = false;
    }
}

