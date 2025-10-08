import { LGraphNode } from '@comfyorg/litegraph';
import { getTypeColor } from '../../types';
import { showError } from '../../utils/uiUtils';
import { NodeTypeSystem } from '../utils/NodeTypeSystem';
import { NodeWidgetManager } from '../utils/NodeWidgetManager';
import { NodeRenderer } from '../utils/NodeRenderer';
import { NodeInteractions } from '../utils/NodeInteractions';

// Reinstate module augmentation at top:
declare module '@comfyorg/litegraph' {
    interface INodeInputSlot {
        color?: string;
        tooltip?: string;
    }
    interface INodeOutputSlot {
        color?: string;
        tooltip?: string;
    }
}

export default class BaseCustomNode extends LGraphNode {
    displayResults: boolean = true;
    result: any;
    displayText: string = '';
    properties: { [key: string]: any } = {};
    error: string = '';
    highlightStartTs: number | null = null;
    readonly highlightDurationMs: number = 900;
    // Local progress state in percent (0-100). We override LiteGraph's built-in
    // drawProgressBar so this field will not conflict with the library's
    // internal 0..1 progress property.
    progress: number = -1; // -1 = no progress, 0-100 = progress percentage
    progressText: string = '';

    // Modular components
    protected widgetManager: NodeWidgetManager;
    protected renderer: NodeRenderer;
    protected interactions: NodeInteractions;

    constructor(title: string, data: any) {
        super(title);
        this.size = [200, 100];

        // Initialize modular components
        this.widgetManager = new NodeWidgetManager(this);
        this.renderer = new NodeRenderer(this);
        this.interactions = new NodeInteractions(this);

        this.initializeNode(data);
    }

    private initializeNode(data: any) {
        // Setup inputs and outputs
        this.setupInputs(data.inputs);
        this.setupOutputs(data.outputs);

        // Setup properties and widgets
        this.setupProperties(data.params);
        if (data.params) {
            this.widgetManager.createWidgetsFromParams(data.params);
        }
    }

    private setupInputs(inputs: any) {
        if (!inputs) return;

        const isArray = Array.isArray(inputs);
        const inputEntries: Array<[string, any]> = isArray
            ? (inputs as string[]).map((name: string) => [name, null])
            : (Object.entries(inputs) as Array<[string, any]>);

        inputEntries.forEach(([inp, typeInfo]: [string, any]) => {
            const typeStr = NodeTypeSystem.parseType(typeInfo);
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
                    inputSlot.color = color;
                }
            }
        });
    }

    private setupOutputs(outputs: any) {
        if (!outputs) return;

        const isArray = Array.isArray(outputs);
        const outputEntries: Array<[string, any]> = isArray
            ? (outputs as string[]).map((name: string) => [name, null])
            : (Object.entries(outputs) as Array<[string, any]>);

        outputEntries.forEach(([out, typeInfo]: [string, any], index: number) => {
            const typeStr = NodeTypeSystem.parseType(typeInfo);
            this.addOutput(out, typeStr);
            if (typeInfo) {
                const color = getTypeColor(typeInfo);
                this.outputs[index].color = color;
            }
        });
    }

    private setupProperties(params: any[]) {
        if (!params) return;

        params.forEach((param: any) => {
            let paramType = param.type;
            if (!paramType) {
                paramType = NodeTypeSystem.determineParamType(param.name);
            }
            const defaultValue = param.default !== undefined ? param.default : NodeTypeSystem.getDefaultValue(param.name);
            this.properties[param.name] = defaultValue;
        });
    }

    setError(message: string) {
        this.error = message;
        this.color = '#FF0000'; // Red border for error
        this.setDirtyCanvas(true, true);
        showError(message);
    }

    // Delegate to renderer
    drawProgressBar(ctx: CanvasRenderingContext2D) {
        this.renderer.drawProgressBar(ctx);
    }

    onDrawForeground(ctx: CanvasRenderingContext2D) {
        this.renderer.onDrawForeground(ctx);
    }

    // Delegate to interactions
    onDblClick(event: MouseEvent, pos: [number, number], canvas: any): boolean {
        return this.interactions.onDblClick(event, pos, canvas);
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
        this.renderer.pulseHighlight();
    }

    setProgress(progress: number, text?: string) {
        this.renderer.setProgress(progress, text);
    }

    clearProgress() {
        this.renderer.clearProgress();
    }

    onConnectionsChange() { }

    configure(info: any) {
        super.configure(info);
        this.widgetManager.syncWidgetValues();
        this.setDirtyCanvas(true, true);
    }

    onConnectInput(inputIndex: number, outputType: string | number, _outputSlot: any, _outputNode: any, _outputIndex: number): boolean {
        const inputSlot = this.inputs[inputIndex];
        const inputType = inputSlot.type;
        return NodeTypeSystem.validateConnection(inputType, outputType);
    }

    // Delegate methods for backward compatibility
    syncWidgetValues() {
        this.widgetManager.syncWidgetValues();
    }

    wrapText(text: string, maxWidth: number, ctx: CanvasRenderingContext2D): string[] {
        return this.renderer.wrapText(text, maxWidth, ctx);
    }

    formatComboValue(value: any): string {
        return this.widgetManager.formatComboValue(value);
    }

    parseType(typeInfo: any): string | number {
        return NodeTypeSystem.parseType(typeInfo);
    }

    findOutputSlotIndex(name: string): number {
        return this.outputs?.findIndex(output => output.name === name) ?? -1;
    }
}