import BaseCustomNode from '../base/BaseCustomNode';

export default class SMAFilterNodeUI extends BaseCustomNode {
    constructor(title: string, data: any, serviceRegistry: any) {
        super(title, data, serviceRegistry);
        this.size = [220, 100];
        this.color = '#2c5530';  // Green theme for market data
        this.bgcolor = '#1a3320';

        // After base setup, ensure step is explicitly set on number widgets
        if (this.widgets && Array.isArray(data?.params)) {
            data.params.forEach((param: any, index: number) => {
                const widget = this.widgets && index < this.widgets.length ? this.widgets[index] : null;
                if (!widget || widget.type !== 'number') return;

                if (param.step !== undefined) {
                    widget.options.step = param.step;
                }
            });
        }
    }

    updateDisplay(result: any) {
        // Store result for other functionality but don't display in node
        this.result = result;
        this.displayText = '';
        this.setDirtyCanvas(true, true);
    }

}
