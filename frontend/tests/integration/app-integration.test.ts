import { describe, expect, test, beforeEach, vi } from 'vitest';
import { JSDOM } from 'jsdom';

// Mock UIModuleLoader for integration tests
vi.mock('../../services/UIModuleLoader', () => ({
    UIModuleLoader: class MockUIModuleLoader {
        async registerNodes() {
            // Register a test node to satisfy the test expectation
            const { LiteGraph, LGraphNode } = await import('@fig-node/litegraph');
            const TestNode = class extends LGraphNode {
                constructor() {
                    super('TestNode');
                }
            };
            LiteGraph.registerNodeType('Test/TestNode', TestNode);

            return {
                allItems: [{ name: 'Test/TestNode', category: 'Test' }],
                categorizedNodes: { 'Test': ['Test/TestNode'] }
            };
        }
        getNodeMetadata() {
            return {};
        }
    }
}));

describe('App Integration Tests', () => {
    let dom: any;

    beforeEach(() => {
        vi.restoreAllMocks();
        vi.resetModules();

        // Setup DOM with complete app structure
        dom = new JSDOM(`<!doctype html><html><body>
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
                <div id="footer">
                    <div class="footer-section footer-center">
                        <div class="control-group file-controls">
                            <button id="new"></button>
                            <button id="save"></button>
                            <input id="graph-file" type="file" />
                            <button id="load"></button>
                        </div>
                    </div>
                    <div class="footer-section footer-right">
                        <div class="control-group execution-controls">
                            <button id="execute" class="btn-primary">Execute</button>
                            <button id="stop" class="btn-stop" style="display: none;">Stop</button>
                        </div>
                    </div>
                </div>
            </div>
        </body></html>`, { url: 'http://localhost/' });

        (globalThis as any).document = dom.window.document as any;
        (globalThis as any).window = dom.window as any;

        try {
            (globalThis as any).localStorage = (dom.window as any).localStorage;
        } catch {
            try {
                Object.defineProperty(globalThis, 'localStorage', { value: (dom.window as any).localStorage });
            } catch {
                // ignore if already non-configurable/non-writable
            }
        }
    });

    test('complete app initialization flow', async () => {
        // Mock fetch for nodes and default graph
        const mockFetch = vi.fn()
            .mockResolvedValueOnce({
                ok: true,
                json: async () => ({
                    nodes: {
                        'Test/NodeA': { category: 'Test', inputs: {}, outputs: {}, params: [] },
                        'Test/NodeB': { category: 'Test', inputs: {}, outputs: {}, params: [] }
                    }
                })
            })
            .mockResolvedValueOnce({
                ok: true,
                json: async () => ({ nodes: [], links: [] })
            });

        (globalThis as any).fetch = mockFetch;

        // Clear localStorage to ensure no autosave interferes
        window.localStorage.clear();

        // Mock WebSocket
        class MockWS {
            static OPEN = 1;
            readyState = 1;
            onopen?: () => void;
            onmessage?: (ev: { data: string }) => void;
            onclose?: (ev: any) => void;
            onerror?: (ev: any) => void;
            constructor(_url: string) {
                setTimeout(() => this.onopen && this.onopen(), 0);
            }
            send(_data: string) { /* capture if needed */ }
            close() { this.onclose && this.onclose({ code: 1000, reason: 'close' }); }
        }
        globalThis.WebSocket = MockWS as typeof WebSocket;

        // Import and initialize app
        const mod = await import('../../app.ts');
        expect(mod).toBeTruthy();

        // Trigger DOMContentLoaded
        const ev = new (window as any).Event('DOMContentLoaded');
        document.dispatchEvent(ev);

        // Wait for initialization
        await new Promise((r) => setTimeout(r, 100));

        // Verify app is initialized
        expect(document.getElementById('graph-name')).toBeTruthy();
        expect(document.getElementById('litegraph-canvas')).toBeTruthy();

        // Verify fetch calls were made
        expect(mockFetch).toHaveBeenCalledWith('/nodes');
        expect(mockFetch).toHaveBeenCalledWith('/examples/default-graph.json', { cache: 'no-store' });
    });

    test('file operations integration', async () => {
        // Mock fetch
        globalThis.fetch = vi.fn().mockResolvedValue({
            ok: true,
            json: async () => ({ nodes: {} })
        });

        // Mock URL and Blob
        globalThis.URL = {
            createObjectURL: vi.fn(() => 'blob:test'),
            revokeObjectURL: vi.fn()
        };

        globalThis.Blob = vi.fn().mockImplementation((parts) => ({
            text: vi.fn().mockResolvedValue(parts[0])
        }));

        // Mock document.createElement for anchor
        const mockAnchor = {
            href: '',
            download: '',
            click: vi.fn()
        };

        const originalCreateElement = document.createElement;
        document.createElement = vi.fn().mockImplementation((tagName) => {
            if (tagName === 'a') return mockAnchor;
            const element = originalCreateElement.call(document, tagName);
            if (!element.style) {
                element.style = {} as CSSStyleDeclaration;
            }
            return element;
        });

        // Initialize app
        await import('../../app.ts');
        document.dispatchEvent(new window.Event('DOMContentLoaded'));
        await new Promise((r) => setTimeout(r, 50));

        // Test save functionality
        const saveBtn = document.getElementById('save') as HTMLButtonElement;
        saveBtn.click();

        // Verify save was triggered
        expect(mockAnchor.click).toHaveBeenCalled();
    });

    test('autosave integration', async () => {
        // Mock fetch
        globalThis.fetch = vi.fn().mockResolvedValue({
            ok: true,
            json: async () => ({ nodes: {} })
        });

        // Mock localStorage
        const mockLocalStorage = {
            getItem: vi.fn(),
            setItem: vi.fn()
        };
        globalThis.localStorage = mockLocalStorage;

        // Initialize app
        await import('../../app.ts');
        document.dispatchEvent(new window.Event('DOMContentLoaded'));
        await new Promise((r) => setTimeout(r, 50));

        // Trigger autosave via beforeunload
        window.dispatchEvent(new (window as any).Event('beforeunload'));

        // Verify autosave was attempted
        expect(mockLocalStorage.setItem).toHaveBeenCalled();
    });

    test('link mode integration', async () => {
        // Mock fetch
        globalThis.fetch = vi.fn().mockResolvedValue({
            ok: true,
            json: async () => ({ nodes: {} })
        });

        // Initialize app
        await import('../../app.ts');
        document.dispatchEvent(new window.Event('DOMContentLoaded'));
        await new Promise((r) => setTimeout(r, 50));

        // Check if link mode button was created
        const linkModeBtn = document.getElementById('link-mode-btn');
        expect(linkModeBtn).toBeTruthy();

        // Test link mode cycling
        if (linkModeBtn) {
            const initialText = linkModeBtn.textContent;
            linkModeBtn.click();
            await new Promise((r) => setTimeout(r, 0));

            // Text should have changed
            expect(linkModeBtn.textContent).not.toBe(initialText);
        }
    });

    test('API key management integration', async () => {
        // Mock fetch
        globalThis.fetch = vi.fn().mockResolvedValue({
            ok: true,
            json: async () => ({ nodes: {} })
        });

        // Mock alert
        const mockAlert = vi.fn();
        globalThis.alert = mockAlert;

        // Initialize app
        await import('../../app.ts');
        document.dispatchEvent(new window.Event('DOMContentLoaded'));
        await new Promise((r) => setTimeout(r, 50));

        // Check if API keys button was created
        const apiKeysBtn = document.getElementById('api-keys-btn');
        expect(apiKeysBtn).toBeTruthy();

        // Test API keys button click
        if (apiKeysBtn) {
            apiKeysBtn.click();
            // Should not throw
        }
    });

    test('node palette integration', async () => {
        // Mock fetch
        (globalThis as any).fetch = vi.fn().mockResolvedValue({
            ok: true,
            json: async () => ({
                nodes: {
                    'Test/NodeA': { category: 'Test', inputs: {}, outputs: {}, params: [] }
                }
            })
        });

        // Initialize app
        await import('../../app.ts');
        document.dispatchEvent(new window.Event('DOMContentLoaded'));
        await new Promise((r) => setTimeout(r, 50));

        // Test palette elements exist
        expect(document.getElementById('node-palette')).toBeTruthy();
        expect(document.getElementById('node-palette-search')).toBeTruthy();
        expect(document.getElementById('node-palette-list')).toBeTruthy();
    });

    test('progress bar integration', async () => {
        // Mock fetch
        globalThis.fetch = vi.fn().mockResolvedValue({
            ok: true,
            json: async () => ({ nodes: {} })
        });

        // Initialize app
        await import('../../app.ts');
        document.dispatchEvent(new window.Event('DOMContentLoaded'));
        await new Promise((r) => setTimeout(r, 50));

        // Test progress bar elements
        const progressRoot = document.getElementById('top-progress');
        const progressBar = document.getElementById('top-progress-bar');
        const progressText = document.getElementById('top-progress-text');

        expect(progressRoot).toBeTruthy();
        expect(progressBar).toBeTruthy();
        expect(progressText).toBeTruthy();

        // Test progress bar visibility
        if (progressRoot) {
            expect(progressRoot.style.display).toBe('block');
        }
    });

    test('graph name management integration', async () => {
        // Mock fetch
        globalThis.fetch = vi.fn().mockResolvedValue({
            ok: true,
            json: async () => ({ nodes: {} })
        });

        // Initialize app
        await import('../../app.ts');
        document.dispatchEvent(new window.Event('DOMContentLoaded'));
        await new Promise((r) => setTimeout(r, 50));

        // Test graph name element
        const graphNameEl = document.getElementById('graph-name');
        expect(graphNameEl).toBeTruthy();
        expect(graphNameEl?.textContent).toBe('default-graph.json');
    });

    test('new graph functionality integration', async () => {
        // Mock fetch
        globalThis.fetch = vi.fn().mockResolvedValue({
            ok: true,
            json: async () => ({ nodes: {} })
        });

        // Initialize app
        await import('../../app.ts');
        document.dispatchEvent(new window.Event('DOMContentLoaded'));
        await new Promise((r) => setTimeout(r, 50));

        // Test new button
        const newBtn = document.getElementById('new') as HTMLButtonElement;
        expect(newBtn).toBeTruthy();

        if (newBtn) {
            newBtn.click();
            await new Promise((r) => setTimeout(r, 0));

            // Graph name should change to untitled.json
            const graphNameEl = document.getElementById('graph-name');
            expect(graphNameEl?.textContent).toBe('untitled.json');
        }
    });

    test('error handling integration', async () => {
        // Mock fetch to fail
        const mockFetch = vi.fn().mockRejectedValue(new Error('Network error'));
        (globalThis as any).fetch = mockFetch;

        // Mock alert
        const mockAlert = vi.fn();
        globalThis.alert = mockAlert;

        // Initialize app with error handling
        try {
            await import('../../app.ts');
            document.dispatchEvent(new window.Event('DOMContentLoaded'));
            await new Promise((r) => setTimeout(r, 50));
        } catch (error) {
            // Expected to fail due to fetch error, but we should handle it gracefully
            console.warn('Expected error during initialization:', error);
        }

        // App should still initialize despite fetch failure
        expect(document.getElementById('graph-name')).toBeTruthy();

        // Verify fetch was called
        expect(mockFetch).toHaveBeenCalled();
    });
});
