import { LGraphNode, LiteGraph, type IDOMWidget } from '@fig-node/litegraph';
import { NodeProperty } from '@fig-node/litegraph/dist/LGraphNode';
import { Dictionary } from '@fig-node/litegraph/dist/interfaces';
import { ISerialisedNode } from '@fig-node/litegraph/dist/types/serialisation';
import { NodeWidgetManager } from '../utils/NodeWidgetManager';
import { NodeRenderer } from '../utils/NodeRenderer';
import { NodeInteractions } from '../utils/NodeInteractions';
import { ServiceRegistry } from '../../services/ServiceRegistry';
import { TypeColorRegistry, TypeInfo } from '../../services/TypeColorRegistry';

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

// ============ UI Configuration Types (imported from @fig-node/core) ============
import type {
    ResultDisplayMode,
    NodeAction,
    ResultFormatter,
    BodyWidget,
    BodyWidgetOptions,
    ResultWidget,
    DataSource,
    NodeUIConfig,
    OutputDisplayConfig,
} from '@fig-node/core';

// ============ Output Display System (Option A) ============
import type { OutputDisplayRenderer, RenderBounds } from '../displays/OutputDisplayRenderer';
import { createOutputDisplay } from '../displays/outputDisplayRegistry';

// Re-export for consumers that import from this file
export type {
    ResultDisplayMode,
    NodeAction,
    ResultFormatter,
    BodyWidget,
    BodyWidgetOptions,
    ResultWidget,
    DataSource,
    NodeUIConfig,
};

export interface NodeData {
    inputs?: unknown;
    outputs?: unknown;
    params?: Array<{
        name: string;
        type?: string;
        default?: unknown;
        options?: unknown[];
        min?: number;
        max?: number;
        step?: number;
        precision?: number;
    }>;
    uiConfig?: NodeUIConfig;
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

    // UI configuration from backend (ComfyUI-style)
    protected uiConfig: NodeUIConfig = {};
    protected resultDisplayMode: ResultDisplayMode = 'json';
    protected resultFormatter?: ResultFormatter;

    // Option B: Body widgets and data sources
    bodyWidgets: BodyWidget[] = [];
    resultWidget?: ResultWidget;
    protected dataSourceCache: Map<string, { data: unknown; lastFetch: number }> = new Map();

    // Option A: Output display renderer (separate from input widgets)
    protected outputDisplay: OutputDisplayRenderer | null = null;
    protected outputDisplayConfig?: OutputDisplayConfig;

    constructor(title: string, data: NodeData, serviceRegistry: ServiceRegistry) {
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

    private initializeNode(data: NodeData) {
        // Apply UI configuration from backend (ComfyUI-style)
        this.applyUIConfig(data.uiConfig);

        // Setup inputs and outputs
        this.setupInputs(data.inputs, data.uiConfig?.inputTooltips);
        this.setupOutputs(data.outputs, data.uiConfig?.outputTooltips);

        // Setup properties and widgets
        this.setupProperties(data.params);
        if (data.params) {
            this.widgetManager.createWidgetsFromParams(data.params);
        }

        // Create action buttons from uiConfig
        if (data.uiConfig?.actions) {
            this.createActionButtons(data.uiConfig.actions);
        }
    }

    /**
     * Apply UI configuration from backend node definition.
     * This is the ComfyUI-style approach where UI is configured in backend.
     */
    protected applyUIConfig(uiConfig?: NodeUIConfig) {
        if (!uiConfig) return;

        this.uiConfig = uiConfig;

        // Apply size
        if (uiConfig.size) {
            this.size = [...uiConfig.size];
        }

        // Apply display settings
        if (uiConfig.displayResults !== undefined) {
            this.displayResults = uiConfig.displayResults;
        }

        // Apply result display mode
        if (uiConfig.resultDisplay) {
            this.resultDisplayMode = uiConfig.resultDisplay;
            // If resultDisplay is 'none', disable displayResults
            if (uiConfig.resultDisplay === 'none') {
                this.displayResults = false;
            }
        }

        // Store result formatter (legacy)
        if (uiConfig.resultFormatter) {
            this.resultFormatter = uiConfig.resultFormatter;
        }

        // Option B: Store result widget config
        if (uiConfig.resultWidget) {
            this.resultWidget = uiConfig.resultWidget;
        }

        // Option B: Store body widgets and create DOM widgets
        if (uiConfig.body) {
            this.bodyWidgets = uiConfig.body;
            // Create DOM widgets (textarea, code editor, etc.)
            this.createDOMWidgets(uiConfig.body);
        }

        // Apply resizable setting
        if (uiConfig.resizable !== undefined) {
            this.resizable = uiConfig.resizable;
        }

        // Note: collapsible is a computed getter in LGraphNode based on constructor.collapsable
        // We cannot set it per-instance. The static property on the class controls this.

        // Apply custom colors
        if (uiConfig.color) {
            this.color = uiConfig.color;
        }
        if (uiConfig.bgcolor) {
            this.bgcolor = uiConfig.bgcolor;
        }

        // Option B: Initialize data sources if configured
        if (uiConfig.dataSources) {
            this.initializeDataSources(uiConfig.dataSources);
        }

        // Option A: Initialize output display renderer if configured
        if (uiConfig.outputDisplay) {
            this.initializeOutputDisplay(uiConfig.outputDisplay);
        }
    }

    /**
     * Initialize the output display renderer from config.
     * Output displays handle specialized rendering of execution results.
     */
    protected initializeOutputDisplay(config: OutputDisplayConfig): void {
        this.outputDisplayConfig = config;
        this.outputDisplay = createOutputDisplay(config.type);

        if (this.outputDisplay) {
            this.outputDisplay.init(this as unknown as LGraphNode, config);
            // When using output display, disable legacy displayResults
            this.displayResults = false;
        }
    }

    /**
     * Initialize data sources for dynamic widgets.
     * Fetches initial data and sets up refresh intervals.
     */
    protected initializeDataSources(dataSources: Record<string, DataSource>) {
        for (const [name, config] of Object.entries(dataSources)) {
            this.fetchDataSource(name, config);

            // Set up refresh interval if configured
            if (config.refreshInterval && config.refreshInterval > 0) {
                setInterval(() => {
                    this.fetchDataSource(name, config);
                }, config.refreshInterval);
            }
        }
    }

    /**
     * Fetch data from a data source endpoint.
     */
    protected async fetchDataSource(name: string, config: DataSource) {
        try {
            // Interpolate params with node properties
            let url = config.endpoint;
            if (config.params) {
                const queryParams = new URLSearchParams();
                for (const [key, value] of Object.entries(config.params)) {
                    const interpolated = this.interpolateTemplate(String(value));
                    queryParams.set(key, interpolated);
                }
                url = `${url}?${queryParams.toString()}`;
            }

            // Build fetch options with optional headers
            const fetchOptions: RequestInit = { method: config.method ?? 'GET' };
            if (config.headers) {
                fetchOptions.headers = config.headers;
            }

            const response = await fetch(url, fetchOptions);
            let data = await response.json();

            // Apply transform if specified
            if (config.transform) {
                data = this.applyTransform(data, config.transform);
            }

            this.dataSourceCache.set(name, { data, lastFetch: Date.now() });

            // If targetParam is specified, update the combo widget with fetched values
            if (config.targetParam && Array.isArray(data)) {
                let values: unknown[];
                if (config.valueField) {
                    // Extract specific field from each object in the array
                    values = data
                        .map((item: unknown) => {
                            if (typeof item === 'object' && item !== null) {
                                return (item as Record<string, unknown>)[config.valueField!];
                            }
                            return item;
                        })
                        .filter((v): v is unknown => v !== undefined && v !== null);
                } else {
                    values = data;
                }
                this.widgetManager.setComboValues(config.targetParam, values);
            }

            this.setDirtyCanvas(true, true);
        } catch (error) {
            console.error(`Failed to fetch data source ${name}:`, error);
            // Use fallback values if fetch fails and targetParam is configured
            if (config.fallback && config.targetParam) {
                this.widgetManager.setComboValues(config.targetParam, config.fallback);
                this.setDirtyCanvas(true, true);
            }
        }
    }

    /**
     * Interpolate {{param}} placeholders in a string with node property values.
     */
    protected interpolateTemplate(template: string): string {
        return template.replace(/\{\{(\w+)\}\}/g, (_, key) => {
            const value = this.properties[key];
            return value !== undefined ? String(value) : '';
        });
    }

    /**
     * Apply a simple transform to data (dot-notation path).
     */
    protected applyTransform(data: unknown, transform: string): unknown {
        const parts = transform.split('.');
        let current = data;
        for (const part of parts) {
            if (current === null || current === undefined) return undefined;
            current = (current as Record<string, unknown>)[part];
        }
        return current;
    }

    /**
     * Get cached data source value by name.
     */
    getDataSourceValue(name: string): unknown {
        return this.dataSourceCache.get(name)?.data;
    }

    // ============ DOM Widget Creation ============

    /** Map of DOM widget IDs to their elements for cleanup */
    protected domWidgetElements: Map<string, HTMLElement> = new Map();

    /**
     * Create DOM widgets from body widget configuration.
     * DOM widgets are HTML elements that overlay the canvas.
     */
    protected createDOMWidgets(widgets: BodyWidget[]): void {
        for (const config of widgets) {
            if (config.type === 'textarea') {
                this.createTextareaWidget(config);
            }
            // Future: 'code', 'json', etc. DOM widgets can be added here
        }
    }

    /**
     * Create a textarea DOM widget.
     * The textarea follows the node as it moves on the canvas.
     */
    protected createTextareaWidget(config: BodyWidget): void {
        const opts = config.options as BodyWidgetOptions | undefined;

        const textarea = document.createElement('textarea');
        textarea.className = 'litegraph-dom-widget litegraph-textarea';
        textarea.spellcheck = opts?.spellcheck ?? false;
        textarea.placeholder = opts?.placeholder ?? '';

        // Add read-only support
        const isReadOnly = opts?.readonly ?? false;
        if (isReadOnly) {
            textarea.readOnly = true;
            textarea.style.cursor = 'default';
            textarea.classList.add('litegraph-textarea-readonly');
        }

        // Parse bind path (e.g., 'properties.value')
        const bindPath = config.bind;
        let getValue: (() => unknown) | undefined;
        let setValue: ((v: unknown) => void) | undefined;

        if (bindPath) {
            const parts = bindPath.split('.');
            getValue = () => {
                let obj: unknown = this;
                for (const p of parts) {
                    obj = (obj as Record<string, unknown>)?.[p];
                }
                return obj;
            };
            setValue = (v: unknown) => {
                if (parts[0] === 'properties' && parts[1]) {
                    this.properties[parts[1]] = v as NodeProperty | undefined;
                    this.setDirtyCanvas(true, true);
                }
            };

            // Set initial value
            textarea.value = String(getValue() ?? '');

            // Sync value on input (skip if readonly)
            if (!isReadOnly) {
                textarea.addEventListener('input', () => {
                    setValue?.(textarea.value);
                });
            }
        }

        // Prevent canvas from receiving events when interacting with textarea
        textarea.addEventListener('mousedown', (e) => e.stopPropagation());
        textarea.addEventListener('keydown', (e) => e.stopPropagation());
        textarea.addEventListener('wheel', (e) => e.stopPropagation());

        // Calculate widget height based on node size and title
        const titleHeight = LiteGraph.NODE_TITLE_HEIGHT;
        const padding = 8;
        const widgetHeight = Math.max(50, this.size[1] - titleHeight - padding * 2);

        // Add widget via litegraph API
        const domWidget = this.addDOMWidget(config.id, 'textarea', textarea, {
            hideOnZoom: opts?.hideOnZoom ?? true,
            zoomThreshold: opts?.zoomThreshold,
            getValue: () => textarea.value,
            setValue: (v: unknown) => { textarea.value = String(v ?? ''); },
            getMinHeight: () => 50,
            getMaxHeight: () => widgetHeight,
        });

        // Store computed height for positioning
        domWidget.computedHeight = widgetHeight;
        // Position after title bar
        domWidget.y = titleHeight + padding;

        // Store reference for cleanup
        this.domWidgetElements.set(config.id, textarea);
    }

    /**
     * Attach DOM widget elements to the canvas container.
     * Called when node is added to graph.
     */
    protected attachDOMWidgets(): void {
        const graph = this.graph;
        if (!graph) return;

        const canvas = graph.list_of_graphcanvas?.[0];
        const container = canvas?.canvas?.parentElement;
        if (!container) return;

        for (const [_id, element] of this.domWidgetElements) {
            if (!element.parentElement) {
                container.appendChild(element);
            }
        }
    }

    /**
     * Detach and remove DOM widget elements.
     * Called when node is removed from graph.
     */
    protected detachDOMWidgets(): void {
        for (const [_id, element] of this.domWidgetElements) {
            element.remove();
        }
        this.domWidgetElements.clear();
    }

    // Lifecycle hooks for DOM widgets
    onAdded(): void {
        this.attachDOMWidgets();
    }

    onRemoved(): void {
        this.detachDOMWidgets();
        // Clean up output display
        if (this.outputDisplay) {
            this.outputDisplay.destroy();
            this.outputDisplay = null;
        }
    }

    /**
     * Create action buttons from uiConfig.
     * Actions are rendered as clickable buttons in the node.
     */
    protected createActionButtons(actions: NodeAction[]) {
        for (const action of actions) {
            const label = action.icon ? `${action.icon} ${action.label}` : action.label;
            this.addWidget('button', label, '', () => {
                this.handleAction(action.id);
            }, {});
        }
    }

    /**
     * Handle action button clicks.
     * Override in subclasses to implement custom action handling.
     * Default implementation emits an event that can be handled externally.
     */
    protected handleAction(actionId: string) {
        // Default action handlers
        switch (actionId) {
            case 'copyResult':
                this.copyResultToClipboard();
                break;
            case 'copyJson':
                this.copyResultAsJson();
                break;
            default:
                // Emit custom event for external handling
                console.log(`Action triggered: ${actionId}`, { nodeId: this.id, result: this.result });
        }
    }

    /**
     * Copy result to clipboard as formatted text.
     */
    protected copyResultToClipboard() {
        if (this.displayText) {
            navigator.clipboard.writeText(this.displayText);
        }
    }

    /**
     * Copy result as JSON to clipboard.
     */
    protected copyResultAsJson() {
        if (this.result) {
            navigator.clipboard.writeText(JSON.stringify(this.result, null, 2));
        }
    }

    private setupInputs(inputs: unknown, tooltips?: Record<string, string>) {
        if (!inputs) return;

        const typeColorRegistry = this.serviceRegistry?.get('typeColorRegistry') as TypeColorRegistry | null;

        const isArray = Array.isArray(inputs);
        const inputEntries: Array<[string, unknown]> = isArray
            ? (inputs as string[]).map((name: string) => [name, null])
            : (Object.entries(inputs) as Array<[string, unknown]>);

        inputEntries.forEach(([inp, typeInfo]: [string, unknown]) => {
            // Use TypeColorRegistry for both type parsing and color
            const typeStr = typeColorRegistry?.parseType(typeInfo) ?? 0;
            const inputSlot = this.addInput(inp, typeStr);

            if (typeInfo && typeColorRegistry) {
                inputSlot.color = typeColorRegistry.getTypeColor(typeInfo as TypeInfo | string);
            }
            if (tooltips?.[inp]) {
                inputSlot.tooltip = tooltips[inp];
            }
        });
    }

    private setupOutputs(outputs: unknown, tooltips?: Record<string, string>) {
        if (!outputs) return;

        const typeColorRegistry = this.serviceRegistry?.get('typeColorRegistry') as TypeColorRegistry | null;

        const isArray = Array.isArray(outputs);
        const outputEntries: Array<[string, unknown]> = isArray
            ? (outputs as string[]).map((name: string) => [name, null])
            : (Object.entries(outputs) as Array<[string, unknown]>);

        outputEntries.forEach(([out, typeInfo]: [string, unknown], index: number) => {
            // Use TypeColorRegistry for both type parsing and color
            const typeStr = typeColorRegistry?.parseType(typeInfo) ?? 0;
            this.addOutput(out, typeStr);

            if (typeInfo && typeColorRegistry) {
                this.outputs[index]!.color = typeColorRegistry.getTypeColor(typeInfo as TypeInfo | string);
            }
            if (tooltips?.[out]) {
                this.outputs[index]!.tooltip = tooltips[out];
            }
        });
    }

    private setupProperties(params: Array<{ name: string; type?: string; default?: unknown; options?: unknown[]; min?: number; max?: number; step?: number; precision?: number }> | undefined) {
        if (!params) return;

        params.forEach((param) => {
            const defaultValue = param.default !== undefined ? param.default : this.getDefaultParamValue(param.name);
            this.properties[param.name] = defaultValue as NodeProperty | undefined;
        });
    }

    /** Get a sensible default value based on param name */
    private getDefaultParamValue(name: string): unknown {
        const lower = name.toLowerCase();
        if (lower.includes('days') || lower.includes('period')) return 14;
        if (lower.includes('bool')) return true;
        return '';
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
        // Draw base renderer (highlight, progress, error, default text display)
        this.renderer.onDrawForeground(ctx);

        // Draw output display if configured
        if (this.outputDisplay) {
            const bounds = this.getOutputDisplayBounds();
            this.outputDisplay.draw(ctx, bounds);
        }
    }

    /**
     * Calculate bounds for output display area.
     * Accounts for title bar and widgets.
     */
    protected getOutputDisplayBounds(): RenderBounds {
        const padding = 12;
        const widgetHeight = this.widgets ? this.widgets.length * LiteGraph.NODE_WIDGET_HEIGHT : 0;
        const widgetSpacing = widgetHeight > 0 ? 8 : 0;

        const x = padding;
        const y = LiteGraph.NODE_TITLE_HEIGHT + widgetHeight + widgetSpacing + padding;
        const width = Math.max(0, this.size[0] - padding * 2);
        const height = Math.max(0, this.size[1] - y - padding);

        return { x, y, width, height };
    }

    // Delegate to interactions, with output display handling
    onDblClick(event: MouseEvent, pos: [number, number], canvas: any): boolean {
        // Try output display first
        if (this.outputDisplay?.onDblClick?.(event, { x: pos[0], y: pos[1] }, canvas)) {
            return true;
        }
        return this.interactions.onDblClick(event, pos, canvas);
    }

    // Mouse wheel handler for output display
    onMouseWheel(event: WheelEvent, pos: [number, number], canvas: any): boolean {
        if (this.outputDisplay?.onMouseWheel?.(event, { x: pos[0], y: pos[1] }, canvas)) {
            return true;
        }
        return false;
    }

    // Mouse down handler for output display
    onMouseDown(event: MouseEvent, pos: [number, number], canvas: any): boolean {
        if (this.outputDisplay?.onMouseDown?.(event, { x: pos[0], y: pos[1] }, canvas)) {
            return true;
        }
        return false;
    }

    updateDisplay(result: unknown) {
        this.result = result;

        // If using output display, delegate to it
        if (this.outputDisplay) {
            this.outputDisplay.updateFromResult(result);
            this.setDirtyCanvas(true, true);
            return;
        }

        // Legacy: Format display based on resultDisplayMode
        switch (this.resultDisplayMode) {
            case 'none':
                this.displayText = '';
                break;

            case 'text':
                // Display as plain text (extract primary output)
                if (this.displayResults && result) {
                    const outputs = Object.values(result as Record<string, unknown>);
                    const primaryOutput = outputs.length === 1 ? outputs[0] : result;
                    this.displayText = typeof primaryOutput === 'string'
                        ? primaryOutput
                        : String(primaryOutput);
                }
                break;

            case 'summary':
                // Use result formatter template
                if (this.displayResults && result && this.resultFormatter) {
                    this.displayText = this.formatResultWithTemplate(result);
                }
                break;

            case 'json':
            default:
                // Default: JSON display
                if (this.displayResults && result) {
                    const outputs = Object.values(result as Record<string, unknown>);
                    const primaryOutput = outputs.length === 1 ? outputs[0] : result;
                    this.displayText = typeof primaryOutput === 'string'
                        ? primaryOutput
                        : JSON.stringify(primaryOutput, null, 2);
                }
                break;
        }

        this.setDirtyCanvas(true, true);
    }

    /**
     * Handle streaming updates for output display.
     */
    onStreamUpdate(chunk: unknown) {
        if (this.outputDisplay?.onStreamUpdate) {
            this.outputDisplay.onStreamUpdate(chunk);
        }
    }

    /**
     * Format result using the configured result formatter template.
     */
    protected formatResultWithTemplate(result: unknown): string {
        if (!this.resultFormatter) return '';

        const resultObj = result as Record<string, unknown>;

        if (this.resultFormatter.type === 'template' && this.resultFormatter.template) {
            // Replace {{field}} placeholders with actual values
            let output = this.resultFormatter.template;
            const matches = output.match(/\{\{(\w+)\}\}/g) || [];

            for (const match of matches) {
                const fieldName = match.slice(2, -2); // Remove {{ and }}
                const value = this.getNestedValue(resultObj, fieldName);
                output = output.replace(match, String(value ?? ''));
            }

            return output;
        }

        if (this.resultFormatter.type === 'fields' && this.resultFormatter.fields) {
            // Display specified fields
            const lines: string[] = [];
            for (const field of this.resultFormatter.fields) {
                const value = this.getNestedValue(resultObj, field);
                if (value !== undefined) {
                    lines.push(`${field}: ${typeof value === 'object' ? JSON.stringify(value) : value}`);
                }
            }

            const maxLines = this.resultFormatter.maxLines ?? 10;
            if (lines.length > maxLines) {
                return lines.slice(0, maxLines).join('\n') + '\n...';
            }
            return lines.join('\n');
        }

        return JSON.stringify(result, null, 2);
    }

    /**
     * Get nested value from object using dot notation.
     */
    protected getNestedValue(obj: Record<string, unknown>, path: string): unknown {
        const parts = path.split('.');
        let current: unknown = obj;

        for (const part of parts) {
            if (current === null || current === undefined) return undefined;
            current = (current as Record<string, unknown>)[part];
        }

        return current;
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
        const typeColorRegistry = this.serviceRegistry?.get('typeColorRegistry') as TypeColorRegistry | null;
        return typeColorRegistry?.parseType(typeInfo) ?? 0;
    }

    findOutputSlotIndex(name: string): number {
        return this.outputs?.findIndex(output => output.name === name) ?? -1;
    }
}