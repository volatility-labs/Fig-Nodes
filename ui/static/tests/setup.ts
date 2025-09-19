// tests/setup.ts
import { vi } from 'vitest';

// Basic clipboard mock for tests that copy text
Object.assign(globalThis, {
    navigator: {
        clipboard: {
            writeText: vi.fn(async (_t: string) => undefined),
        },
    },
});

// Default fetch mock (tests may override case-by-case)
if (!(globalThis as any).fetch) {
    (globalThis as any).fetch = vi.fn(async () => ({ ok: true, json: async () => ({}) }));
}

// Minimal LiteGraph mocks sufficient for UI node classes and app.ts
vi.mock('@comfyorg/litegraph', () => {
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
        configure(info: any) { /* mock */ }
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
        addWidget(type: string, name: string, value: any, callback: Function, options?: any) {
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
        add(node: any) { this._nodes.push(node); }
        serialize() { return {}; }
        configure(_data: any) { }
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
    }

    return { LGraphNode, LGraphCanvas, LGraph, LiteGraph };
});

// Mute UI utilities side-effects during tests; provide no-op implementations
vi.mock('@/utils/uiUtils', () => ({
    setupResize: vi.fn(),
    setupKeyboard: vi.fn(),
    updateStatus: vi.fn(),
    showError: vi.fn(),
}));

// Silence websocket wiring in tests
vi.mock('../websocket', () => ({
    setupWebSocket: vi.fn(),
}));

