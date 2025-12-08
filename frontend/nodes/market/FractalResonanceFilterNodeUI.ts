import BaseCustomNode from '../base/BaseCustomNode';

export default class FractalResonanceFilterNodeUI extends BaseCustomNode {
    constructor(title: string, data: any, serviceRegistry: any) {
        super(title, data, serviceRegistry);
        // Don't display results in widget - it expands the node with large JSON output
        this.displayResults = false;
    }
}

