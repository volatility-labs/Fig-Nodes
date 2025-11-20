import BaseCustomNode from '../base/BaseCustomNode';

export default class MovingAverageFilterNodeUI extends BaseCustomNode {
    constructor(title: string, data: any, serviceRegistry: any) {
        super(title, data, serviceRegistry);
        this.size = [220, 100];
        this.displayResults = false; // Store results but don't display in node

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

