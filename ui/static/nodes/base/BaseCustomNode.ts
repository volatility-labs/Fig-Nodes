import { LGraphNode } from '@comfyorg/litegraph';
import { NodeProperty } from '@comfyorg/litegraph/dist/LGraphNode';
import { Dictionary } from '@comfyorg/litegraph/dist/interfaces';
import { ISerialisedNode } from '@comfyorg/litegraph/dist/types/serialisation';
import { getTypeColor, TypeInfo } from '../../types';
import { showError } from '../../utils/uiUtils';
import { NodeTypeSystem } from '../utils/NodeTypeSystem';
import { NodeWidgetManager } from '../utils/NodeWidgetManager';
import { NodeRenderer } from '../utils/NodeRenderer';
import { NodeInteractions } from '../utils/NodeInteractions';
import { ServiceRegistry } from '../../services/ServiceRegistry';

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
    result: unknown;
    displayText: string = '';
    declare properties: Dictionary<NodeProperty | undefined>;
    error: string = '';
    highlightStartTs: number | null = null;
    readonly highlightDurationMs: number = 900;
    progress: number = -1; // -1 = no progress, 0-100 = progress percentage
    progressText: string = '';

    // Modular components
    protected widgetManager: NodeWidgetManager;
    protected renderer: NodeRenderer;
    protected interactions: NodeInteractions;

    constructor(title: string, data: { inputs?: unknown; outputs?: unknown; params?: Array<{ name: string; type?: string; default?: unknown; options?: unknown[]; min?: number; max?: number; step?: number; precision?: number }> }, serviceRegistry: ServiceRegistry) {
        super(title);
        this.size = [200, 100];

        // Initialize properties object
        this.properties = {};

        // Initialize modular components
        this.widgetManager = new NodeWidgetManager(this as unknown as LGraphNode & { properties: { [key: string]: unknown } }, serviceRegistry);
        this.renderer = new NodeRenderer(this as unknown as LGraphNode & { displayResults: boolean; result: unknown; displayText: string; error: string; highlightStartTs: number | null; readonly highlightDurationMs: number; progress: number; progressText: string; properties: { [key: string]: unknown } });
        this.interactions = new NodeInteractions(this as unknown as LGraphNode & { title: string; pos: [number, number]; size: [number, number] });

        this.initializeNode(data);
    }

    private initializeNode(data: { inputs?: unknown; outputs?: unknown; params?: Array<{ name: string; type?: string; default?: unknown; options?: unknown[]; min?: number; max?: number; step?: number; precision?: number }> }) {
        // Setup inputs and outputs
        this.setupInputs(data.inputs);
        this.setupOutputs(data.outputs);

        // Setup properties and widgets
        this.setupProperties(data.params);
        if (data.params) {
            this.widgetManager.createWidgetsFromParams(data.params);
        }
    }

    private setupInputs(inputs: unknown) {
        if (!inputs) return;

        const isArray = Array.isArray(inputs);
        const inputEntries: Array<[string, unknown]> = isArray
            ? (inputs as string[]).map((name: string) => [name, null])
            : (Object.entries(inputs) as Array<[string, unknown]>);

        inputEntries.forEach(([inp, typeInfo]: [string, unknown]) => {
            const typeStr = NodeTypeSystem.parseType(typeInfo);
            let color: string | undefined;
            if (typeInfo) {
                color = getTypeColor(typeInfo as TypeInfo);
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

    private setupOutputs(outputs: unknown) {
        if (!outputs) return;

        const isArray = Array.isArray(outputs);
        const outputEntries: Array<[string, unknown]> = isArray
            ? (outputs as string[]).map((name: string) => [name, null])
            : (Object.entries(outputs) as Array<[string, unknown]>);

        outputEntries.forEach(([out, typeInfo]: [string, unknown], index: number) => {
            const typeStr = NodeTypeSystem.parseType(typeInfo);
            this.addOutput(out, typeStr);
            if (typeInfo) {
                const color = getTypeColor(typeInfo as TypeInfo);
                this.outputs[index]!.color = color;
            }
        });
    }

    private setupProperties(params: Array<{ name: string; type?: string; default?: unknown; options?: unknown[]; min?: number; max?: number; step?: number; precision?: number }> | undefined) {
        if (!params) return;

        params.forEach((param) => {
            let paramType = param.type;
            if (!paramType) {
                paramType = NodeTypeSystem.determineParamType(param.name);
            }
            const defaultValue = param.default !== undefined ? param.default : NodeTypeSystem.getDefaultValue(param.name);
            this.properties[param.name] = defaultValue as NodeProperty | undefined;
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

    updateDisplay(result: unknown) {
        this.result = result;
        if (this.displayResults) {
            const outputs = Object.values(result as Record<string, unknown>);
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

    configure(info: ISerialisedNode) {
        super.configure(info);
        this.widgetManager.syncWidgetValues();
        this.setDirtyCanvas(true, true);
    }

    onConnectInput(inputIndex: number, outputType: string | number, _outputSlot: unknown, _outputNode: unknown, _outputIndex: number): boolean {
        const inputSlot = this.inputs[inputIndex];
        const inputType = inputSlot?.type;
        // Handle the case where type is 0 (Any type) - don't convert to empty string
        const actualInputType = inputType === 0 ? 0 : (inputType || '');
        return NodeTypeSystem.validateConnection(actualInputType, outputType);
    }

    // Delegate methods for backward compatibility
    syncWidgetValues() {
        this.widgetManager.syncWidgetValues();
    }

    wrapText(text: string, maxWidth: number, ctx: CanvasRenderingContext2D): string[] {
        return this.renderer.wrapText(text, maxWidth, ctx);
    }

    formatComboValue(value: unknown): string {
        return this.widgetManager.formatComboValue(value);
    }

    parseType(typeInfo: unknown): string | number {
        return NodeTypeSystem.parseType(typeInfo);
    }

    findOutputSlotIndex(name: string): number {
        return this.outputs?.findIndex(output => output.name === name) ?? -1;
    }
}