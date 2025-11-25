import BaseCustomNode from '../base/BaseCustomNode';

export default class PolygonCryptoUniverseNodeUI extends BaseCustomNode {
    constructor(title: string, data: any, serviceRegistry: any) {
        super(title, data, serviceRegistry);
        
        this.displayResults = false; // Store results but don't display in node

        // After BaseCustomNode constructor adds widgets, customize their labels and properties
        if (this.widgets && data.params) {
            data.params.forEach((param: any, index: number) => {
                const widget = this.widgets && index < this.widgets.length ? this.widgets[index] : null;
                if (widget) {
                    const widgetLabel = param.label || param.name;
                    const unitSuffix = param.unit ? ` (${param.unit})` : '';

                    if (widget.type === 'number') {
                        // Update name with unit
                        widget.name = `${widgetLabel}${unitSuffix}`;
                        // Apply step if provided
                        if (param.step !== undefined) {
                            widget.options.step = param.step;
                        }
                    } else if (widget.type === 'button' && param.type === 'combo') {
                        // For combo, the name is already set to include the value, but we can set a custom property
                        widget.name = `${widgetLabel}${unitSuffix}: ${this.formatComboValue(this.properties[param.name])}`;
                    } else if (widget.type === 'boolean' || param.type === 'boolean') {
                        widget.name = `${widgetLabel}${unitSuffix}`;
                    } else {
                        widget.name = `${widgetLabel}${unitSuffix}`;
                    }

                    // Store description for potential future tooltip
                    widget.description = param.description || '';
                }
            });
        }
    }

    // Override syncWidgetValues to maintain custom labels
    syncWidgetValues() {
        super.syncWidgetValues();
        // After sync, reapply custom labels if needed (e.g., for combo updates)
        if (this.widgets && this.constructor.name === 'PolygonCryptoUniverseNodeUI') {
            // Hardcode the params to match PolygonCryptoUniverse params
            const params = [
                { name: 'min_change_perc', label: 'Min Change', unit: '%' },
                { name: 'max_change_perc', label: 'Max Change', unit: '%' },
                { name: 'min_volume', label: 'Min Volume', unit: 'shares/contracts' },
                { name: 'min_price', label: 'Min Price', unit: 'USD' },
                { name: 'max_price', label: 'Max Price', unit: 'USD' },
                { name: 'data_day', label: 'Data Day' },
            ];
            params.forEach((param, index) => {
                const widget = this.widgets && index < this.widgets.length ? this.widgets[index] : null;
                if (widget && widget.type === 'button') {
                    const unitSuffix = param.unit ? ` (${param.unit})` : '';
                    widget.name = `${param.label}${unitSuffix}: ${this.formatComboValue(this.properties[param.name])}`;
                }
            });
        }
    }
}




