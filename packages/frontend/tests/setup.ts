// tests/setup.ts
import { vi } from 'vitest';

// Basic clipboard mock for tests that copy text
Object.assign(globalThis, {
    navigator: {
        clipboard: {
            writeText: vi.fn(async (_t: string) => undefined),
        },
    },
    alert: vi.fn(),
    prompt: vi.fn(),
    confirm: vi.fn(() => true),
});

// Default fetch mock (tests may override case-by-case)
if (!(globalThis as any).fetch) {
    (globalThis as any).fetch = vi.fn(async () => ({ ok: true, json: async () => ({}) }));
}

// Ensure URL blob helpers exist
if (!(globalThis as any).URL) {
    (globalThis as any).URL = {} as any;
}
if (!(globalThis as any).URL.createObjectURL) {
    (globalThis as any).URL.createObjectURL = vi.fn(() => 'blob:mock');
}
if (!(globalThis as any).URL.revokeObjectURL) {
    (globalThis as any).URL.revokeObjectURL = vi.fn();
}

// Mock canvas context for tests
if (typeof HTMLCanvasElement !== 'undefined') {
    const originalGetContext = HTMLCanvasElement.prototype.getContext;
    HTMLCanvasElement.prototype.getContext = function (type: string) {
        if (type === '2d') {
            return {
                fillRect: vi.fn(),
                strokeRect: vi.fn(),
                fillText: vi.fn(),
                drawImage: vi.fn(),
                measureText: vi.fn(() => ({ width: 0 })),
                save: vi.fn(),
                restore: vi.fn(),
                beginPath: vi.fn(),
                moveTo: vi.fn(),
                lineTo: vi.fn(),
                stroke: vi.fn(),
                fill: vi.fn(),
                arc: vi.fn(),
                clearRect: vi.fn(),
                scale: vi.fn(),
                translate: vi.fn(),
                rotate: vi.fn(),
                setTransform: vi.fn(),
                getImageData: vi.fn(),
                putImageData: vi.fn(),
                createImageData: vi.fn(),
                canvas: this,
                globalAlpha: 1,
                globalCompositeOperation: 'source-over',
                fillStyle: '#000000',
                strokeStyle: '#000000',
                lineWidth: 1,
                font: '10px sans-serif',
                textAlign: 'start',
                textBaseline: 'alphabetic',
                shadowColor: 'rgba(0,0,0,0)',
                shadowBlur: 0,
                shadowOffsetX: 0,
                shadowOffsetY: 0
            } as any;
        }
        return originalGetContext.call(this, type);
    };
}

// Polyfill Blob.text() in jsdom if missing
try {
    const hasBlob = typeof (globalThis as any).Blob !== 'undefined';
    const proto = hasBlob ? (globalThis as any).Blob.prototype : undefined;
    if (hasBlob && proto && typeof proto.text !== 'function') {
        proto.text = function thisTextPolyfill(): Promise<string> {
            return new Promise((resolve, reject) => {
                try {
                    const reader = new (globalThis as any).FileReader();
                    reader.onload = () => resolve(String(reader.result || ''));
                    reader.onerror = (e: any) => reject(e);
                    reader.readAsText(this as any);
                } catch (err) {
                    try { resolve(''); } catch { reject(err); }
                }
            });
        };
    }
} catch { /* ignore */ }

// Map global localStorage to window.localStorage in jsdom environment if missing
try {
    if (!(globalThis as any).localStorage && (globalThis as any).window?.localStorage) {
        (globalThis as any).localStorage = (globalThis as any).window.localStorage;
    }
} catch { /* ignore */ }

// Mock HTMLElement.style for jsdom compatibility
try {
    const originalCreateElement = (globalThis as any).document?.createElement;
    if (originalCreateElement) {
        (globalThis as any).document.createElement = function (tagName: string) {
            const element = originalCreateElement.call(this, tagName);
            if (!element.style) {
                element.style = {};
            }
            return element;
        };
    }
} catch { /* ignore */ }

// Minimal LiteGraph mocks sufficient for UI node classes and app.ts
vi.mock('@fig-node/litegraph', () => {
    class LGraphNode {
        title: string;
        size: [number, number];
        inputs: any[];
        outputs: any[];
        widgets: any[];
        flags: Record<string, any>;
        pos: [number, number];
        constructor(title: string = '') {
            this.title = title;
            this.size = [200, 100];
            this.inputs = [];
            this.outputs = [];
            this.widgets = [];
            this.flags = {};
            this.pos = [0, 0];
        }
        configure(_info: any) { /* mock */ }
        addInput(name: string, type: any) {
            const slot = { name, type };
            this.inputs.push(slot);
            return slot;
        }
        addOutput(name: string, type: any) {
            const slot = { name, type };
            this.outputs.push(slot);
            return slot;
        }
        addWidget(type: string, name: string, value: any, callback: (...args: unknown[]) => unknown, options?: any) {
            const widget = { type, name, value, callback, options: options || {} };
            this.widgets.push(widget);
            return widget;
        }
        setDirtyCanvas(_a?: boolean, _b?: boolean) { }
        removeInput(index: number) { this.inputs.splice(index, 1); }
        findInputSlot(name: string) { return this.inputs.findIndex((s: any) => s.name === name); }
    }

    const registry = new Map<string, any>();
    const LiteGraph = {
        NODE_TITLE_HEIGHT: 20,
        NODE_WIDGET_HEIGHT: 24,
        INPUT: 1,
        // Link render mode constants used by app.ts logic and tests
        STRAIGHT_LINK: 0,
        LINEAR_LINK: 1,
        SPLINE_LINK: 2,
        registerNodeType(name: string, klass: any) { registry.set(name, klass); },
        createNode(name: string) {
            const K = registry.get(name);
            if (!K) return null;
            try { return new K(); } catch { return { pos: [0, 0] } as any; }
        },
        _registry: registry,
    } as any;

    class LGraph {
        _nodes: any[] = [];
        config: any = {};
        add(node: any) { this._nodes.push(node); }
        serialize() {
            return {
                nodes: this._nodes,
                links: [],
                groups: [],
                config: this.config,
                version: 1
            };
        }
        configure(data: any) {
            if (data.nodes) this._nodes = data.nodes;
            if (data.config) this.config = data.config;
        }
        clear() { this._nodes = []; this.config = {}; }
        start() { }
    }

    class LGraphCanvas {
        canvas: HTMLCanvasElement;
        graph: any;
        selected_nodes: Record<string, any> = {};
        constructor(canvas: HTMLCanvasElement, graph: any) {
            this.canvas = canvas;
            this.graph = graph;
            (this as any).showSearchBox = () => { };
        }
        convertEventToCanvasOffset(e: any) { return [e?.clientX || 0, e?.clientY || 0]; }
        draw() { }
        setDirty(_a?: boolean, _b?: boolean) { /* no-op for tests */ }
    }

    return { LGraphNode, LGraphCanvas, LGraph, LiteGraph };
});

// Silence websocket wiring in tests
vi.mock('../websocket', () => ({
    setupWebSocket: vi.fn(),
}));

