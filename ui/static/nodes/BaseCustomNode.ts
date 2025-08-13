import { LGraphNode, LiteGraph } from '@comfyorg/litegraph';
import { getTypeColor } from '../types';
import { showError } from '../utils/uiUtils';

export default class BaseCustomNode extends LGraphNode {
    displayResults: boolean = true;
    multiInputs?: Record<string, { slots: string[]; multiType: string; color?: string }>;
    result: any;
    displayText: string = '';
    properties: { [key: string]: any } = {};
    error: string = '';

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
                if (typeof typeStr === 'string' && typeStr.startsWith('list<') && typeInfo) {
                    const innerStr = typeStr.slice(5, -1);
                    const multiType = `${innerStr},${typeStr}`;
                    this.multiInputs = this.multiInputs || {};
                    this.multiInputs[inp] = { slots: [], multiType, color };
                    this.addMultiSlot(inp);
                } else if (typeof typeStr === 'string' && typeStr.startsWith('dict<') && typeInfo) {
                    const multiType = typeStr;
                    this.multiInputs = this.multiInputs || {};
                    this.multiInputs[inp] = { slots: [], multiType, color };
                    this.addMultiSlot(inp);
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
                } else {
                    const widgetOpts = paramType === 'combo' ? { values: param.options || [] } : {};
                    this.addWidget(paramType as any, param.name, this.properties[param.name], (v: any) => {
                        this.properties[param.name] = v;
                    }, widgetOpts);
                }
            });
        }

        this.displayResults = data.category !== 'data_source';

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

    showCustomPrompt(title: string, defaultValue: string, isPassword: boolean, callback: (value: string | null) => void) {
        const dialog = document.createElement('div');
        dialog.className = 'custom-input-dialog';

        const label = document.createElement('label');
        label.className = 'dialog-label';
        label.textContent = title;

        const input = document.createElement('input');
        input.className = 'dialog-input';
        input.type = isPassword ? 'password' : 'text';
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

    addMultiSlot(inp: string) {
        const info = this.multiInputs![inp];
        const index = info.slots.length;
        const slotName = `${inp}_${index}`;
        const inputSlot = this.addInput(slotName, info.multiType);
        if (info.color) {
            // @ts-ignore: Custom color property
            inputSlot.color = info.color;
        }
        info.slots.push(slotName);
    }

    onConnectionsChange(type: number, slot: number, connected: boolean, link_info: any, input_or_output: any) {
        if (type !== LiteGraph.INPUT) return;
        const input = this.inputs[slot];
        if (!input) return;
        const nameParts = input.name.split('_');
        if (nameParts.length !== 2 || isNaN(parseInt(nameParts[1]))) return;
        const baseName = nameParts[0];
        const info = this.multiInputs?.[baseName];
        if (!info) return;
        const slotIndex = parseInt(nameParts[1]);
        if (connected) {
            if (slotIndex === info.slots.length - 1) {
                this.addMultiSlot(baseName);
            }
        } else {
            if (slotIndex < info.slots.length - 1 && !input.link) {
                this.removeInput(slot);
                info.slots.splice(slotIndex, 1);
                for (let j = 0; j < info.slots.length; j++) {
                    const currentName = info.slots[j];
                    const newName = `${baseName}_${j}`;
                    if (currentName !== newName) {
                        const sIdx = this.findInputSlot(currentName);
                        if (sIdx !== -1) {
                            this.inputs[sIdx].name = newName;
                        }
                        info.slots[j] = newName;
                    }
                }
            }
        }
        this.setDirtyCanvas(true, true);
    }
}