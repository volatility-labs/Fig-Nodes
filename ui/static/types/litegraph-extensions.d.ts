// TypeScript declarations for LiteGraph extensions used in EditorInitializer

// Custom interfaces that extend LiteGraph types without conflicts
export interface ExtendedLGraphCanvas {
    showSearchBox: () => void;
    getLastMouseEvent: () => MouseEvent | null;
    selected_nodes: Record<string, any>;
    prompt: (
        title: string,
        value: unknown,
        callback: (v: unknown) => void,
        options?: { type?: 'number' | 'text'; input?: 'number' | 'text'; step?: number; min?: number }
    ) => void;
    convertEventToCanvasOffset: (e: MouseEvent) => number[];
    draw: (flag1?: boolean, flag2?: boolean) => void;
    canvas: HTMLCanvasElement;
    graph: ExtendedLGraph;
    links_render_mode: number;
    render_curved_connections: boolean;
    setDirty: (flag1?: boolean, flag2?: boolean) => void;
}

export interface ExtendedLiteGraph {
    prompt: (
        title: string,
        value: unknown,
        callback: (v: unknown) => void,
        options?: { type?: 'number' | 'text'; input?: 'number' | 'text'; step?: number; min?: number }
    ) => void;
}

export interface ExtendedLGraph {
    _nodes: ExtendedLGraphNode[];
    getNodeOnPos?: (x: number, y: number) => ExtendedLGraphNode | null;
    configure: (data: GraphData) => void;
    clear: () => void;
    start: () => void;
    remove: (node: ExtendedLGraphNode) => void;
    serialize: () => GraphData;
    add: (node: ExtendedLGraphNode) => void;
    list_of_graphcanvas?: ExtendedLGraphCanvas[];
}

export interface ExtendedLGraphNode {
    pos?: [number, number];
    size?: [number, number];
    inputs?: ExtendedNodeSlot[];
    outputs?: ExtendedNodeSlot[];
    flags?: Record<string, any>;
    widgets?: ExtendedWidget[];
    properties?: Record<string, any>;
    graph?: ExtendedLGraph;
    getConnectionPos: (isInput: boolean, slotIndex: number) => [number, number] | null;
    isPointInside?: (x: number, y: number) => boolean;
    onDblClick?: (event: MouseEvent, localPos: [number, number], canvas: ExtendedLGraphCanvas) => boolean;
    findInputSlot: (name: string) => number;
    onConnectInput: (inputIndex: number, inputType: string | number, outputSlot: ExtendedNodeSlot, outputNode: ExtendedLGraphNode, outputIndex: number) => boolean;
}

export interface ExtendedNodeSlot {
    name: string;
    type: any;
    tooltip?: string;
}

export interface ExtendedWidget {
    name: string;
    type: string;
    value?: any;
    options?: any;
    paramName?: string;
    callback?: (value: any) => void;
    description?: string;
}

export interface GraphData {
    nodes: ExtendedLGraphNode[];
    links: any[];
    config?: any;
    extra?: any;
    groups?: any[];
    version?: number;
}

// Extended Window interface for global properties
export interface ExtendedWindow {
    linkModeManager?: {
        cycleLinkMode: () => void;
        applyLinkMode: (mode: number) => void;
        getCurrentLinkMode: () => number;
        restoreFromGraphConfig: (config: GraphData) => void;
    };
    dialogManager?: {
        showQuickValuePrompt: (title: string, value: string, numericOnly: boolean, callback: (value: string | null) => void) => void;
        setLastMouseEvent: (event: MouseEvent) => void;
    };
    openSettings?: () => void;
    getCurrentGraphData?: () => GraphData;
    getRequiredKeysForGraph?: (graphData: GraphData) => Promise<string[]>;
    checkMissingKeys?: (requiredKeys: string[]) => Promise<string[]>;
    setLastMissingKeys?: (keys: string[]) => void;
    getLastMissingKeys?: () => string[];
    graph?: ExtendedLGraph;
    LiteGraph?: ExtendedLiteGraph;
}

// Extended HTMLElement interface for style properties
export interface ExtendedHTMLElement extends HTMLElement {
    style: CSSStyleDeclaration & {
        pointerEvents?: string;
    };
}

// Extended Navigator interface for clipboard
export interface ExtendedNavigator extends Navigator {
    clipboard?: Clipboard;
}

// Extended Clipboard interface
export interface ExtendedClipboard {
    writeText: (text: string) => Promise<void>;
}

// Extended File interface
export interface ExtendedFile extends File {
    text?: () => Promise<string>;
}

// Extended Canvas Context interface
export interface ExtendedCanvasRenderingContext2D extends CanvasRenderingContext2D {
    fillRect?: (x: number, y: number, width: number, height: number) => void;
}

// Global type augmentation
declare global {
    interface Window extends ExtendedWindow { }
    interface GlobalThis {
        LiteGraph?: ExtendedLiteGraph;
        fetch?: typeof fetch;
        localStorage?: Storage;
        URL?: typeof URL;
        Blob?: typeof Blob;
        navigator?: ExtendedNavigator;
        document?: Document;
    }

    interface Navigator extends ExtendedNavigator { }
    interface Clipboard extends ExtendedClipboard { }
    interface File extends ExtendedFile { }
}

export { };
