import BaseCustomNode from '../base/BaseCustomNode';

export default class LodFilterNodeUI extends BaseCustomNode {
    constructor(title: string, data: any, serviceRegistry: any) {
        super(title, data, serviceRegistry);
        this.size = [360, 120];
        this.displayResults = false; // Store results but don't display in node

        // After base setup, enhance numeric widget labels with units and ensure step/precision
        if (this.widgets && Array.isArray(data?.params)) {
            data.params.forEach((param: any, index: number) => {
                const widget = this.widgets && index < this.widgets.length ? this.widgets[index] : null;
                if (!widget) return;

                const label = param.label || param.name;
                const unitSuffix = param.unit ? ` (${param.unit})` : '';

                // Update number widgets to include label and unit
                if (widget.type === 'number') {
                    widget.name = `${label}${unitSuffix}`;
                    if (param.step !== undefined) {
                        widget.options.step = param.step;
                    }
                    if (param.precision !== undefined) {
                        widget.options.precision = param.precision;
                    }
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
