import { describe, expect, test, beforeEach, vi } from 'vitest';
import { FileManager } from '../../../services/FileManager';

describe('FileManager', () => {
    let fileManager: FileManager;
    let mockGraph: any;
    let mockCanvas: any;
    let mockFetch: ReturnType<typeof vi.fn>;

    beforeEach(() => {
        mockGraph = {
            serialize: vi.fn(() => ({ nodes: [], links: [] })),
            configure: vi.fn(),
            clear: vi.fn()
        };

        mockCanvas = {
            draw: vi.fn(),
            links_render_mode: 0
        };

        fileManager = new FileManager(mockGraph, mockCanvas);

        mockFetch = vi.fn();
        (globalThis as any).fetch = mockFetch;

        // Mock DOM elements
        const mockElement = {
            addEventListener: vi.fn(),
            click: vi.fn(),
            files: null
        };

        document.getElementById = vi.fn().mockImplementation((id) => {
            if (id === 'save' || id === 'load' || id === 'graph-file') {
                return mockElement as any;
            }
            if (id === 'graph-name') {
                return { textContent: '' } as any;
            }
            return null;
        });

        // Mock URL and Blob
        (globalThis as any).URL = {
            createObjectURL: vi.fn(() => 'blob:mock'),
            revokeObjectURL: vi.fn()
        };

        (globalThis as any).Blob = vi.fn().mockImplementation((parts) => ({
            text: vi.fn().mockResolvedValue(parts[0])
        }));

        // Mock localStorage
        const mockLocalStorage = {
            getItem: vi.fn(),
            setItem: vi.fn()
        };
        (globalThis as any).localStorage = mockLocalStorage;

        // Mock window functions
        (window as any).linkModeManager = {
            restoreFromGraphConfig: vi.fn()
        };
    });

    test('initializes with correct default values', () => {
        expect(fileManager.getCurrentGraphName()).toBe('untitled.json');
        expect(fileManager.getLastSavedGraphJson()).toBe('');
    });

    test('setupFileHandling registers event listeners', () => {
        fileManager.setupFileHandling();

        expect(document.getElementById).toHaveBeenCalledWith('save');
        expect(document.getElementById).toHaveBeenCalledWith('load');
        expect(document.getElementById).toHaveBeenCalledWith('graph-file');
    });

    test('saveGraph creates download link with current graph name', () => {
        const mockAnchor = {
            href: '',
            download: '',
            click: vi.fn()
        };

        document.createElement = vi.fn().mockImplementation((tagName) => {
            if (tagName === 'a') return mockAnchor;
            return {} as any;
        });

        fileManager.updateGraphName('test-graph.json');
        fileManager.saveGraph();

        expect(mockGraph.serialize).toHaveBeenCalled();
        expect(mockAnchor.download).toBe('test-graph.json');
        expect(mockAnchor.click).toHaveBeenCalled();
    });

    test('loadGraph processes file content correctly', async () => {
        const mockFile = {
            name: 'test.json',
            text: vi.fn().mockResolvedValue('{"nodes": [], "links": []}')
        };

        await fileManager.loadGraph(mockFile as any);

        expect(mockGraph.configure).toHaveBeenCalledWith({ nodes: [], links: [] });
        expect(mockCanvas.draw).toHaveBeenCalledWith(true);
        expect(fileManager.getCurrentGraphName()).toBe('test.json');
    });

    test('loadGraph handles FileReader fallback', async () => {
        const mockFile = {
            name: 'test.json',
            text: undefined // No text method
        };

        const mockReader = {
            onload: null as ((event: any) => void) | null,
            readAsText: vi.fn()
        };

        (globalThis as any).FileReader = vi.fn().mockImplementation(() => mockReader);

        // Mock the onload callback
        setTimeout(() => {
            if (mockReader.onload) {
                mockReader.onload({ target: { result: '{"nodes": [], "links": []}' } } as any);
            }
        }, 0);

        await fileManager.loadGraph(mockFile as any);

        expect(mockReader.readAsText).toHaveBeenCalledWith(mockFile);
    });

    test('loadGraph handles invalid JSON gracefully', async () => {
        const mockFile = {
            name: 'invalid.json',
            text: vi.fn().mockResolvedValue('invalid json')
        };

        const mockAlert = vi.fn();
        (globalThis as any).alert = mockAlert;

        await fileManager.loadGraph(mockFile as any);

        expect(mockAlert).toHaveBeenCalledWith('Invalid graph file');
    });

    test('loadGraph checks for missing API keys after load', async () => {
        const mockFile = {
            name: 'test.json',
            text: vi.fn().mockResolvedValue('{"nodes": [{"type": "TestNode"}], "links": []}')
        };

        mockFetch
            .mockResolvedValueOnce({
                ok: true,
                json: async () => ({
                    nodes: { 'TestNode': { required_keys: ['API_KEY'] } }
                })
            })
            .mockResolvedValueOnce({
                ok: true,
                json: async () => ({
                    keys: { 'API_KEY': '' }
                })
            });

        const mockAlert = vi.fn();
        (globalThis as any).alert = mockAlert;

        // Mock APIKeyManager.openSettings
        const mockOpenSettings = vi.fn();
        (fileManager as any).apiKeyManager = {
            getRequiredKeysForGraph: vi.fn().mockResolvedValue(['API_KEY']),
            checkMissingKeys: vi.fn().mockResolvedValue(['API_KEY']),
            openSettings: mockOpenSettings
        };

        await fileManager.loadGraph(mockFile as any);

        expect(mockAlert).toHaveBeenCalledWith('Missing API keys for this graph: API_KEY. Please set them in the settings menu.');
        expect(mockOpenSettings).toHaveBeenCalledWith(['API_KEY']);
    });

    test('updateGraphName updates internal state and DOM', () => {
        const mockGraphNameEl = { textContent: '' };
        document.getElementById = vi.fn().mockReturnValue(mockGraphNameEl as any);

        fileManager.updateGraphName('new-graph.json');

        expect(fileManager.getCurrentGraphName()).toBe('new-graph.json');
        expect(mockGraphNameEl.textContent).toBe('new-graph.json');
    });

    test('setLastSavedGraphJson updates internal state', () => {
        const json = '{"nodes": [], "links": []}';

        fileManager.setLastSavedGraphJson(json);

        expect(fileManager.getLastSavedGraphJson()).toBe(json);
    });

    test('doAutosave saves when graph has changed', () => {
        const mockLocalStorage = {
            setItem: vi.fn()
        };
        (globalThis as any).localStorage = mockLocalStorage;

        const graphData = { nodes: [{ id: 1 }], links: [] };
        mockGraph.serialize.mockReturnValue(graphData);

        fileManager.doAutosave();

        expect(mockLocalStorage.setItem).toHaveBeenCalledWith(
            'fig-nodes:autosave:v1',
            JSON.stringify({ graph: graphData, name: 'untitled.json' })
        );
    });

    test('doAutosave skips save when graph unchanged', () => {
        const mockLocalStorage = {
            setItem: vi.fn()
        };
        (globalThis as any).localStorage = mockLocalStorage;

        const graphData = { nodes: [], links: [], extra: { linkRenderMode: 0 } };
        mockGraph.serialize.mockReturnValue(graphData);

        // Set the same JSON as last saved (matching the graph data format used by doAutosave)
        fileManager.setLastSavedGraphJson(JSON.stringify(graphData));

        fileManager.doAutosave();

        expect(mockLocalStorage.setItem).not.toHaveBeenCalled();
    });

    test('doAutosave handles serialization errors gracefully', () => {
        const mockLocalStorage = {
            setItem: vi.fn()
        };
        (globalThis as any).localStorage = mockLocalStorage;

        mockGraph.serialize.mockImplementation(() => {
            throw new Error('Serialization failed');
        });

        // Should not throw
        expect(() => fileManager.doAutosave()).not.toThrow();
    });

    test('restoreFromAutosave restores valid autosave data', async () => {
        const mockLocalStorage = {
            getItem: vi.fn().mockReturnValue(JSON.stringify({
                graph: { nodes: [{ id: 1 }], links: [] },
                name: 'autosave.json'
            }))
        };
        (globalThis as any).localStorage = mockLocalStorage;

        const result = await fileManager.restoreFromAutosave();

        expect(result).toBe(true);
        expect(mockGraph.configure).toHaveBeenCalledWith({ nodes: [{ id: 1 }], links: [] });
        expect(mockCanvas.draw).toHaveBeenCalledWith(true);
        expect(fileManager.getCurrentGraphName()).toBe('autosave.json');
    });

    test('restoreFromAutosave returns false for invalid data', async () => {
        const mockLocalStorage = {
            getItem: vi.fn().mockReturnValue('invalid json')
        };
        (globalThis as any).localStorage = mockLocalStorage;

        const result = await fileManager.restoreFromAutosave();

        expect(result).toBe(false);
    });

    test('restoreFromAutosave returns false for missing data', async () => {
        const mockLocalStorage = {
            getItem: vi.fn().mockReturnValue(null)
        };
        (globalThis as any).localStorage = mockLocalStorage;

        const result = await fileManager.restoreFromAutosave();

        expect(result).toBe(false);
    });

    test('restoreFromAutosave handles configuration errors gracefully', async () => {
        const mockLocalStorage = {
            getItem: vi.fn().mockReturnValue(JSON.stringify({
                graph: { nodes: [{ id: 1 }], links: [] },
                name: 'autosave.json'
            }))
        };
        (globalThis as any).localStorage = mockLocalStorage;

        mockGraph.configure.mockImplementation(() => {
            throw new Error('Configuration failed');
        });

        const result = await fileManager.restoreFromAutosave();

        // Should still return true since we consider it restored
        expect(result).toBe(true);
        expect(fileManager.getCurrentGraphName()).toBe('autosave.json');
    });

    test('restoreFromAutosave restores link mode from graph config', async () => {
        const mockLocalStorage = {
            getItem: vi.fn().mockReturnValue(JSON.stringify({
                graph: {
                    nodes: [],
                    links: [],
                    config: { linkRenderMode: 1 }
                },
                name: 'autosave.json'
            }))
        };
        (globalThis as any).localStorage = mockLocalStorage;

        await fileManager.restoreFromAutosave();

        expect((window as any).linkModeManager.restoreFromGraphConfig).toHaveBeenCalledWith({
            nodes: [],
            links: [],
            config: { linkRenderMode: 1 }
        });
    });

    test('safeLocalStorageSet handles storage errors', () => {
        const mockLocalStorage = {
            setItem: vi.fn().mockImplementation(() => {
                throw new Error('Storage quota exceeded');
            })
        };
        (globalThis as any).localStorage = mockLocalStorage;

        const consoleSpy = vi.spyOn(console, 'error').mockImplementation(() => { });

        (fileManager as any).safeLocalStorageSet('key', 'value');

        expect(consoleSpy).toHaveBeenCalledWith('Autosave failed:', expect.any(Error));

        consoleSpy.mockRestore();
    });

    test('safeLocalStorageGet handles storage errors', () => {
        const mockLocalStorage = {
            getItem: vi.fn().mockImplementation(() => {
                throw new Error('Storage access denied');
            })
        };
        (globalThis as any).localStorage = mockLocalStorage;

        const result = (fileManager as any).safeLocalStorageGet('key');

        expect(result).toBeNull();
    });
});
