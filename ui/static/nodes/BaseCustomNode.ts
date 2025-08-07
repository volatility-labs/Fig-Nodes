import { LGraphNode, LiteGraph } from '@comfyorg/litegraph';

export default class BaseCustomNode extends LGraphNode {
    displayResults: boolean = true;
    result: any;
    displayText: string = '';
    properties: { [key: string]: any } = {};

    constructor(title: string, data: any) {
        super(title);
        this.size = [200, 100];

        if (data.inputs) {
            let inputNames = Array.isArray(data.inputs) ? data.inputs : Object.keys(data.inputs);
            inputNames.forEach((inp: string) => {
                const inputType = this.inferInputType(inp);
                this.addInput(inp, inputType);
            });
        }

        if (data.outputs) {
            let outputNames = Array.isArray(data.outputs) ? data.outputs : Object.keys(data.outputs);
            outputNames.forEach((out: string) => {
                const outputType = this.inferOutputType(out);
                this.addOutput(out, outputType);
            });
        }

        this.properties = {};

        if (data.params) {
            data.params.forEach((param: string) => {
                this.addParameterWidget(param);
                this.properties[param] = this.getDefaultValue(param);
            });
        }

        this.displayResults = data.category !== 'data_source';
    }

    inferInputType(inputName: string): string {
        const lowerName = inputName.toLowerCase();
        if (lowerName.includes('symbol')) return 'AssetSymbol';
        if (lowerName.includes('data')) return 'data';
        return 'any';
    }

    inferOutputType(outputName: string): string {
        const lowerName = outputName.toLowerCase();
        if (lowerName.includes('symbols')) return 'AssetSymbolList';
        if (lowerName.includes('result')) return 'result';
        return 'any';
    }

    getDefaultValue(param: string): any {
        const lowerParam = param.toLowerCase();
        if (lowerParam.includes('days') || lowerParam.includes('period')) return 14;
        if (lowerParam.includes('bool')) return true;
        return '';
    }

    addParameterWidget(param: string) {
        const paramLower = param.toLowerCase();
        if (paramLower.includes('period') || paramLower.includes('days')) {
            this.addWidget('number', param, this.properties[param] || 14, (v) => this.properties[param] = v);
        } else {
            this.addWidget('text', param, this.properties[param] || '', (v) => this.properties[param] = v);
        }
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