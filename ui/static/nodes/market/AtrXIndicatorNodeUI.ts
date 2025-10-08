import BaseCustomNode from '../base/BaseCustomNode';

export default class AtrXIndicatorNodeUI extends BaseCustomNode {
    constructor(title: string, data: any) {
        super(title, data);
        // Remove the 'results' output slot from UI
        // Note: removeOutput not available in test environment
        // const slot = this.findOutputSlot('results');
        // if (slot !== -1) {
        //     (this as any).removeOutput(slot);
        // }
    }
} 