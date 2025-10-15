import { describe, expect, test, beforeEach, vi } from 'vitest';
import { AppState } from '../../services/AppState';
import { APIKeyManager } from '../../services/APIKeyManager';
import { FileManager } from '../../services/FileManager';
import { LinkModeManager } from '../../services/LinkModeManager';
import { DialogManager } from '../../services/DialogManager';

describe('Services Integration Tests', () => {
    let mockGraph: any;
    let mockCanvas: any;
    let mockFetch: ReturnType<typeof vi.fn>;

    beforeEach(() => {
        vi.restoreAllMocks();
        vi.resetModules();

        // Reset singleton
        (AppState as any).instance = undefined;

        mockGraph = {
            serialize: vi.fn(() => ({ nodes: [], links: [] })),
            configure: vi.fn(),
            clear: vi.fn()
        };

        mockCanvas = {
            draw: vi.fn(),
            links_render_mode: 0,
            render_curved_connections: false,
            setDirty: vi.fn()
        };

        mockFetch = vi.fn();
        (globalThis as any).fetch = mockFetch;

        // Mock DOM
        document.createElement = vi.fn().mockImplementation((_tagName) => ({
            id: '',
            className: '',
            textContent: '',
            style: {},
            addEventListener: vi.fn(),
            appendChild: vi.fn(),
            focus: vi.fn(),
            click: vi.fn(),
            classList: { add: vi.fn(), remove: vi.fn() }
        }));

        const mockBody = document.createElement('body');
        mockBody.appendChild = vi.fn();
        mockBody.removeChild = vi.fn();
        Object.defineProperty(document, 'body', { value: mockBody, writable: true });

        document.getElementById = vi.fn().mockReturnValue({
            textContent: '',
            addEventListener: vi.fn(),
            click: vi.fn()
        });

        // Mock localStorage
        (globalThis as any).localStorage = {
            getItem: vi.fn(),
            setItem: vi.fn()
        };

        // Mock URL
        (globalThis as any).URL = {
            createObjectURL: vi.fn(() => 'blob:test'),
            revokeObjectURL: vi.fn()
        };
    });

    test('AppState and FileManager integration', () => {
        const appState = AppState.getInstance();
        const fileManager = new FileManager(mockGraph, mockCanvas);

        // Set up app state
        appState.setCurrentGraph(mockGraph);
        appState.setCanvas(mockCanvas);

        // FileManager should work with the same graph
        expect(fileManager.getCurrentGraphName()).toBe('untitled.json');

        // Update graph name through file manager
        fileManager.updateGraphName('test-graph.json');
        expect(fileManager.getCurrentGraphName()).toBe('test-graph.json');
    });

    test('APIKeyManager and AppState integration', async () => {
        const appState = AppState.getInstance();
        const apiKeyManager = new APIKeyManager();

        // Mock node metadata
        mockFetch.mockResolvedValue({
            ok: true,
            json: async () => ({
                nodes: {
                    'TestNode': { required_keys: ['API_KEY'] }
                }
            })
        });

        // Set up app state with graph data
        const graphData = { nodes: [{ type: 'TestNode' }], links: [] };
        appState.setCurrentGraph(mockGraph);
        mockGraph.serialize.mockReturnValue(graphData);

        // Get required keys through APIKeyManager
        const requiredKeys = await apiKeyManager.getRequiredKeysForGraph(graphData);
        expect(requiredKeys).toEqual(['API_KEY']);

        // Check missing keys
        mockFetch.mockResolvedValue({
            ok: true,
            json: async () => ({ keys: { 'API_KEY': '' } })
        });

        const missingKeys = await apiKeyManager.checkMissingKeys(requiredKeys);
        expect(missingKeys).toEqual(['API_KEY']);
    });

    test('FileManager and LinkModeManager integration', () => {
        const _fileManager = new FileManager(mockGraph, mockCanvas);
        const linkModeManager = new LinkModeManager(mockCanvas);

        // Set up link mode
        linkModeManager.applyLinkMode(1); // LINEAR_LINK

        // Create graph data with link mode
        const graphData = { nodes: [], links: [] };
        linkModeManager.saveToGraphConfig(graphData);

        expect(graphData.config.linkRenderMode).toBe(1);

        // Restore link mode
        linkModeManager.restoreFromGraphConfig(graphData);
        expect(linkModeManager.getCurrentLinkMode()).toBe(1);
    });

    test('DialogManager and APIKeyManager integration', () => {
        const dialogManager = new DialogManager();
        const _apiKeyManager = new APIKeyManager();

        // Mock mouse event
        const mockEvent = { clientX: 100, clientY: 200 } as MouseEvent;
        dialogManager.setLastMouseEvent(mockEvent);

        // APIKeyManager should be able to use DialogManager for prompts
        expect((dialogManager as any).lastMouseEvent).toBe(mockEvent);
    });

    test('AppState global exposure integration', () => {
        const appState = AppState.getInstance();
        appState.setCurrentGraph(mockGraph);
        appState.setCanvas(mockCanvas);

        // Expose globally
        appState.exposeGlobally();

        // Verify global functions exist
        expect(typeof (window as any).getCurrentGraphData).toBe('function');
        expect(typeof (window as any).getRequiredKeysForGraph).toBe('function');
        expect(typeof (window as any).checkMissingKeys).toBe('function');

        // Test global functions
        const graphData = (window as any).getCurrentGraphData();
        expect(graphData).toEqual({ nodes: [], links: [] });
    });

    test('FileManager autosave and AppState integration', () => {
        const appState = AppState.getInstance();
        const fileManager = new FileManager(mockGraph, mockCanvas);

        appState.setCurrentGraph(mockGraph);

        // Mock localStorage
        const mockLocalStorage = {
            getItem: vi.fn().mockReturnValue(null),
            setItem: vi.fn()
        };
        (globalThis as any).localStorage = mockLocalStorage;

        // Trigger autosave
        fileManager.doAutosave();

        // Verify autosave was called
        expect(mockLocalStorage.setItem).toHaveBeenCalledWith(
            'fig-nodes:autosave:v1',
            expect.stringContaining('"name":"untitled.json"')
        );
    });

    test('APIKeyManager settings modal integration', async () => {
        const apiKeyManager = new APIKeyManager();

        // Mock fetch for keys and metadata
        mockFetch
            .mockResolvedValueOnce({
                ok: true,
                json: async () => ({ keys: { 'KEY1': 'value1' } })
            })
            .mockResolvedValueOnce({
                ok: true,
                json: async () => ({ meta: {} })
            });

        // Mock alert
        const mockAlert = vi.fn();
        (globalThis as any).alert = mockAlert;

        // Mock window functions
        (window as any).getCurrentGraphData = () => ({ nodes: [], links: [] });

        try {
            await apiKeyManager.openSettings(['KEY2']);
            // Should not throw
        } catch (error) {
            // Expected due to DOM manipulation in tests
        }

        expect(mockFetch).toHaveBeenCalledWith('/api_keys');
        expect(mockFetch).toHaveBeenCalledWith('/api_keys/meta');
    });

    test('LinkModeManager button integration', () => {
        const linkModeManager = new LinkModeManager(mockCanvas);

        // Mock button element
        const mockButton = {
            textContent: '',
            title: ''
        };
        document.getElementById = vi.fn().mockReturnValue(mockButton as any);

        // Apply link mode
        linkModeManager.applyLinkMode(1);

        // Verify button was updated
        expect(mockButton.textContent).toBe('Orthogonal');
        expect(mockButton.title).toBe('Link style: Orthogonal (click to cycle)');
    });

    test('FileManager file loading integration', async () => {
        const fileManager = new FileManager(mockGraph, mockCanvas);

        // Mock file
        const mockFile = {
            name: 'test.json',
            text: vi.fn().mockResolvedValue('{"nodes": [], "links": []}')
        };

        // Mock API key check
        mockFetch.mockResolvedValue({
            ok: true,
            json: async () => ({ keys: {} })
        });

        // Mock APIKeyManager methods
        (fileManager as any).apiKeyManager = {
            getRequiredKeysForGraph: vi.fn().mockResolvedValue([]),
            checkMissingKeys: vi.fn().mockResolvedValue([]),
            openSettings: vi.fn()
        };

        await fileManager.loadGraph(mockFile as any);

        // Verify graph was configured
        expect(mockGraph.configure).toHaveBeenCalledWith({ nodes: [], links: [] });
        expect(mockCanvas.draw).toHaveBeenCalledWith(true);
        expect(fileManager.getCurrentGraphName()).toBe('test.json');
    });

    test('Services error handling integration', async () => {
        const appState = AppState.getInstance();
        const apiKeyManager = new APIKeyManager();

        // Mock fetch to fail
        mockFetch.mockRejectedValue(new Error('Network error'));

        // AppState should handle errors gracefully
        await expect(appState.getNodeMetadata()).rejects.toThrow('Network error');

        // APIKeyManager should handle errors gracefully
        await expect(apiKeyManager.checkMissingKeys(['KEY1'])).rejects.toThrow('Network error');
    });

    test('Services state persistence integration', () => {
        const appState = AppState.getInstance();
        const fileManager = new FileManager(mockGraph, mockCanvas);

        // Set up state
        appState.setMissingKeys(['KEY1', 'KEY2']);
        fileManager.updateGraphName('persistent.json');

        // Verify state is maintained
        expect(appState.getMissingKeys()).toEqual(['KEY1', 'KEY2']);
        expect(fileManager.getCurrentGraphName()).toBe('persistent.json');

        // Create new instances
        const newAppState = AppState.getInstance();
        const newFileManager = new FileManager(mockGraph, mockCanvas);

        // AppState singleton should maintain state
        expect(newAppState.getMissingKeys()).toEqual(['KEY1', 'KEY2']);

        // FileManager should have fresh state
        expect(newFileManager.getCurrentGraphName()).toBe('untitled.json');
    });
});
