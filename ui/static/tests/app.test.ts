import { describe, expect, test, vi, beforeEach } from 'vitest';
import { JSDOM } from 'jsdom';

// Import after mocks from setup are applied
import * as uiUtils from '@/utils/uiUtils';

describe('app.ts initialization', () => {
    beforeEach(() => {
        vi.restoreAllMocks();
        vi.resetModules();
        // Minimal DOM with required container and canvas
        const dom = new JSDOM(`<!doctype html><html><body>
            <div class="app-container">
              <canvas id="litegraph-canvas" width="300" height="150"></canvas>
              <div id="node-palette-overlay"></div>
              <div id="node-palette"></div>
              <input id="node-palette-search" />
              <div id="node-palette-list"></div>
              <span id="graph-name">default-graph.json</span>
              <button id="new"></button>
              <button id="save"></button>
              <input id="graph-file" type="file" />
              <button id="load"></button>
              <div id="top-progress"></div>
              <div id="top-progress-bar"></div>
              <div id="top-progress-text"></div>
            </div>
        </body></html>`, { url: 'http://localhost/' });
        (globalThis as any).document = dom.window.document as any;
        (globalThis as any).window = dom.window as any;
        // Ensure global localStorage points to the current window's storage
        (globalThis as any).localStorage = (dom.window as any).localStorage;
    });

    test('registers nodes and starts graph', async () => {
        // Mock fetch for /nodes metadata
        (globalThis as any).fetch = vi.fn(async (url: string) => {
            if (url === '/nodes') {
                return {
                    ok: true,
                    json: async () => ({
                        nodes: {
                            'Test/NodeA': { category: 'Test', inputs: {}, outputs: {}, params: [], uiModule: undefined },
                            'Test/NodeB': { category: 'Test', inputs: {}, outputs: {}, params: [], uiModule: 'StreamingCustomNode' },
                        },
                    }),
                } as any;
            }
            return { ok: true, json: async () => ({}) } as any;
        });

        // Spy on utilities
        const statusSpy = vi.spyOn(uiUtils, 'updateStatus');

        // Import app.ts which attaches DOMContentLoaded listener
        const mod = await import('../app.ts');
        expect(mod).toBeTruthy();

        // Trigger DOMContentLoaded to bootstrap
        const ev = new (window as any).Event('DOMContentLoaded');
        document.dispatchEvent(ev);

        // Wait a microtask for async createEditor
        await new Promise((r) => setTimeout(r, 0));

        // Expect status updates called to connected state
        expect(statusSpy).toHaveBeenCalled();

        // Ensure at least one node registered
        const { LiteGraph } = await import('@comfyorg/litegraph');
        expect((LiteGraph as any)._registry.size).toBeGreaterThanOrEqual(1);
    });

    test('restores graph and name from autosave on load', async () => {
        // Prepare autosave payload BEFORE importing app.ts
        const autosaveKey = 'fig-nodes:autosave:v1';
        const savedGraph = {
            nodes: [{
                id: 1,
                type: 'Test/NodeA',
                pos: [100, 100],
                size: [200, 100],
                flags: {},
                order: 0,
                mode: 0
            }],
            links: [],
            groups: [],
            config: {},
            version: 1
        };
        const saved = { graph: savedGraph, name: 'restored.json', timestamp: Date.now() };
        window.localStorage.setItem(autosaveKey, JSON.stringify(saved));

        // Mock fetch for /nodes
        (globalThis as any).fetch = vi.fn(async (url: string) => {
            if (url === '/nodes') {
                return {
                    ok: true,
                    json: async () => ({
                        nodes: {
                            'Test/NodeA': { category: 'Test', inputs: {}, outputs: {}, params: [] },
                        },
                    }),
                } as any;
            }
            // default-graph should not be needed because autosave exists
            return { ok: true, json: async () => ({}) } as any;
        });

        const mod = await import('../app.ts');
        expect(mod).toBeTruthy();

        document.dispatchEvent(new (window as any).Event('DOMContentLoaded'));
        await new Promise((r) => setTimeout(r, 0));

        const nameEl = document.getElementById('graph-name')!;
        expect(nameEl.textContent).toBe('restored.json');
    });

    test('clicking New clears and sets name to untitled.json and autosaves', async () => {
        // Ensure no pre-existing autosave
        window.localStorage.removeItem('fig-nodes:autosave:v1');

        // Mock fetch for nodes and default graph
        const fetchSpy = vi.fn(async (url: string) => {
            if (url === '/nodes') return { ok: true, json: async () => ({ nodes: {} }) } as any;
            if (url === '/examples/default-graph.json') return { ok: true, json: async () => ({ nodes: [], links: [] }) } as any;
            return { ok: true, json: async () => ({}) } as any;
        });
        (globalThis as any).fetch = fetchSpy as any;

        await import('../app.ts');
        document.dispatchEvent(new (window as any).Event('DOMContentLoaded'));
        await new Promise((r) => setTimeout(r, 0));

        const newBtn = document.getElementById('new')! as HTMLButtonElement;
        newBtn.click();

        const nameEl = document.getElementById('graph-name')!;
        expect(nameEl.textContent).toBe('untitled.json');

        // Trigger beforeunload to force autosave write immediately
        window.dispatchEvent(new (window as any).Event('beforeunload'));
        const savedRaw = window.localStorage.getItem('fig-nodes:autosave:v1');
        expect(savedRaw).toBeTruthy();
        const payload = JSON.parse(savedRaw!);
        expect(payload.name).toBe('untitled.json');
        expect(payload.graph).toBeDefined();
    });

    test('falls back to default graph when no autosave is present', async () => {
        window.localStorage.removeItem('fig-nodes:autosave:v1');
        const fetchSpy = vi.fn(async (url: string) => {
            if (url === '/nodes') return { ok: true, json: async () => ({ nodes: {} }) } as any;
            if (url === '/examples/default-graph.json') return { ok: true, json: async () => ({ nodes: [], links: [] }) } as any;
            return { ok: true, json: async () => ({}) } as any;
        });
        (globalThis as any).fetch = fetchSpy as any;

        await import('../app.ts');
        document.dispatchEvent(new (window as any).Event('DOMContentLoaded'));
        await new Promise((r) => setTimeout(r, 0));

        // Verify default graph fetch was attempted
        expect(fetchSpy).toHaveBeenCalledWith('/examples/default-graph.json', { cache: 'no-store' });
    });

    test('Save uses the current graph name for download attribute', async () => {
        // Prepare autosave with a custom name so internal state reflects it
        const autosaveKey = 'fig-nodes:autosave:v1';
        const saved = { graph: { nodes: [], links: [] }, name: 'custom.json', timestamp: Date.now() };
        window.localStorage.setItem(autosaveKey, JSON.stringify(saved));

        // Mock fetch
        (globalThis as any).fetch = vi.fn(async (url: string) => {
            if (url === '/nodes') return { ok: true, json: async () => ({ nodes: {} }) } as any;
            return { ok: true, json: async () => ({}) } as any;
        });

        // Stub document.createElement to capture anchor
        const realCreateEl = document.createElement.bind(document);
        const anchorStub = { href: '', download: '', click: vi.fn() } as any;
        const createSpy = vi.spyOn(document, 'createElement').mockImplementation((tagName: any) => {
            if (String(tagName).toLowerCase() === 'a') return anchorStub;
            return realCreateEl(tagName);
        });

        await import('../app.ts');
        document.dispatchEvent(new (window as any).Event('DOMContentLoaded'));
        await new Promise((r) => setTimeout(r, 0));

        // Click Save
        (document.getElementById('save') as HTMLButtonElement).click();
        expect(anchorStub.download).toBe('custom.json');
        expect(anchorStub.click).toHaveBeenCalled();

        createSpy.mockRestore();
    });
});

describe('Autosave bug coverage', () => {
    test('loading a file updates lastSavedGraphJson to prevent unnecessary autosave', async () => {
        // Mock fetch for nodes and a sample graph file
        (globalThis as any).fetch = vi.fn(async (url: string) => {
            if (url === '/nodes') return { ok: true, json: async () => ({ nodes: {} }) } as any;
            if (url.endsWith('.json')) return { ok: true, json: async () => ({ nodes: [{ id: 1 }], links: [] }) } as any;
            return { ok: true, json: async () => ({}) } as any;
        });

        // Clear storage
        window.localStorage.removeItem('fig-nodes:autosave:v1');

        const statusSpy = vi.spyOn(uiUtils, 'updateStatus');

        // Load app
        await import('../app.ts');
        document.dispatchEvent(new (window as any).Event('DOMContentLoaded'));

        // Wait for initialization to complete
        await vi.waitFor(() => {
            expect(statusSpy).toHaveBeenCalledWith('connected', 'Ready');
        });

        // Add spy for setItem
        const setItemSpy = vi.spyOn(Storage.prototype, 'setItem');

        // Simulate file load
        const fileInput = document.getElementById('graph-file') as HTMLInputElement;
        const mockFile = new File([JSON.stringify({ nodes: [{ id: 1 }], links: [] })], 'loaded.json', { type: 'application/json' });
        Object.defineProperty(fileInput, 'files', { value: [mockFile] });
        fileInput.dispatchEvent(new Event('change'));

        // Wait for reader onload with longer timeout
        await vi.waitFor(() => {
            const nameEl = document.getElementById('graph-name')!;
            expect(nameEl.textContent).toBe('loaded.json');
        }, { timeout: 2000 });

        // Clear storage if any
        window.localStorage.clear();

        // Wait for autosave interval to potentially trigger
        await new Promise((r) => setTimeout(r, 3000));

        // Assert no autosave occurred (since no changes after load)
        expect(setItemSpy).not.toHaveBeenCalled();

        setItemSpy.mockRestore();
        statusSpy.mockRestore();
    });

    test('invalid autosave falls back to default graph', async () => {
        // Set invalid autosave
        window.localStorage.setItem('fig-nodes:autosave:v1', JSON.stringify({ graph: { nodes: null, links: null } }));

        // Mock fetch for nodes and default graph
        (globalThis as any).fetch = vi.fn(async (url: string) => {
            if (url === '/nodes') return { ok: true, json: async () => ({ nodes: {} }) } as any;
            if (url === '/examples/default-graph.json') return { ok: true, json: async () => ({ nodes: [], links: [] }) } as any;
            return { ok: true, json: async () => ({}) } as any;
        });

        await import('../app.ts');
        document.dispatchEvent(new (window as any).Event('DOMContentLoaded'));
        await new Promise((r) => setTimeout(r, 0));

        // Assert fallback fetch was called (will fail if not handled)
        expect((globalThis as any).fetch).toHaveBeenCalledWith('/examples/default-graph.json', { cache: 'no-store' });
        const nameEl = document.getElementById('graph-name')!;
        expect(nameEl.textContent).toBe('default-graph.json'); // This will pass if fallback works, but add try-catch in fix
    });

    test('storage errors are handled gracefully with warning', async () => {
        // Enable fake timers to control autosave interval
        vi.useFakeTimers();

        // Setup localStorage mock that throws on setItem
        const localStorageMock = {
            getItem: vi.fn((_key) => null),
            setItem: vi.fn((_key, _value) => { throw new Error('Storage error'); }),
            removeItem: vi.fn(),
            clear: vi.fn(),
        };
        Object.defineProperty(window, 'localStorage', { value: localStorageMock });
        Object.defineProperty(globalThis as any, 'localStorage', { value: localStorageMock });

        // Mock fetch
        (globalThis as any).fetch = vi.fn(async (url: string) => {
            if (url === '/nodes') return { ok: true, json: async () => ({ nodes: { 'Test/NodeA': { category: 'Test', inputs: {}, outputs: {}, params: [] } } }) } as any;
            return { ok: true, json: async () => ({}) } as any;
        });

        const statusSpy = vi.spyOn(uiUtils, 'updateStatus');

        // Load app
        await import('../app.ts');
        document.dispatchEvent(new (window as any).Event('DOMContentLoaded'));

        // Wait for initialization to complete
        await vi.waitFor(() => {
            expect(statusSpy).toHaveBeenCalledWith('connected', 'Ready');
        });

        // Force autosave via beforeunload event to bypass timer dependence
        window.dispatchEvent(new (window as any).Event('beforeunload'));

        // Assert setItem was attempted (call made, even though it throws)
        expect(localStorageMock.setItem).toHaveBeenCalled();

        // Assert error handling updated status
        expect(statusSpy).toHaveBeenCalledWith('disconnected', 'Autosave failed: Check storage settings');

        // Cleanup
        vi.useRealTimers();
        statusSpy.mockRestore();
    });

    // Skip Bug 3 and 4 for now as they are harder to test meaningfully
});


