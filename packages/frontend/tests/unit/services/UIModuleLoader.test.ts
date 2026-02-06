import { describe, expect, test, beforeEach, vi } from 'vitest';
import { UIModuleLoader } from '../../../services/UIModuleLoader';
import { BaseCustomNode } from '../../../nodes';

vi.mock('../../../nodes', () => ({
    BaseCustomNode: class MockBaseCustomNode {
        constructor(public name: string, public data: any) { }
    }
}));

describe('UIModuleLoader', () => {
    let uiModuleLoader: UIModuleLoader;
    let mockFetch: ReturnType<typeof vi.fn>;

    beforeEach(() => {
        uiModuleLoader = new UIModuleLoader(null as any);

        mockFetch = vi.fn();
        (globalThis as any).fetch = mockFetch;

        // Mock LiteGraph
        const mockRegistry = new Map();
        (globalThis as any).LiteGraph = {
            registerNodeType: vi.fn((name, klass) => {
                mockRegistry.set(name, klass);
            }),
            _registry: mockRegistry
        };

    });

    test('loadUIModuleByPath returns cached module', async () => {
        const mockModule = { default: class MockNode { } };
        (uiModuleLoader as any).uiModules['TestNodeNodeUI'] = mockModule.default;

        const result = await (uiModuleLoader as any).loadUIModuleByPath('TestNodeNodeUI');

        expect(result).toBe(mockModule.default);
    });

    test('loadUIModuleByPath falls back to BaseCustomNode when no module found', async () => {
        const consoleSpy = vi.spyOn(console, 'warn').mockImplementation(() => { });

        const result = await (uiModuleLoader as any).loadUIModuleByPath('NonexistentNodeUI');

        expect(result).toBe(BaseCustomNode);
        expect(consoleSpy).toHaveBeenCalledWith(
            '[UIModuleLoader] No UI module found for path: NonexistentNodeUI'
        );

        consoleSpy.mockRestore();
    });

    test('registerNodes fetches node metadata and registers types', async () => {
        const mockMetadata = {
            'TestNode': {
                category: 'Test',
                inputs: { input: { base: 'str' } },
                outputs: { output: { base: 'str' } },
                params: []
            },
            'CustomNode': {
                category: 'Custom',
                inputs: {},
                outputs: {},
                params: []
            }
        };

        mockFetch.mockResolvedValue({
            ok: true,
            json: async () => ({ nodes: mockMetadata })
        });

        const result = await uiModuleLoader.registerNodes();

        expect(mockFetch).toHaveBeenCalledWith('/api/v1/nodes');
        expect((globalThis as any).LiteGraph.registerNodeType).toHaveBeenCalledTimes(2);
        expect(result.allItems).toHaveLength(2);
        expect(result.categorizedNodes.Test).toEqual(['TestNode']);
        expect(result.categorizedNodes.Custom).toEqual(['CustomNode']);
    });

    test('registerNodes handles fetch errors', async () => {
        mockFetch.mockRejectedValue(new Error('Network error'));

        await expect(uiModuleLoader.registerNodes()).rejects.toThrow('Network error');
    });

    test('registerNodes handles non-OK response', async () => {
        mockFetch.mockResolvedValue({
            ok: false,
            statusText: 'Not Found'
        });

        await expect(uiModuleLoader.registerNodes()).rejects.toThrow('Failed to fetch nodes: Not Found');
    });

    test('registerNodes uses default category for nodes without category', async () => {
        const mockMetadata = {
            'UncategorizedNode': {
                inputs: {},
                outputs: {},
                params: []
            }
        };

        mockFetch.mockResolvedValue({
            ok: true,
            json: async () => ({ nodes: mockMetadata })
        });

        const result = await uiModuleLoader.registerNodes();

        expect(result.categorizedNodes.base).toEqual(['UncategorizedNode']);
    });

    test('registerNodes creates custom class with UI module', async () => {
        const mockMetadata = {
            'CustomNode': {
                category: 'Test',
                inputs: {},
                outputs: {},
                params: []
            }
        };

        mockFetch.mockResolvedValue({
            ok: true,
            json: async () => ({ nodes: mockMetadata })
        });

        await uiModuleLoader.registerNodes();

        expect((globalThis as any).LiteGraph.registerNodeType).toHaveBeenCalledWith(
            'CustomNode',
            expect.any(Function)
        );
    });

    test('registerNodes falls back to BaseCustomNode when UI module not found', async () => {
        const mockMetadata = {
            'CustomNode': {
                category: 'Test',
                inputs: {},
                outputs: {},
                params: []
            }
        };

        mockFetch.mockResolvedValue({
            ok: true,
            json: async () => ({ nodes: mockMetadata })
        });

        const consoleSpy = vi.spyOn(console, 'warn').mockImplementation(() => { });

        await uiModuleLoader.registerNodes();

        expect(consoleSpy).toHaveBeenCalledWith('[UIModuleLoader] No UI module found for path: CustomNodeNodeUI');
        expect((globalThis as any).LiteGraph.registerNodeType).toHaveBeenCalledWith(
            'CustomNode',
            expect.any(Function)
        );

        consoleSpy.mockRestore();
    });

    test('registerNodes includes description in allItems', async () => {
        const mockMetadata = {
            'DescribedNode': {
                category: 'Test',
                inputs: {},
                outputs: {},
                params: [],
                description: 'A test node'
            }
        };

        mockFetch.mockResolvedValue({
            ok: true,
            json: async () => ({ nodes: mockMetadata })
        });

        const result = await uiModuleLoader.registerNodes();

        expect(result.allItems[0]).toEqual({
            name: 'DescribedNode',
            category: 'Test',
            description: 'A test node'
        });
    });

    test('getNodeMetadata returns cached metadata', async () => {
        const mockMetadata = { 'TestNode': { category: 'Test' } };
        (uiModuleLoader as any).nodeMetadata = mockMetadata;

        const result = uiModuleLoader.getNodeMetadata();

        expect(result).toBe(mockMetadata);
    });

    test('getNodeMetadata returns null when not loaded', () => {
        const result = uiModuleLoader.getNodeMetadata();

        expect(result).toBeNull();
    });

    test('registerNodes creates proper node registry structure', async () => {
        const mockMetadata = {
            'NodeA': { category: 'CategoryA', inputs: {}, outputs: {}, params: [] },
            'NodeB': { category: 'CategoryB', inputs: {}, outputs: {}, params: [] },
            'NodeC': { category: 'CategoryA', inputs: {}, outputs: {}, params: [] }
        };

        mockFetch.mockResolvedValue({
            ok: true,
            json: async () => ({ nodes: mockMetadata })
        });

        const result = await uiModuleLoader.registerNodes();

        expect(result.categorizedNodes.CategoryA).toEqual(['NodeA', 'NodeC']);
        expect(result.categorizedNodes.CategoryB).toEqual(['NodeB']);
        expect(result.allItems).toHaveLength(3);
    });
});
