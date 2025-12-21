import { LGraphNode } from '@fig-node/litegraph';
import { NodeProperty } from '@fig-node/litegraph/dist/LGraphNode';
import { Dictionary } from '@fig-node/litegraph/dist/interfaces';
import { ISerialisedNode } from '@fig-node/litegraph/dist/types/serialisation';
import { NodeTypeSystem } from '../utils/NodeTypeSystem';
import { NodeWidgetManager } from '../utils/NodeWidgetManager';
import { NodeRenderer } from '../utils/NodeRenderer';
import { NodeInteractions } from '../utils/NodeInteractions';
import { ServiceRegistry } from '../../services/ServiceRegistry';
import { TypeColorRegistry, TypeInfo } from '../../services/TypeColorRegistry';
import { PerformanceProfiler } from '../../services/PerformanceProfiler';

// Reinstate module augmentation at top:
declare module '@fig-node/litegraph' {
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
    isExecuting: boolean = false;
    readonly highlightDurationMs: number = 500;
    readonly pulseCycleMs: number = 1200; // Full pulse cycle duration for continuous pulsing
    progress: number = -1; // -1 = no progress, 0-100 = progress percentage
    progressText: string = '';

    // Modular components
    protected widgetManager: NodeWidgetManager;
    protected renderer: NodeRenderer;
    protected interactions: NodeInteractions;
    protected serviceRegistry: ServiceRegistry;

    constructor(title: string, data: { inputs?: unknown; outputs?: unknown; params?: Array<{ name: string; type?: string; default?: unknown; options?: unknown[]; min?: number; max?: number; step?: number; precision?: number }> }, serviceRegistry: ServiceRegistry) {
        super(title);
        this.size = [200, 100];

        // Initialize properties object
        this.properties = {};

        // Store service registry
        this.serviceRegistry = serviceRegistry;

        // Initialize modular components
        this.widgetManager = new NodeWidgetManager(this as unknown as LGraphNode & { properties: { [key: string]: unknown } }, serviceRegistry);
        this.renderer = new NodeRenderer(this as unknown as LGraphNode & { displayResults: boolean; result: unknown; displayText: string; error: string; highlightStartTs: number | null; isExecuting: boolean; readonly highlightDurationMs: number; readonly pulseCycleMs: number; progress: number; progressText: string; properties: { [key: string]: unknown } });
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

        const typeColorRegistry = this.serviceRegistry?.get('typeColorRegistry') as TypeColorRegistry | null;

        const isArray = Array.isArray(inputs);
        const inputEntries: Array<[string, unknown]> = isArray
            ? (inputs as string[]).map((name: string) => [name, null])
            : (Object.entries(inputs) as Array<[string, unknown]>);

        inputEntries.forEach(([inp, typeInfo]: [string, unknown]) => {
            const typeStr = NodeTypeSystem.parseType(typeInfo);
            let color: string | undefined;
            if (typeInfo && typeColorRegistry) {
                color = typeColorRegistry.getTypeColor(typeInfo as TypeInfo);
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

        const typeColorRegistry = this.serviceRegistry?.get('typeColorRegistry') as TypeColorRegistry | null;

        const isArray = Array.isArray(outputs);
        const outputEntries: Array<[string, unknown]> = isArray
            ? (outputs as string[]).map((name: string) => [name, null])
            : (Object.entries(outputs) as Array<[string, unknown]>);

        outputEntries.forEach(([out, typeInfo]: [string, unknown], index: number) => {
            const typeStr = NodeTypeSystem.parseType(typeInfo);
            this.addOutput(out, typeStr);
            if (typeInfo && typeColorRegistry) {
                const color = typeColorRegistry.getTypeColor(typeInfo as TypeInfo);
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
        try {
            const sr: ServiceRegistry | undefined = (window as any).serviceRegistry || undefined;
            const dm = sr?.get?.('dialogManager');
            if (dm && typeof (dm as any).showError === 'function') {
                (dm as any).showError(message);
            }
        } catch { /* ignore */ }
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
        const profiler = PerformanceProfiler.getInstance();
        
        profiler?.measure('updateDisplay', () => {
        this.result = result;
        if (this.displayResults) {
            const outputs = Object.values(result as Record<string, unknown>);
            const primaryOutput = outputs.length === 1 ? outputs[0] : result;
            
            if (typeof primaryOutput === 'string') {
                // Truncate long strings to prevent UI freeze
                this.displayText = primaryOutput.length > 1000 
                    ? primaryOutput.substring(0, 1000) + '... (truncated, connect to LoggingNode for full output)'
                    : primaryOutput;
            } else {
                // Smart truncation for different result types
                try {
                    // Check if it's a message object (from LLM nodes)
                    const resultObj = primaryOutput as any;
                    if (resultObj && typeof resultObj === 'object' && 'content' in resultObj) {
                        // LLM message - show summary
                        const content = resultObj.content || '';
                        const role = resultObj.role || 'assistant';
                        const hasToolCalls = resultObj.tool_calls && resultObj.tool_calls.length > 0;
                        
                        let summary = `[${role}]\n${content}`;
                        
                        if (hasToolCalls) {
                            summary += `\n\n🔧 Tool calls: ${resultObj.tool_calls.length}`;
                        }
                        
                        // Truncate if still too long
                        this.displayText = summary.length > 1500
                            ? summary.substring(0, 1500) + '\n... (truncated, connect to LoggingNode for full output)'
                            : summary;
                    } else if (Array.isArray(resultObj)) {
                        // Array of results (e.g., trading analysis)
                        const itemCount = resultObj.length;
                        if (itemCount <= 3) {
                            // Small arrays - show all
                            const jsonStr = JSON.stringify(resultObj, null, 2);
                            this.displayText = jsonStr.length > 2000
                                ? jsonStr.substring(0, 2000) + '\n... (truncated, connect to LoggingNode for full output)'
                                : jsonStr;
                        } else {
                            // Large arrays - show summary
                            this.displayText = `[Array with ${itemCount} items]\n${JSON.stringify(resultObj.slice(0, 2), null, 2)}\n... and ${itemCount - 2} more\n(Connect to LoggingNode for full output)`;
                        }
                    } else {
                        // Generic object - truncate JSON
                        const jsonStr = JSON.stringify(primaryOutput, null, 2);
                        this.displayText = jsonStr.length > 1500
                            ? jsonStr.substring(0, 1500) + '\n... (truncated, connect to LoggingNode for full output)'
                            : jsonStr;
                    }
                } catch (e) {
                    // Handle circular references or other stringify errors
                    this.displayText = '[Result too large to display - connect to LoggingNode]';
                }
            }
            } else {
                // Skip expensive JSON.stringify when displayResults is false
                this.displayText = '';
            }
        }, { nodeType: this.title, displayResults: this.displayResults });
        
        // Use debounced canvas redraw to prevent lag when many nodes update simultaneously
        this.debouncedSetDirtyCanvas();
    }

    // Debounced canvas redraw to prevent lag during batch updates (e.g. scan completion)
    private static canvasRedrawTimeout: number | null = null;
    private debouncedSetDirtyCanvas() {
        const profiler = PerformanceProfiler.getInstance();
        
        // Clear existing timeout
        if (BaseCustomNode.canvasRedrawTimeout !== null) {
            clearTimeout(BaseCustomNode.canvasRedrawTimeout);
        }
        
        // Set new timeout - all updates within 16ms (1 frame) will be batched
        BaseCustomNode.canvasRedrawTimeout = window.setTimeout(() => {
            profiler?.trackRenderCall();
        this.setDirtyCanvas(true, true);
            BaseCustomNode.canvasRedrawTimeout = null;
        }, 16);
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

    clearHighlight() {
        this.renderer.clearHighlight();
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