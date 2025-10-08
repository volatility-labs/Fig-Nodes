import BaseCustomNode from '../base/BaseCustomNode';

export default class AtrXFilterNodeUI extends BaseCustomNode {
    constructor(title: string, data: any) {
        super(title, data);
        // Note: indicator_results output has been removed from the Python node definition
        // so it won't be created in the UI in the first place
    }
} 