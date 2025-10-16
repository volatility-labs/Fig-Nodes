import { describe, expect, test, beforeEach, vi } from 'vitest';
import { UIModuleLoader } from '../../../services/UIModuleLoader';
import { BaseCustomNode } from '../../../nodes';

// Mock dynamic imports
vi.mock('../../../nodes/io/TextInputNodeUI', () => ({ default: class MockTextInputNodeUI { } }));
vi.mock('../../../nodes/io/LoggingNodeUI', () => ({ default: class MockLoggingNodeUI { } }));
vi.mock('../../../nodes/io/SaveOutputNodeUI', () => ({ default: class MockSaveOutputNodeUI { } }));
vi.mock('../../../nodes/io/ExtractSymbolsNodeUI', () => ({ default: class MockExtractSymbolsNodeUI { } }));
vi.mock('../../../nodes/llm/LLMMessagesBuilderNodeUI', () => ({ default: class MockLLMMessagesBuilderNodeUI { } }));
vi.mock('../../../nodes/llm/OllamaChatNodeUI', () => ({ default: class MockOllamaChatNodeUI { } }));
vi.mock('../../../nodes/llm/OpenRouterChatNodeUI', () => ({ default: class MockOpenRouterChatNodeUI { } }));
vi.mock('../../../nodes/llm/SystemPromptLoaderNodeUI', () => ({ default: class MockSystemPromptLoaderNodeUI { } }));
vi.mock('../../../nodes/market/ADXFilterNodeUI', () => ({ default: class MockADXFilterNodeUI { } }));
vi.mock('../../../nodes/market/AtrXFilterNodeUI', () => ({ default: class MockAtrXFilterNodeUI { } }));
vi.mock('../../../nodes/market/AtrXIndicatorNodeUI', () => ({ default: class MockAtrXIndicatorNodeUI { } }));
vi.mock('../../../nodes/market/PolygonBatchCustomBarsNodeUI', () => ({ default: class MockPolygonBatchCustomBarsNodeUI { } }));
vi.mock('../../../nodes/market/PolygonCustomBarsNodeUI', () => ({ default: class MockPolygonCustomBarsNodeUI { } }));
vi.mock('../../../nodes/market/PolygonUniverseNodeUI', () => ({ default: class MockPolygonUniverseNodeUI { } }));
vi.mock('../../../nodes/market/RSIFilterNodeUI', () => ({ default: class MockRSIFilterNodeUI { } }));
vi.mock('../../../nodes/market/SMACrossoverFilterNodeUI', () => ({ default: class MockSMACrossoverFilterNodeUI { } }));
vi.mock('../../../nodes/base/StreamingCustomNode', () => ({ default: class MockStreamingCustomNode { } }));
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

    test('loadUIModule returns cached module', async () => {
        const mockModule = { default: class MockNode { } };
        (uiModuleLoader as any).uiModules['test/module'] = mockModule.default;

        const result = await uiModuleLoader.loadUIModule('test/module');

        expect(result).toBe(mockModule.default);
    });

    test('loadUIModule loads module dynamically', async () => {
        // Test with a mocked static module
        const result = await uiModuleLoader.loadUIModule('TextInput');

        expect(result).toBeDefined();
        expect(typeof result).toBe('function');
    });

    test('loadUIModule falls back to BaseCustomNode on import error', async () => {
        const consoleSpy = vi.spyOn(console, 'warn').mockImplementation(() => { });

        const result = await uiModuleLoader.loadUIModule('nonexistent/module');

        expect(result).toBe(BaseCustomNode);
        expect(consoleSpy).toHaveBeenCalledWith(
            'Failed to load UI module nonexistent/module:',
            expect.any(Error)
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
                params: [],
                uiModule: 'custom/CustomNodeUI'
            }
        };

        mockFetch.mockResolvedValue({
            ok: true,
            json: async () => ({ nodes: mockMetadata })
        });

        // Mock UI module loading
        const mockUIModule = class MockCustomNode { };
        vi.spyOn(uiModuleLoader, 'loadUIModule').mockResolvedValue(mockUIModule);

        const result = await uiModuleLoader.registerNodes();

        expect(mockFetch).toHaveBeenCalledWith('/nodes');
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

        expect(result.categorizedNodes.Utilities).toEqual(['UncategorizedNode']);
    });

    test('registerNodes creates custom class with UI module', async () => {
        const mockMetadata = {
            'CustomNode': {
                category: 'Test',
                inputs: {},
                outputs: {},
                params: [],
                uiModule: 'custom/CustomNodeUI'
            }
        };

        mockFetch.mockResolvedValue({
            ok: true,
            json: async () => ({ nodes: mockMetadata })
        });

        const mockUIModule = class MockCustomNode { };
        vi.spyOn(uiModuleLoader, 'loadUIModule').mockResolvedValue(mockUIModule);

        await uiModuleLoader.registerNodes();

        expect(uiModuleLoader.loadUIModule).toHaveBeenCalledWith('custom/CustomNodeUI');
        expect((globalThis as any).LiteGraph.registerNodeType).toHaveBeenCalledWith(
            'CustomNode',
            expect.any(Function)
        );
    });

    test('registerNodes falls back to BaseCustomNode when UI module fails', async () => {
        const mockMetadata = {
            'CustomNode': {
                category: 'Test',
                inputs: {},
                outputs: {},
                params: [],
                uiModule: 'custom/CustomNodeUI'
            }
        };

        mockFetch.mockResolvedValue({
            ok: true,
            json: async () => ({ nodes: mockMetadata })
        });

        vi.spyOn(uiModuleLoader, 'loadUIModule').mockResolvedValue(null);

        const consoleSpy = vi.spyOn(console, 'warn').mockImplementation(() => { });

        await uiModuleLoader.registerNodes();

        expect(consoleSpy).toHaveBeenCalledWith('UI module custom/CustomNodeUI not found');
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

    test('initializeStaticModules loads static UI modules', async () => {
        // Create new instance to trigger initializeStaticModules
        const loader = new UIModuleLoader(null as any);

        // Wait for static modules to load
        await new Promise(resolve => setTimeout(resolve, 10));

        // Verify that static modules are loaded (they should be cached)
        expect((loader as any).uiModules['TextInput']).toBeDefined();
        expect((loader as any).uiModules['Logging']).toBeDefined();
        expect((loader as any).uiModules['OllamaChat']).toBeDefined();
    });
});
