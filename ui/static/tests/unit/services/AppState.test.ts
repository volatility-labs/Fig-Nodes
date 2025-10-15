import { describe, expect, test, beforeEach, vi } from 'vitest';
import { AppState } from '../../../services/AppState';

describe('AppState', () => {
    let appState: AppState;

    beforeEach(() => {
        // Reset singleton instance
        (AppState as any).instance = undefined;
        appState = AppState.getInstance();
    });

    test('is singleton', () => {
        const instance1 = AppState.getInstance();
        const instance2 = AppState.getInstance();
        expect(instance1).toBe(instance2);
    });

    test('manages current graph', () => {
        const mockGraph = { serialize: vi.fn(() => ({ nodes: [], links: [] })) } as any;

        expect(appState.getCurrentGraph()).toBeNull();

        appState.setCurrentGraph(mockGraph);
        expect(appState.getCurrentGraph()).toBe(mockGraph);
    });

    test('manages canvas', () => {
        const mockCanvas = { draw: vi.fn() } as any;

        expect(appState.getCanvas()).toBeNull();

        appState.setCanvas(mockCanvas);
        expect(appState.getCanvas()).toBe(mockCanvas);
    });

    test('getCurrentGraphData returns serialized graph data', () => {
        const mockGraph = {
            serialize: vi.fn(() => ({ nodes: [{ id: 1 }], links: [] }))
        } as any;

        appState.setCurrentGraph(mockGraph);
        const data = appState.getCurrentGraphData();

        expect(mockGraph.serialize).toHaveBeenCalled();
        expect(data).toEqual({ nodes: [{ id: 1 }], links: [] });
    });

    test('getCurrentGraphData returns empty data when no graph', () => {
        const data = appState.getCurrentGraphData();
        expect(data).toEqual({ nodes: [], links: [] });
    });

    test('getCurrentGraphData handles serialization errors', () => {
        const mockGraph = {
            serialize: vi.fn(() => { throw new Error('Serialization failed'); })
        } as any;

        appState.setCurrentGraph(mockGraph);
        const data = appState.getCurrentGraphData();

        expect(data).toEqual({ nodes: [], links: [] });
    });

    test('manages missing keys', () => {
        expect(appState.getMissingKeys()).toEqual([]);

        appState.setMissingKeys(['KEY1', 'KEY2']);
        expect(appState.getMissingKeys()).toEqual(['KEY1', 'KEY2']);

        // Test deduplication
        appState.setMissingKeys(['KEY1', 'KEY2', 'KEY1']);
        expect(appState.getMissingKeys()).toEqual(['KEY1', 'KEY2']);
    });

    test('setMissingKeys handles invalid input', () => {
        appState.setMissingKeys(null as any);
        expect(appState.getMissingKeys()).toEqual([]);

        appState.setMissingKeys('invalid' as any);
        expect(appState.getMissingKeys()).toEqual([]);
    });

    test('exposes methods globally', () => {
        const mockGraph = { serialize: vi.fn(() => ({ nodes: [], links: [] })) } as any;
        appState.setCurrentGraph(mockGraph);

        appState.exposeGlobally();

        expect(typeof (window as any).getCurrentGraphData).toBe('function');
        expect(typeof (window as any).getRequiredKeysForGraph).toBe('function');
        expect(typeof (window as any).checkMissingKeys).toBe('function');
        expect(typeof (window as any).setLastMissingKeys).toBe('function');
        expect(typeof (window as any).getLastMissingKeys).toBe('function');
    });

    test('getNodeMetadata fetches and caches metadata', async () => {
        const mockMetadata = { 'TestNode': { category: 'test' } };
        const mockFetch = vi.fn().mockResolvedValue({
            ok: true,
            json: async () => ({ nodes: mockMetadata })
        });
        (globalThis as any).fetch = mockFetch;

        const metadata = await appState.getNodeMetadata();
        expect(metadata).toEqual(mockMetadata);
        expect(mockFetch).toHaveBeenCalledWith('/nodes');

        // Second call should use cache
        const cachedMetadata = await appState.getNodeMetadata();
        expect(cachedMetadata).toEqual(mockMetadata);
        expect(mockFetch).toHaveBeenCalledTimes(1);
    });

    test('getNodeMetadata handles fetch errors', async () => {
        const mockFetch = vi.fn().mockRejectedValue(new Error('Network error'));
        (globalThis as any).fetch = mockFetch;

        await expect(appState.getNodeMetadata()).rejects.toThrow('Network error');
    });

    test('getRequiredKeysForGraph extracts required keys from nodes', async () => {
        const mockMetadata = {
            'NodeA': { required_keys: ['KEY1', 'KEY2'] },
            'NodeB': { required_keys: ['KEY2', 'KEY3'] },
            'NodeC': { category: 'test' } // No required_keys
        };

        const mockFetch = vi.fn().mockResolvedValue({
            ok: true,
            json: async () => ({ nodes: mockMetadata })
        });
        (globalThis as any).fetch = mockFetch;

        const graphData = {
            nodes: [
                { type: 'NodeA' },
                { type: 'NodeB' },
                { type: 'NodeC' },
                { type: 'UnknownNode' } // Not in metadata
            ],
            links: []
        };

        const requiredKeys = await appState.getRequiredKeysForGraph(graphData);
        expect(requiredKeys).toEqual(['KEY1', 'KEY2', 'KEY3']);
    });

    test('checkMissingKeys identifies missing keys', async () => {
        const mockFetch = vi.fn().mockResolvedValue({
            ok: true,
            json: async () => ({
                keys: {
                    'KEY1': 'value1',
                    'KEY2': '',
                    'KEY3': null
                }
            })
        });
        (globalThis as any).fetch = mockFetch;

        const missingKeys = await appState.checkMissingKeys(['KEY1', 'KEY2', 'KEY3', 'KEY4']);
        expect(missingKeys).toEqual(['KEY2', 'KEY3', 'KEY4']);
    });

    test('checkMissingKeys handles fetch errors', async () => {
        const mockFetch = vi.fn().mockRejectedValue(new Error('API error'));
        (globalThis as any).fetch = mockFetch;

        await expect(appState.checkMissingKeys(['KEY1'])).rejects.toThrow('API error');
    });
});
