import { LGraphNode, LiteGraph } from '@comfyorg/litegraph';
import { getTypeColor } from '../types';
import { showError } from '../utils/uiUtils';

// Reinstate module augmentation at top:
declare module '@comfyorg/litegraph' {
    interface INodeInputSlot {
        color?: string;
    }
}

export default class BaseCustomNode extends LGraphNode {
    displayResults: boolean = true;
    result: any;
    displayText: string = '';
    properties: { [key: string]: any } = {};
    error: string = '';
    private highlightStartTs: number | null = null;
    private readonly highlightDurationMs: number = 900;

    constructor(title: string, data: any) {
        super(title);
        this.size = [200, 100];

        if (data.inputs) {
            const isArray = Array.isArray(data.inputs);
            // For inputs map
            const inputEntries = isArray ? data.inputs.map((name: string) => [name, null]) : Object.entries(data.inputs);
            inputEntries.forEach(([inp, typeInfo]: [string, any]) => {
                const typeStr = this.parseType(typeInfo);
                let color;
                if (typeInfo) {
                    color = getTypeColor(typeInfo);
                }
                const typeStrLower = typeof typeStr === 'string' ? typeStr.toLowerCase() : '';
                if (typeof typeStr === 'string' && (typeStrLower.startsWith('list<') || typeStrLower.startsWith('dict<')) && typeInfo) {
                    const inputSlot = this.addInput(inp, typeStr);
                    if (color) inputSlot.color = color;
                } else {
                    const inputSlot = this.addInput(inp, typeStr);
                    if (color) {
                        // @ts-ignore: Custom color property
                        inputSlot.color = color;
                    }
                }
            });
        }

        if (data.outputs) {
            const isArray = Array.isArray(data.outputs);
            // For outputs map
            const outputEntries = isArray ? data.outputs.map((name: string) => [name, null]) : Object.entries(data.outputs);
            outputEntries.forEach(([out, typeInfo]: [string, any], index: number) => {
                const typeStr = this.parseType(typeInfo);
                this.addOutput(out, typeStr);
                if (typeInfo) {
                    const color = getTypeColor(typeInfo);
                    // @ts-ignore: Custom color property
                    this.outputs[index].color = color;  // Set color on output slot
                }
            });
        }

        this.properties = {};

        // Set defaults for all params regardless of UI type
        if (data.params) {
            data.params.forEach((param: any) => {
                let paramType = param.type;
                if (!paramType) {
                    paramType = this.determineParamType(param.name);
                }
                const defaultValue = param.default !== undefined ? param.default : this.getDefaultValue(param.name);
                this.properties[param.name] = defaultValue;
            });
        }

        // Only auto-add generic widgets if no custom UI module
        if (data.params) {
            data.params.forEach((param: any) => {
                let paramType = param.type;
                if (!paramType) {
                    paramType = this.determineParamType(param.name);
                }
                const defaultValue = param.default !== undefined ? param.default : this.getDefaultValue(param.name);
                this.properties[param.name] = defaultValue;

                if (paramType === 'text') {
                    const isSecret = param.name.toLowerCase().includes('key') || param.name.toLowerCase().includes('password');
                    let displayValue = isSecret ? (defaultValue ? '********' : 'Not set') : defaultValue;
                    const initialLabel = `${param.name}: ${displayValue}`;
                    const widget = this.addWidget('button', initialLabel, defaultValue, () => {
                        this.showCustomPrompt('Value', this.properties[param.name], isSecret, (newVal: string | null) => {
                            if (newVal !== null) {
                                this.properties[param.name] = newVal;
                                displayValue = isSecret ? (newVal ? '********' : 'Not set') : newVal.substring(0, 15) + (newVal.length > 15 ? '...' : '');
                                widget.name = `${param.name}: ${displayValue}`;
                            }
                        });
                    }, {});
                } else if (paramType === 'textarea') {
                    // Multi-line input directly in the node UI (e.g., long prompts)
                    this.addWidget('text', param.name, defaultValue, (v) => {
                        this.properties[param.name] = v;
                    }, { multiline: true });
                } else if (paramType === 'number') {
                    const opts = { min: param.min ?? 0, max: param.max ?? undefined, step: param.step ?? 0.1, precision: param.precision ?? (param.step < 1 ? 2 : 0) };
                    const widget = this.addWidget('number', param.name, defaultValue, (v) => {
                        this.properties[param.name] = v;
                        widget.value = v;
                        this.setDirtyCanvas(true, true);
                    }, opts);
                    // Ensure widget value stays in sync with properties
                    widget.value = this.properties[param.name];
                } else if (paramType === 'combo') {
                    // Custom dropdown widget for combo parameters
                    const options = param.options || [];
                    const widget = this.addWidget('button', `${param.name}: ${this.formatComboValue(this.properties[param.name])}`, '', () => {
                        this.showCustomDropdown(param.name, options, (selectedValue: any) => {
                            this.properties[param.name] = selectedValue;
                            widget.name = `${param.name}: ${this.formatComboValue(selectedValue)}`;
                            this.setDirtyCanvas(true, true);
                        });
                    }, {});
                    // Store options for later use
                    (widget as any).options = options;
                } else {
                    let widgetOpts = {};
                    let isBooleanCombo = false;
                    let originalOptions = param.options || [];
                    let displayValues = originalOptions;
                    if (paramType === 'combo' && originalOptions.length === 2 && typeof originalOptions[0] === 'boolean' && typeof originalOptions[1] === 'boolean') {
                        isBooleanCombo = true;
                        displayValues = originalOptions.map((b: boolean) => b ? 'true' : 'false');
                    }
                    widgetOpts = { values: displayValues };
                    const widget = this.addWidget(paramType as any, param.name, this.properties[param.name], (v: any) => {
                        let finalV = v;
                        if (isBooleanCombo) {
                            finalV = v === 'true';
                        }
                        this.properties[param.name] = finalV;
                        widget.value = isBooleanCombo ? (finalV ? 'true' : 'false') : finalV;
                        this.setDirtyCanvas(true, true);
                    }, widgetOpts);
                    // Ensure widget value stays in sync with properties
                    widget.value = isBooleanCombo ? (this.properties[param.name] ? 'true' : 'false') : this.properties[param.name];
                }
            });
        }

        this.displayResults = false;

        // Auto-resize node if it has a textarea widget
        if (data.params && data.params.some((p: any) => p.type === 'textarea')) {
            this.size[1] = 120; // Default height for nodes with a textarea
        }
    }

    parseType(typeInfo: any): string | number {
        if (!typeInfo) {
            return 0; // LiteGraph wildcard for "accept any"
        }
        const baseName = typeof typeInfo.base === 'string' ? typeInfo.base : String(typeInfo.base);
        if (baseName === 'Any' || baseName === 'typing.Any' || baseName.toLowerCase() === 'any') {
            return 0; // LiteGraph wildcard
        }
        let type = baseName;
        if (typeInfo.subtype) {
            const sub = this.parseType(typeInfo.subtype);
            return `${type}<${sub}>`;
        } else if (typeInfo.subtypes && typeInfo.subtypes.length > 0) {
            const subs = typeInfo.subtypes.map((st: any) => this.parseType(st)).join(', ');
            return `${type}<${subs}>`;
        } else if (typeInfo.key_type && typeInfo.value_type) {
            const key = this.parseType(typeInfo.key_type);
            const val = this.parseType(typeInfo.value_type);
            return `dict<${key}, ${val}>`;
        }
        return type;
    }

    getDefaultValue(param: string): any {
        const lowerParam = param.toLowerCase();
        if (lowerParam.includes('days') || lowerParam.includes('period')) return 14;
        if (lowerParam.includes('bool')) return true;
        return '';
    }

    determineParamType(name: string): string {
        const lower = name.toLowerCase();
        if (lower.includes('period') || lower.includes('days')) return 'number';
        return 'text';
    }

    wrapText(text: string, maxWidth: number, ctx: CanvasRenderingContext2D): string[] {
        if (typeof text !== 'string') return [];
        const lines: string[] = [];
        const paragraphs = text.split('\n');
        for (let p of paragraphs) {
            const words = p.split(' ');
            let currentLine = words[0] || '';
            for (let i = 1; i < words.length; i++) {
                const word = words[i];
                const width = ctx.measureText(currentLine + ' ' + word).width;
                if (width < maxWidth) {
                    currentLine += ' ' + word;
                } else {
                    lines.push(currentLine);
                    currentLine = word;
                }
            }
            if (currentLine) lines.push(currentLine);
        }
        return lines;
    }

    setError(message: string) {
        this.error = message;
        this.color = '#FF0000'; // Red border for error
        this.setDirtyCanvas(true, true);
        showError(message);
    }

    onDrawForeground(ctx: CanvasRenderingContext2D) {
        // Pulse highlight outline to indicate recent execution
        if (this.highlightStartTs !== null) {
            const now = performance.now();
            const elapsed = now - this.highlightStartTs;
            if (elapsed < this.highlightDurationMs) {
                const t = 1 - (elapsed / this.highlightDurationMs);
                const alpha = 0.25 + 0.55 * t;
                const glow = Math.floor(6 * t) + 2;
                ctx.save();
                ctx.strokeStyle = `rgba(33, 150, 243, ${alpha.toFixed(3)})`;
                ctx.lineWidth = 2;
                // Outer glow
                (ctx as any).shadowColor = `rgba(33, 150, 243, ${Math.min(0.8, 0.2 + 0.6 * t).toFixed(3)})`;
                (ctx as any).shadowBlur = glow;
                ctx.strokeRect(1, 1, this.size[0] - 2, this.size[1] - 2);
                ctx.restore();
                this.setDirtyCanvas(true, true);
            } else {
                this.highlightStartTs = null;
            }
        }

        if (this.flags.collapsed || !this.displayResults || !this.displayText) {
            return;
        }

        const maxWidth = this.size[0] - 20;

        // Create temporary canvas context for measurement
        const tempCanvas = document.createElement('canvas');
        const tempCtx = tempCanvas.getContext('2d');
        if (!tempCtx) return;

        tempCtx.font = '12px Arial';
        const lines = this.wrapText(this.displayText, maxWidth, tempCtx);

        // Calculate needed height
        let y = LiteGraph.NODE_TITLE_HEIGHT + 4;
        if (this.widgets) {
            y += this.widgets.length * LiteGraph.NODE_WIDGET_HEIGHT;
        }
        y += 10;
        const contentHeight = lines.length * 15;
        const neededHeight = y + contentHeight + 10;

        // Resize if necessary
        if (Math.abs(this.size[1] - neededHeight) > 1) {
            this.size[1] = neededHeight;
            this.setDirtyCanvas(true, true);
            return; // Skip drawing this frame to avoid flicker
        }

        // Draw the text
        ctx.font = '12px Arial';
        ctx.fillStyle = '#ffffff';
        ctx.textAlign = 'left';

        lines.forEach((line, index) => {
            ctx.fillText(line, 10, y + index * 15);
        });

        // Draw error if present
        if (this.error) {
            ctx.fillStyle = '#FF0000';
            ctx.font = 'bold 12px Arial';
            const errorY = y + lines.length * 15 + 10;
            ctx.fillText(`Error: ${this.error}`, 10, errorY);
            this.size[1] = Math.max(this.size[1], errorY + 20);
        }
    }

    updateDisplay(result: any) {
        this.result = result;
        if (this.displayResults) {
            const outputs = Object.values(result);
            const primaryOutput = outputs.length === 1 ? outputs[0] : result;
            this.displayText = typeof primaryOutput === 'string' ? primaryOutput : JSON.stringify(primaryOutput, null, 2);
        }
        this.setDirtyCanvas(true, true);
    }

    pulseHighlight() {
        this.highlightStartTs = performance.now();
        this.setDirtyCanvas(true, true);
    }

    showCustomPrompt(title: string, defaultValue: string, isPassword: boolean, callback: (value: string | null) => void) {
        // Backward-compatible: route to compact quick input if not password
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

    // Small ComfyUI-style quick input popup for values like seed
    showQuickValuePrompt(labelText: string, defaultValue: string | number, numericOnly: boolean, callback: (value: string | null) => void, position?: { x: number; y: number }) {
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
                    return; // ignore invalid
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

        // Prefer to use canvas-global prompt if it has been overridden in app.ts
        try {
            const graph: any = (this as any).graph;
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

        // Positioning: center by default, otherwise near provided coordinates
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

    onDblClick(_event: MouseEvent, pos: [number, number], _canvas: any): boolean {
        // Hit-test precisely on the title TEXT bounds
        const bounds = this.getTitleTextBounds();
        if (!bounds) return false;
        const [x, y] = pos;
        const within = x >= bounds.x && x <= bounds.x + bounds.width && y >= bounds.y && y <= bounds.y + bounds.height;
        if (within) {
            this.startTitleEdit();
            return true;
        }
        return false;
    }

    startTitleEdit() {
        const titleElement = document.createElement('input');
        titleElement.className = 'inline-title-input';
        titleElement.value = this.title;
        titleElement.style.position = 'absolute';
        titleElement.style.left = `${this.pos[0] + 10}px`; // Small margin from left
        titleElement.style.top = `${this.pos[1] + 8}px`; // Small margin from top
        titleElement.style.width = `${this.size[0] - 20}px`; // Account for margins
        titleElement.style.zIndex = '3000';

        const finishEdit = (save: boolean) => {
            if (save && titleElement.value.trim()) {
                this.title = titleElement.value.trim();
            }
            if (titleElement.parentNode) {
                document.body.removeChild(titleElement);
            }
            this.setDirtyCanvas(true, true);
        };

        titleElement.addEventListener('keydown', (e: KeyboardEvent) => {
            e.stopPropagation();
            if (e.key === 'Enter') {
                finishEdit(true);
            } else if (e.key === 'Escape') {
                finishEdit(false);
            }
        });

        titleElement.addEventListener('blur', () => {
            finishEdit(true);
        });

        document.body.appendChild(titleElement);
        titleElement.focus();
        titleElement.select();
    }

    private getTitleFontSize(): number {
        // Try to parse from this.titleFontStyle, fallback to LiteGraph default
        try {
            // titleFontStyle looks like "bold 18px Arial" or "16px Roboto"
            // pick the first number+px
            const style: any = (this as any).titleFontStyle || '';
            const m = String(style).match(/(\d+(?:\.\d+)?)px/);
            if (m) return Math.round(Number(m[1]));
        } catch { /* ignore */ }
        // Reasonable default matching LiteGraph.NODE_TEXT_SIZE if available
        try {
            const sizeConst: any = (LiteGraph as any).NODE_TEXT_SIZE;
            if (typeof sizeConst === 'number' && Number.isFinite(sizeConst)) return sizeConst;
        } catch { /* ignore */ }
        return 16;
    }

    private getTitleTextBounds(): { x: number; y: number; width: number; height: number } | null {
        // Local node coordinates: origin at (0, 0) is the bottom of the title bar
        // Title bar spans y in [-NODE_TITLE_HEIGHT, 0]
        const fontSize = this.getTitleFontSize();
        const padLeft = LiteGraph.NODE_TITLE_HEIGHT; // matches library padding used for icon/space
        const baselineY = -LiteGraph.NODE_TITLE_HEIGHT + (LiteGraph as any).NODE_TITLE_TEXT_Y;

        // Measure text width using offscreen canvas and node's font style
        const canvasEl = document.createElement('canvas');
        const ctx = canvasEl.getContext('2d');
        if (!ctx) return null;
        const fontStyle: any = (this as any).titleFontStyle || `${fontSize}px Arial`;
        ctx.font = String(fontStyle);
        const text = this.title ?? '';
        const textWidth = Math.ceil(ctx.measureText(text).width);

        const height = Math.ceil(fontSize + 6); // small vertical padding around text
        const yTop = Math.round(baselineY - fontSize * 0.85); // approx ascent region

        return { x: padLeft, y: yTop, width: Math.max(2, textWidth), height };
    }

    onConnectionsChange() { }

    configure(info: any) {
        super.configure(info);
        // Sync widget values with properties after configuration
        this.syncWidgetValues();
        this.setDirtyCanvas(true, true);
    }

    syncWidgetValues() {
        if (this.widgets) {
            this.widgets.forEach((widget: any) => {
                if (widget.name) {
                    if (widget.options) {
                        // Custom combo widget - update display name
                        const paramName = widget.name.split(':')[0].trim();
                        if (this.properties.hasOwnProperty(paramName)) {
                            widget.name = `${paramName}: ${this.formatComboValue(this.properties[paramName])}`;
                        }
                    } else if (widget.type === 'number' || widget.type === 'combo') {
                        if (this.properties.hasOwnProperty(widget.name)) {
                            widget.value = this.properties[widget.name];
                        }
                    }
                }
            });
        }
    }

    private formatComboValue(value: any): string {
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

        // Position the menu near the mouse cursor
        const graph = (this as any).graph;
        const canvas = graph?.list_of_graphcanvas?.[0];
        if (canvas && canvas.canvas) {
            const canvasRect = canvas.canvas.getBoundingClientRect();
            const lastMouseEvent = (canvas as any).getLastMouseEvent?.();

            if (lastMouseEvent) {
                // Position near mouse cursor with bounds checking
                let menuX = lastMouseEvent.clientX;
                let menuY = lastMouseEvent.clientY + 5;

                // Adjust if menu would go off-screen
                const menuWidth = 200; // Compact menu width
                const menuHeight = Math.min(150, options.length * 28 + 16); // Estimate height

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
                // Fallback to node position if no mouse event available
                const scale = canvas.ds?.scale || 1;
                const offset = canvas.ds?.offset || [0, 0];
                const screenX = canvasRect.left + (this.pos[0] + offset[0]) * scale;
                const screenY = canvasRect.top + (this.pos[1] + offset[1] + this.size[1]) * scale;
                menu.style.left = `${screenX}px`;
                menu.style.top = `${screenY + 5}px`;
                menu.style.width = '200px';
                menu.style.maxHeight = '150px';
            }
        }

        // Add options to menu
        options.forEach((option) => {
            const item = document.createElement('div');
            item.className = 'custom-dropdown-item';
            item.textContent = this.formatComboValue(option);

            // Highlight current selection
            if (option === this.properties[paramName]) {
                item.classList.add('selected');
            }

            item.addEventListener('click', () => {
                callback(option);
                document.body.removeChild(overlay);
            });

            menu.appendChild(item);
        });

        overlay.appendChild(menu);
        overlay.tabIndex = -1; // Make focusable
        document.body.appendChild(overlay);

        // Close on click outside
        overlay.addEventListener('click', (e) => {
            if (e.target === overlay) {
                document.body.removeChild(overlay);
            }
        });

        // Handle keyboard navigation
        let selectedIndex = options.findIndex(opt => opt === this.properties[paramName]);
        if (selectedIndex === -1) selectedIndex = 0;

        const updateSelection = () => {
            const items = menu.querySelectorAll('.custom-dropdown-item');
            items.forEach((item, i) => {
                if (i === selectedIndex) {
                    item.classList.add('selected');
                    // Only scroll if the method exists (not in test environment)
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

        // Focus the overlay for keyboard events
        overlay.focus();
    }
}