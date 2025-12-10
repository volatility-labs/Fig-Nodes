import BaseCustomNode from '../base/BaseCustomNode';

export default class AtrXFilterNodeUI extends BaseCustomNode {
    constructor(title: string, data: any, serviceRegistry: any) {
        super(title, data, serviceRegistry);
        this.displayResults = false; // Prevent UI expansion by not displaying raw output
    }
} 