import BaseCustomNode from '../base/BaseCustomNode';

export default class XcomUsersFeedNodeUI extends BaseCustomNode {
    constructor(title: string, data: any, serviceRegistry: any) {
        super(title, data, serviceRegistry);
        this.size = [240, 120];
        this.displayResults = false;
    }
}
