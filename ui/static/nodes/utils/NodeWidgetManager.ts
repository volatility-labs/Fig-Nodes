import { LGraphNode } from '@comfyorg/litegraph';
import { NodeTypeSystem } from './NodeTypeSystem';

export class NodeWidgetManager {
    private node: LGraphNode & { properties: { [key: string]: any } };

    constructor(node: LGraphNode & { properties: { [key: string]: any } }) {
        this.node = node;
    }

    createWidgetsFromParams(params: any[]) {
        params.forEach((param: any) => {
            let paramType = param.type;
            if (!paramType) {
                paramType = NodeTypeSystem.determineParamType(param.name);
            }
            const defaultValue = param.default !== undefined ? param.default : NodeTypeSystem.getDefaultValue(param.name);
            this.node.properties[param.name] = defaultValue;

            const typeLower = String(paramType || '').toLowerCase();

            if (typeLower === 'text' || typeLower === 'string') {
                this.createTextWidget(param);
            } else if (typeLower === 'textarea') {
                this.createTextareaWidget(param);
            } else if (typeLower === 'number' || typeLower === 'integer' || typeLower === 'int' || typeLower === 'float') {
                this.createNumberWidget(param);
            } else if (typeLower === 'combo') {
                this.createComboWidget(param);
            } else {
                this.createDefaultWidget(param);
            }
        });

        // Auto-resize node if it has a textarea widget
        if (params.some((p: any) => p.type === 'textarea')) {
            (this.node as any).size[1] = 120; // Default height for nodes with a textarea
        }
    }

    private createTextWidget(param: any) {
        const isSecret = param.name.toLowerCase().includes('key') || param.name.toLowerCase().includes('password');
        const displayValue = isSecret ? (param.default ? '********' : 'Not set') : param.default;
        const initialLabel = `${param.name}: ${displayValue}`;
        const widget = this.node.addWidget('button', initialLabel, param.default, () => {
            this.showCustomPrompt('Value', this.node.properties[param.name], isSecret, (newVal: string | null) => {
                if (newVal !== null) {
                    this.node.properties[param.name] = newVal;
                    const shown = isSecret ? (newVal ? '********' : 'Not set') : (typeof newVal === 'string' ? (newVal.substring(0, 15) + (newVal.length > 15 ? '...' : '')) : String(newVal));
                    widget.name = `${param.name}: ${shown}`;
                }
            });
        }, {});
        (widget as any).paramName = param.name;
    }

    private createTextareaWidget(param: any) {
        const widget = this.node.addWidget('text', param.name, param.default, (v) => {
            this.node.properties[param.name] = v;
        }, { multiline: true });
        (widget as any).paramName = param.name;
    }

    private createNumberWidget(param: any) {
        const isInteger = (String(param.type || '').toLowerCase() === 'integer' || String(param.type || '').toLowerCase() === 'int');
        const stepFromParam = (typeof param.step === 'number' && Number.isFinite(param.step)) ? param.step : (isInteger ? 1 : 0.1);
        const precisionFromParam = (typeof param.precision === 'number' && Number.isFinite(param.precision)) ? param.precision : (isInteger ? 0 : (stepFromParam < 1 ? 2 : 0));
        const opts = {
            min: (typeof param.min === 'number') ? param.min : undefined,
            max: (typeof param.max === 'number') ? param.max : undefined,
            step: stepFromParam,
            precision: precisionFromParam,
        };
        const widget = this.node.addWidget('number', param.name, param.default, (v) => {
            let final = v;
            if (isInteger) {
                const n = Number(v);
                final = Number.isFinite(n) ? Math.round(n) : this.node.properties[param.name];
            }
            this.node.properties[param.name] = final;
            widget.value = final;
            this.node.setDirtyCanvas(true, true);
        }, opts);
        widget.value = this.node.properties[param.name];
        (widget as any).paramName = param.name;
    }

    private createComboWidget(param: any) {
        const initialOptions = param.options || [];
        const widget = this.node.addWidget('button', `${param.name}: ${this.formatComboValue(this.node.properties[param.name])}`, '', () => {
            const dynamicValues = (widget as any).options?.values;
            const opts: any[] = Array.isArray(dynamicValues) && dynamicValues.length >= 0 ? dynamicValues : initialOptions;
            this.showCustomDropdown(param.name, opts, (selectedValue: any) => {
                this.node.properties[param.name] = selectedValue;
                widget.name = `${param.name}: ${this.formatComboValue(selectedValue)}`;
                this.node.setDirtyCanvas(true, true);
            });
        }, {});
        (widget as any).options = { values: initialOptions };
        (widget as any).paramName = param.name;
    }

    private createDefaultWidget(param: any) {
        const widget = this.node.addWidget('text', param.name, param.default, (v) => {
            this.node.properties[param.name] = v;
        }, {});
        (widget as any).paramName = param.name;
    }

    syncWidgetValues() {
        if (!(this.node as any).widgets) return;
        (this.node as any).widgets.forEach((widget: any) => {
            const explicitName = (widget as any).paramName;
            const parsedFromLabel = (widget && widget.options && typeof widget.name === 'string') ? widget.name.split(':')[0].trim() : widget?.name;
            const paramKey = explicitName || parsedFromLabel;

            if (!paramKey) return;

            if ((widget.type === 'number' || widget.type === 'combo' || widget.type === 'text' || widget.type === 'button') && Object.prototype.hasOwnProperty.call(this.node.properties, paramKey)) {
                if (widget.type === 'button' && widget.options?.values) {
                    // Combo button: update label only below
                } else {
                    widget.value = this.node.properties[paramKey];
                }
            }

            if (widget.options?.values && Object.prototype.hasOwnProperty.call(this.node.properties, paramKey)) {
                const leftLabel = (typeof widget.name === 'string' && widget.name.includes(':')) ? widget.name.split(':')[0] : String(paramKey);
                widget.name = `${leftLabel}: ${this.formatComboValue(this.node.properties[paramKey])}`;
            }
        });
    }



    private showCustomPrompt(title: string, defaultValue: string, isPassword: boolean, callback: (value: string | null) => void) {
        const dialogManager = (window as any).dialogManager;
        if (dialogManager) {
            dialogManager.showCustomPrompt(title, defaultValue, isPassword, callback);
        } else {
            // Fallback to simple prompt
            const value = prompt(title, defaultValue);
            callback(value);
        }
    }

    private showQuickValuePrompt(labelText: string, defaultValue: string | number, numericOnly: boolean, callback: (value: string | null) => void, position?: { x: number; y: number }) {
        const dialogManager = (window as any).dialogManager;
        if (dialogManager) {
            dialogManager.showQuickValuePrompt(labelText, defaultValue, numericOnly, callback, position);
        } else {
            // Fallback to simple prompt
            const value = prompt(labelText, String(defaultValue));
            callback(value);
        }
    }

    formatComboValue(value: any): string {
        if (typeof value === 'boolean') {
            return value ? 'true' : 'false';
        }
        return String(value);
    }

    private showCustomDropdown(paramName: string, options: any[], callback: (value: any) => void) {
        const dialogManager = (window as any).dialogManager;
        if (dialogManager) {
            dialogManager.showCustomDropdown(paramName, options, callback);
        } else {
            // Fallback to simple select
            const value = prompt(`Select ${paramName}:`, options.join(', '));
            if (value && options.includes(value)) {
                callback(value);
            }
        }
    }
}
