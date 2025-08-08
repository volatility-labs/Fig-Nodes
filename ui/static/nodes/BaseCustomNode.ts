import { LGraphNode, LiteGraph } from '@comfyorg/litegraph';
import { getTypeColor } from '../types';

export default class BaseCustomNode extends LGraphNode {
    displayResults: boolean = true;
    result: any;
    displayText: string = '';
    properties: { [key: string]: any } = {};

    constructor(title: string, data: any) {
        super(title);
        this.size = [200, 100];

        if (data.inputs) {
            const isArray = Array.isArray(data.inputs);
            // For inputs map
            const inputEntries = isArray ? data.inputs.map((name: string) => [name, null]) : Object.entries(data.inputs);
            inputEntries.forEach(([inp, typeInfo]: [string, any], index: number) => {
                const typeStr = this.parseType(typeInfo);
                this.addInput(inp, typeStr);
                if (typeInfo) {
                    const color = getTypeColor(typeInfo);
                    // @ts-ignore: Custom color property
                    this.inputs[index].color = color;  // Set color on input slot
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
                    // Single-line values via popup prompt (ideal for secrets like API keys)
                    const initialLabel = `${param.name}: ${defaultValue}`;
                    const widget = this.addWidget('button', initialLabel, defaultValue, () => {
                        const newVal = prompt(`Enter value for ${param.name}`, this.properties[param.name]);
                        if (newVal !== null) {
                            this.properties[param.name] = newVal;
                            widget.name = `${param.name}: ${newVal}`;
                        }
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
        if (!typeInfo || typeInfo.base === 'Any' || typeInfo.base === 'typing.Any') {
            return 0; // LiteGraph wildcard for "accept any"
        }
        let type = typeInfo.base;
        if (typeInfo.subtype) {
            const sub = this.parseType(typeInfo.subtype);
            if (type === 'list' && sub === 'AssetSymbol') return 'AssetSymbolList';
            // Add more mappings as needed for extensibility
            return `${type}<${sub}>`;
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

    onDrawForeground(ctx: CanvasRenderingContext2D) {
        if (this.flags.collapsed || !this.displayResults || !this.displayText) {
            return;
        }
        let y = LiteGraph.NODE_TITLE_HEIGHT + 4;
        if (this.widgets) {
            y += this.widgets.length * LiteGraph.NODE_WIDGET_HEIGHT;
        }
        y += 10;
        ctx.font = '12px Arial';
        ctx.fillStyle = '#ffffff';
        ctx.textAlign = 'left';
        const lines = this.wrapText(this.displayText, this.size[0] - 20, ctx);
        lines.forEach(line => {
            ctx.fillText(line, 10, y);
            y += 15;
        });
    }
}