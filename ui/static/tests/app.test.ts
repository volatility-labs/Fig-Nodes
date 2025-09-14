import { describe, expect, test, vi, beforeEach } from 'vitest';
import { JSDOM } from 'jsdom';

// Import after mocks from setup are applied
import * as uiUtils from '@/utils/uiUtils';

describe('app.ts initialization', () => {
    beforeEach(() => {
        vi.restoreAllMocks();
        // Minimal DOM with required container and canvas
        const dom = new JSDOM(`<!doctype html><html><body>
            <div class="app-container">
              <canvas id="litegraph-canvas" width="300" height="150"></canvas>
              <div id="node-palette-overlay"></div>
              <div id="node-palette"></div>
              <input id="node-palette-search" />
              <div id="node-palette-list"></div>
              <button id="save"></button>
              <input id="graph-file" type="file" />
              <button id="load"></button>
            </div>
        </body></html>`);
        (globalThis as any).document = dom.window.document as any;
        (globalThis as any).window = dom.window as any;
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
});


