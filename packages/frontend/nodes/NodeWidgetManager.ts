import { LGraphNode, LiteGraph } from '@fig-node/litegraph';
import { NodeProperty } from '@fig-node/litegraph/dist/LGraphNode';
import { Dictionary } from '@fig-node/litegraph/dist/interfaces';
import { ServiceRegistry } from '../services/ServiceRegistry';

export class NodeWidgetManager {
    private node: LGraphNode & { properties: Dictionary<NodeProperty | undefined> };
    private serviceRegistry: ServiceRegistry;

    constructor(node: LGraphNode & { properties: Dictionary<NodeProperty | undefined> }, serviceRegistry: ServiceRegistry) {
        this.node = node;
        this.serviceRegistry = serviceRegistry;
    }

    createWidgetsFromParams(params: Array<{ name: string; type?: string; default?: unknown; options?: unknown[]; min?: number; max?: number; step?: number; precision?: number }>) {
        params.forEach((param) => {
            let paramType = param.type;
            if (!paramType) {
                paramType = this.determineParamType(param.name);
            }
            const defaultValue = param.default !== undefined ? param.default : this.getDefaultValue(param.name);
            this.node.properties[param.name] = defaultValue as NodeProperty | undefined;

            const typeLower = String(paramType || '').toLowerCase();

            if (typeLower === 'text' || typeLower === 'string') {
                this.createTextWidget(param);
            } else if (typeLower === 'textarea') {
                this.createTextareaWidget(param);
            } else if (typeLower === 'number' || typeLower === 'integer' || typeLower === 'int' || typeLower === 'float') {
                this.createNumberWidget(param);
            } else if (typeLower === 'combo') {
                this.createComboWidget(param);
            } else if (typeLower === 'fileupload') {
                this.createFileUploadWidget(param);
            } else {
                this.createDefaultWidget(param);
            }
        });

        // Auto-resize node if it has a textarea widget
        if (params.some((p) => p.type === 'textarea')) {
            (this.node as { size: [number, number] }).size[1] = 120; // Default height for nodes with a textarea
        }
    }

    private createTextWidget(param: { name: string; default?: unknown }) {
        const isSecret = param.name.toLowerCase().includes('key') || param.name.toLowerCase().includes('password');
        const displayValue = isSecret ? (param.default ? '********' : 'Not set') : param.default;
        const initialLabel = `${param.name}: ${displayValue}`;
        const widget = this.node.addWidget('button', initialLabel, param.default as string | undefined, () => {
            const currentValue = this.node.properties[param.name];
            this.showCustomPrompt('Value', typeof currentValue === 'string' ? currentValue : String(currentValue || ''), isSecret, (newVal: string | null) => {
                if (newVal !== null) {
                    this.node.properties[param.name] = newVal;
                    const shown = isSecret ? (newVal ? '********' : 'Not set') : (typeof newVal === 'string' ? (newVal.substring(0, 15) + (newVal.length > 15 ? '...' : '')) : String(newVal));
                    widget.name = `${param.name}: ${shown}`;
                }
            });
        }, {});
        (widget as unknown as { paramName: string }).paramName = param.name;
    }

    private createTextareaWidget(param: { name: string; default?: unknown }) {
        const widget = this.node.addWidget('text', param.name, param.default as string, (v: unknown) => {
            this.node.properties[param.name] = v as NodeProperty | undefined;
        }, { multiline: true });
        (widget as unknown as { paramName: string }).paramName = param.name;
    }

    private createNumberWidget(param: { name: string; type?: string; default?: unknown; min?: number; max?: number; step?: number; precision?: number }) {
        const isInteger = (String(param.type || '').toLowerCase() === 'integer' || String(param.type || '').toLowerCase() === 'int');
        const stepFromParam = (typeof param.step === 'number' && Number.isFinite(param.step)) ? param.step : (isInteger ? 1 : 0.1);
        const precisionFromParam = (typeof param.precision === 'number' && Number.isFinite(param.precision)) ? param.precision : (isInteger ? 0 : (stepFromParam < 1 ? 2 : 0));
        const opts: any = {};
        if (typeof param.min === 'number') opts.min = param.min;
        if (typeof param.max === 'number') opts.max = param.max;
        opts.step = stepFromParam;
        opts.precision = precisionFromParam;
        const widget = this.node.addWidget('number', param.name, param.default as number, (v: unknown) => {
            let final = v;
            if (isInteger) {
                const n = Number(v);
                final = Number.isFinite(n) ? Math.round(n) : this.node.properties[param.name];
            }
            this.node.properties[param.name] = final as NodeProperty | undefined;
            widget.value = final as number;
            this.node.setDirtyCanvas(true, true);
        }, opts);
        widget.value = this.node.properties[param.name] as number;
        (widget as unknown as { paramName: string }).paramName = param.name;
    }

    private createComboWidget(param: { name: string; options?: unknown[] }) {
        const initialOptions = param.options || [];
        const widget = this.node.addWidget('button', `${param.name}: ${this.formatComboValue(this.node.properties[param.name])}`, '', () => {
            const dynamicValues = (widget as { options?: { values?: unknown[] } }).options?.values;
            const opts: unknown[] = Array.isArray(dynamicValues) && dynamicValues.length >= 0 ? dynamicValues : initialOptions;
            this.showCustomDropdown(param.name, opts, (selectedValue: unknown) => {
                this.node.properties[param.name] = selectedValue as NodeProperty | undefined;
                widget.name = `${param.name}: ${this.formatComboValue(selectedValue)}`;
                this.node.setDirtyCanvas(true, true);
            });
        }, {});
        (widget as unknown as { options: { values: unknown[] }; paramName: string }).options = { values: initialOptions };
        (widget as unknown as { options: { values: unknown[] }; paramName: string }).paramName = param.name;
    }

    private createFileUploadWidget(param: { name: string; default?: unknown; options?: unknown }) {
        const options = param.options as { accept?: string; maxSize?: number } | undefined;
        const accept = options?.accept ?? '.txt,.md,.json';

        const widget = this.node.addWidget('button', `${param.name}: Select file`, '', () => {
            const input = document.createElement('input');
            input.type = 'file';
            input.accept = accept;
            input.onchange = () => {
                const file = input.files?.[0];
                if (!file) return;

                // Check file size if maxSize is specified
                if (options?.maxSize && file.size > options.maxSize) {
                    console.warn(`File size ${file.size} exceeds max size ${options.maxSize}`);
                    return;
                }

                const reader = new FileReader();
                reader.onload = () => {
                    this.node.properties[param.name] = reader.result as string;
                    widget.name = `${param.name}: ${file.name}`;
                    this.node.setDirtyCanvas(true, true);
                };
                reader.readAsText(file);
            };
            input.click();
        }, {});
        (widget as unknown as { paramName: string }).paramName = param.name;
    }

    private createDefaultWidget(param: { name: string; default?: unknown }) {
        const widget = this.node.addWidget('text', param.name, param.default as string, (v: unknown) => {
            this.node.properties[param.name] = v as NodeProperty | undefined;
        }, {});
        (widget as unknown as { paramName: string }).paramName = param.name;
    }

    syncWidgetValues() {
        const nodeWithWidgets = this.node as { widgets?: Array<{ type: string; name: string; value: unknown; options?: { values?: unknown[] }; paramName?: string }> };
        if (!nodeWithWidgets.widgets) return;
        nodeWithWidgets.widgets.forEach((widget) => {
            const key = widget.paramName;
            if (!key) return;

            if ((widget.type === 'number' || widget.type === 'text' || widget.type === 'button') && Object.prototype.hasOwnProperty.call(this.node.properties, key)) {
                if (widget.type === 'button' && widget.options?.values) {
                    // combo-style button: do not overwrite value, only label below
                } else {
                    widget.value = this.node.properties[key];
                }
            }

            if (widget.options?.values && Object.prototype.hasOwnProperty.call(this.node.properties, key)) {
                const left = (typeof widget.name === 'string' && widget.name.includes(':')) ? widget.name.split(':')[0] : String(key);
                widget.name = `${left}: ${this.formatComboValue(this.node.properties[key])}`;
            }
        });
    }

    // Helpers for paramName-based widget operations
    findWidgetByParamName(paramName: string) {
        const nodeWithWidgets = this.node as { widgets?: Array<{ paramName?: string }> };
        return (nodeWithWidgets.widgets || []).find(w => (w as any).paramName === paramName);
    }

    setComboValues(paramName: string, values: unknown[]) {
        const w = this.findWidgetByParamName(paramName) as any;
        if (!w) return;
        w.options = w.options || {};
        w.options.values = Array.isArray(values) ? values : [];
        this.node.setDirtyCanvas(true, true);
    }

    setWidgetLabel(paramName: string, label: string) {
        const w = this.findWidgetByParamName(paramName) as any;
        if (!w) return;
        w.name = label;
        this.node.setDirtyCanvas(true, true);
    }



    private showCustomPrompt(title: string, defaultValue: string, isPassword: boolean, callback: (value: string | null) => void) {
        const dialogManager = this.serviceRegistry.get('dialogManager');
        if (dialogManager && typeof dialogManager.showPrompt === 'function') {
            dialogManager.showPrompt(title, defaultValue, isPassword, callback);
        } else {
            // Fallback to simple prompt
            const value = prompt(title, defaultValue);
            callback(value);
        }
    }


    formatComboValue(value: unknown): string {
        if (typeof value === 'boolean') {
            return value ? 'true' : 'false';
        }
        return String(value);
    }

    /** Get a sensible default value based on param name */
    private getDefaultValue(name: string): unknown {
        const lower = name.toLowerCase();
        if (lower.includes('days') || lower.includes('period')) return 14;
        if (lower.includes('bool')) return true;
        return '';
    }

    /** Determine widget type from param name */
    private determineParamType(name: string): string {
        const lower = name.toLowerCase();
        if (lower.includes('period') || lower.includes('days')) return 'number';
        return 'text';
    }

    private showCustomDropdown(paramName: string, options: unknown[], callback: (value: unknown) => void) {
        const dialogManager = this.serviceRegistry.get('dialogManager');
        if (dialogManager && typeof dialogManager.showCustomDropdown === 'function') {
            // Calculate widget position for dropdown placement
            const widgetPosition = this.calculateWidgetPosition(paramName);
            dialogManager.showCustomDropdown(paramName, options, callback, widgetPosition || undefined);
        } else {
            // Fallback to simple select
            const value = prompt(`Select ${paramName}:`, options.map(String).join(', '));
            if (value && options.includes(value)) {
                callback(value);
            }
        }
    }

    private calculateWidgetPosition(paramName: string): { x: number; y: number } | null {
        const canvas = this.serviceRegistry.get('canvas');
        if (!canvas?.canvas) {
            return null;
        }

        const canvasRect = canvas.canvas.getBoundingClientRect();
        const scale = canvas.ds?.scale || 1;
        const offset = canvas.ds?.offset || [0, 0];

        // Find the widget that triggered this dropdown
        const nodeWithWidgets = this.node as { widgets?: Array<{ paramName?: string }>; pos: [number, number] };
        const widgets = nodeWithWidgets.widgets || [];
        const widgetIndex = widgets.findIndex((w) => w.paramName === paramName);
        if (widgetIndex === -1) {
            return null;
        }

        // Calculate widget position in screen coordinates
        const widgetY = nodeWithWidgets.pos[1] + LiteGraph.NODE_TITLE_HEIGHT + (widgetIndex * LiteGraph.NODE_WIDGET_HEIGHT);
        const widgetScreenX = canvasRect.left + (nodeWithWidgets.pos[0] + offset[0]) * scale;
        const widgetScreenY = canvasRect.top + (widgetY + offset[1]) * scale;

        return { x: widgetScreenX, y: widgetScreenY };
    }
}
