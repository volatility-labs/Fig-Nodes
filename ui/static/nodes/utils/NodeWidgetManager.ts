import { LGraphNode } from '@comfyorg/litegraph';

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
            min: (typeof param.min === 'number') ? param.min : 0,
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

    private formatComboValue(value: any): string {
        if (typeof value === 'boolean') {
            return value ? 'true' : 'false';
        }
        return String(value);
    }

    private showCustomPrompt(title: string, defaultValue: string, isPassword: boolean, callback: (value: string | null) => void) {
        if (!isPassword) {
            this.showQuickValuePrompt(title || 'Value', defaultValue, false, (val) => callback(val));
            return;
        }

        const dialog = document.createElement('div');
        dialog.className = 'custom-input-dialog';

        const label = document.createElement('label');
        label.className = 'dialog-label';
        label.textContent = title;

        const input = document.createElement('input');
        input.className = 'dialog-input';
        input.type = 'password';
        input.value = defaultValue;

        const okButton = document.createElement('button');
        okButton.className = 'dialog-button';
        okButton.textContent = 'OK';
        okButton.onclick = () => {
            callback(input.value);
            document.body.removeChild(dialog);
        };

        dialog.appendChild(label);
        dialog.appendChild(input);
        dialog.appendChild(okButton);

        document.body.appendChild(dialog);
        input.focus();
        input.select();
    }

    private showQuickValuePrompt(labelText: string, defaultValue: string | number, numericOnly: boolean, callback: (value: string | null) => void, position?: { x: number; y: number }) {
        const overlay = document.createElement('div');
        overlay.className = 'quick-input-overlay';

        const dialog = document.createElement('div');
        dialog.className = 'quick-input-dialog';

        const label = document.createElement('div');
        label.className = 'quick-input-label';
        label.textContent = labelText || 'Value';

        const input = document.createElement('input');
        input.className = 'quick-input-field';
        input.type = numericOnly ? 'number' : 'text';
        input.value = String(defaultValue ?? '');
        input.spellcheck = false;

        const okButton = document.createElement('button');
        okButton.className = 'quick-input-ok';
        okButton.textContent = 'OK';

        const submit = () => {
            if (numericOnly) {
                const n = Number(input.value);
                if (!Number.isFinite(n)) {
                    return;
                }
                callback(String(Math.floor(n)));
            } else {
                callback(input.value);
            }
            document.body.removeChild(overlay);
        };

        const cancel = () => {
            callback(null);
            if (overlay.parentNode) document.body.removeChild(overlay);
        };

        okButton.addEventListener('click', submit);
        input.addEventListener('keydown', (ev) => {
            ev.stopPropagation();
            if (ev.key === 'Enter') submit();
            if (ev.key === 'Escape') cancel();
        });
        overlay.addEventListener('click', (ev) => {
            if (ev.target === overlay) cancel();
        });

        dialog.appendChild(label);
        dialog.appendChild(input);
        dialog.appendChild(okButton);
        overlay.appendChild(dialog);
        document.body.appendChild(overlay);

        try {
            const graph: any = (this.node as any).graph;
            const canvas = graph?.list_of_graphcanvas?.[0];
            const prompt = (canvas && (canvas as any).prompt) || (window as any).LiteGraph?.prompt;
            if (typeof prompt === 'function') {
                document.body.removeChild(overlay);
                prompt(labelText, defaultValue, (val: any) => {
                    if (numericOnly && val != null) {
                        const n = Number(val);
                        if (!Number.isFinite(n)) { callback(null); return; }
                        callback(String(Math.floor(n)));
                    } else {
                        callback(val == null ? null : String(val));
                    }
                }, { type: numericOnly ? 'number' : 'text', step: 1, min: 0 });
                return;
            }
        } catch { /* fall back to inline */ }

        if (position && Number.isFinite(position.x) && Number.isFinite(position.y)) {
            dialog.style.position = 'absolute';
            dialog.style.left = `${position.x}px`;
            dialog.style.top = `${position.y}px`;
            overlay.style.background = 'transparent';
            (overlay.style as any).pointerEvents = 'none';
            (dialog.style as any).pointerEvents = 'auto';
        }

        input.focus();
        input.select();
    }

    formatComboValue(value: any): string {
        if (typeof value === 'boolean') {
            return value ? 'true' : 'false';
        }
        return String(value);
    }

    private showCustomDropdown(paramName: string, options: any[], callback: (value: any) => void) {
        const overlay = document.createElement('div');
        overlay.className = 'custom-dropdown-overlay';

        const menu = document.createElement('div');
        menu.className = 'custom-dropdown-menu';

        const graph = (this.node as any).graph;
        const canvas = graph?.list_of_graphcanvas?.[0];
        if (canvas && canvas.canvas) {
            const canvasRect = canvas.canvas.getBoundingClientRect();
            const lastMouseEvent = (canvas as any).getLastMouseEvent?.();

            if (lastMouseEvent) {
                let menuX = lastMouseEvent.clientX;
                let menuY = lastMouseEvent.clientY + 5;

                const menuWidth = 200;
                const menuHeight = Math.min(150, options.length * 28 + 16);

                if (menuX + menuWidth > window.innerWidth) {
                    menuX = window.innerWidth - menuWidth - 10;
                }
                if (menuY + menuHeight > window.innerHeight) {
                    menuY = lastMouseEvent.clientY - menuHeight - 5;
                }

                menu.style.left = `${menuX}px`;
                menu.style.top = `${menuY}px`;
                menu.style.width = `${menuWidth}px`;
                menu.style.maxHeight = `${menuHeight}px`;
            } else {
                const scale = canvas.ds?.scale || 1;
                const offset = canvas.ds?.offset || [0, 0];
                const screenX = canvasRect.left + (this.node.pos[0] + offset[0]) * scale;
                const screenY = canvasRect.top + (this.node.pos[1] + offset[1] + (this.node as any).size[1]) * scale;
                menu.style.left = `${screenX}px`;
                menu.style.top = `${screenY + 5}px`;
                menu.style.width = '200px';
                menu.style.maxHeight = '150px';
            }
        }

        options.forEach((option) => {
            const item = document.createElement('div');
            item.className = 'custom-dropdown-item';
            item.textContent = this.formatComboValue(option);

            if (option === this.node.properties[paramName]) {
                item.classList.add('selected');
            }

            item.addEventListener('click', () => {
                callback(option);
                document.body.removeChild(overlay);
            });

            menu.appendChild(item);
        });

        overlay.appendChild(menu);
        overlay.tabIndex = -1;
        document.body.appendChild(overlay);

        overlay.addEventListener('click', (e) => {
            if (e.target === overlay) {
                document.body.removeChild(overlay);
            }
        });

        let selectedIndex = options.findIndex(opt => opt === this.node.properties[paramName]);
        if (selectedIndex === -1) selectedIndex = 0;

        const updateSelection = () => {
            const items = menu.querySelectorAll('.custom-dropdown-item');
            items.forEach((item, i) => {
                if (i === selectedIndex) {
                    item.classList.add('selected');
                    if (typeof item.scrollIntoView === 'function') {
                        item.scrollIntoView({ block: 'nearest' });
                    }
                } else {
                    item.classList.remove('selected');
                }
            });
        };

        updateSelection();

        overlay.addEventListener('keydown', (e) => {
            e.preventDefault();
            e.stopPropagation();

            if (e.key === 'ArrowDown') {
                selectedIndex = (selectedIndex + 1) % options.length;
                updateSelection();
            } else if (e.key === 'ArrowUp') {
                selectedIndex = (selectedIndex - 1 + options.length) % options.length;
                updateSelection();
            } else if (e.key === 'Enter') {
                callback(options[selectedIndex]);
                document.body.removeChild(overlay);
            } else if (e.key === 'Escape') {
                document.body.removeChild(overlay);
            }
        });

        overlay.focus();
    }
}
