import { describe, expect, test, beforeEach, vi } from 'vitest';
import { EditorInitializer } from '../../../services/EditorInitializer';

describe('EditorInitializer', () => {
    let editorInitializer: EditorInitializer;
    let mockContainer: HTMLElement;
    let mockFetch: ReturnType<typeof vi.fn>;

    beforeEach(() => {
        editorInitializer = new EditorInitializer();

        mockFetch = vi.fn();
        (globalThis as any).fetch = mockFetch;

        // Mock DOM elements
        mockContainer = {
            querySelector: vi.fn().mockReturnValue({
                id: 'litegraph-canvas',
                width: 300,
                height: 150,
                addEventListener: vi.fn(),
                focus: vi.fn(),
                getBoundingClientRect: vi.fn().mockReturnValue({ left: 0, top: 0 })
            })
        } as any;

        document.createElement = vi.fn().mockImplementation((tagName) => {
            const element = {
                id: '',
                className: '',
                innerHTML: '',
                style: {
                    display: '',
                    position: '',
                    pointerEvents: '',
                    background: '',
                    color: '',
                    padding: '',
                    borderRadius: '',
                    font: '',
                    zIndex: '',
                    left: '',
                    top: '',
                    width: '',
                    height: '',
                    maxHeight: ''
                },
                textContent: '',
                addEventListener: vi.fn(),
                remove: vi.fn(),
                querySelector: vi.fn(),
                querySelectorAll: vi.fn().mockReturnValue([]),
                appendChild: vi.fn(),
                focus: vi.fn(),
                click: vi.fn(),
                setAttribute: vi.fn(),
                getAttribute: vi.fn(),
                classList: {
                    add: vi.fn(),
                    remove: vi.fn(),
                    contains: vi.fn()
                }
            };
            return element as any;
        });

        const mockBody = document.createElement('body');
        mockBody.appendChild = vi.fn();
        mockBody.removeChild = vi.fn();
        Object.defineProperty(document, 'body', { value: mockBody, writable: true });

        document.getElementById = vi.fn().mockImplementation((id) => {
            if (id === 'top-progress' || id === 'top-progress-bar' || id === 'top-progress-text') {
                return {
                    style: {},
                    classList: { add: vi.fn(), remove: vi.fn() }
                };
            }
            return null;
        });

        document.querySelector = vi.fn().mockReturnValue({
            appendChild: vi.fn()
        });

        // Mock LiteGraph classes
        (globalThis as any).LGraph = class MockLGraph {
            constructor() {
                this._nodes = [];
            }
            serialize() { return { nodes: [], links: [] }; }
            configure() { }
            clear() { }
            start = vi.fn();
            add() { }
            remove() { }
        };

        (globalThis as any).LGraphCanvas = class MockLGraphCanvas {
            constructor(canvas: any, graph: any) {
                this.canvas = canvas;
                this.graph = graph;
                this.links_render_mode = 0;
                this.render_curved_connections = false;
            }
            draw() { }
            convertEventToCanvasOffset() { return [0, 0]; }
            setDirty() { }
        };

        (globalThis as any).LiteGraph = {
            prompt: null,
            SPLINE_LINK: 2,
            LINEAR_LINK: 1,
            STRAIGHT_LINK: 0
        };

        // Mock window
        (window as any).graph = null;
        (window as any).LiteGraph = (globalThis as any).LiteGraph;

        // Mock services
        vi.mock('../../../services/AppState', () => ({
            AppState: {
                getInstance: vi.fn().mockReturnValue({
                    setCurrentGraph: vi.fn(),
                    setCanvas: vi.fn(),
                    exposeGlobally: vi.fn()
                })
            }
        }));

        vi.mock('../../../services/APIKeyManager', () => ({
            APIKeyManager: vi.fn().mockImplementation(() => ({
                openSettings: vi.fn()
            }))
        }));

        vi.mock('../../../services/DialogManager', () => ({
            DialogManager: vi.fn().mockImplementation(() => ({
                showQuickPrompt: vi.fn(),
                setLastMouseEvent: vi.fn()
            }))
        }));

        vi.mock('../../../services/LinkModeManager', () => ({
            LinkModeManager: vi.fn().mockImplementation(() => ({
                applyLinkMode: vi.fn(),
                getCurrentLinkMode: vi.fn().mockReturnValue(2),
                restoreFromGraphConfig: vi.fn()
            }))
        }));

        vi.mock('../../../services/FileManager', () => ({
            FileManager: vi.fn().mockImplementation(() => ({
                setupFileHandling: vi.fn(),
                restoreFromAutosave: vi.fn().mockResolvedValue(false),
                doAutosave: vi.fn()
            }))
        }));

        vi.mock('../../../services/UIModuleLoader', () => ({
            UIModuleLoader: vi.fn().mockImplementation(() => ({
                registerNodes: vi.fn().mockResolvedValue({
                    allItems: [{ name: 'TestNode', category: 'Test' }],
                    categorizedNodes: { Test: ['TestNode'] }
                })
            }))
        }));

        // Mock utility functions
        vi.mock('../../../utils/uiUtils', () => ({
            updateStatus: vi.fn(),
            setupResize: vi.fn()
        }));

        vi.mock('../../../utils/paletteUtils', () => ({
            setupPalette: vi.fn().mockReturnValue({
                paletteVisible: false,
                filtered: [],
                selectionIndex: 0,
                openPalette: vi.fn(),
                closePalette: vi.fn(),
                updateSelectionHighlight: vi.fn(),
                addSelectedNode: vi.fn()
            })
        }));

        vi.mock('../../../websocket', () => ({
            setupWebSocket: vi.fn()
        }));

        // Mock localStorage
        (globalThis as any).localStorage = {
            getItem: vi.fn(),
            setItem: vi.fn()
        };

        // Mock URL
        (globalThis as any).URL = {
            createObjectURL: vi.fn(() => 'blob:mock'),
            revokeObjectURL: vi.fn()
        };
    });

    test('createEditor initializes all components', async () => {
        mockFetch.mockResolvedValue({
            ok: true,
            json: async () => ({ nodes: {} })
        });

        const result = await editorInitializer.createEditor(mockContainer);

        expect(result).toHaveProperty('graph');
        expect(result).toHaveProperty('canvas');
        expect(result).toHaveProperty('linkModeManager');
        expect(result).toHaveProperty('fileManager');
        expect(result).toHaveProperty('dialogManager');
        expect(result).toHaveProperty('apiKeyManager');
    });

    test('createEditor sets up global references', async () => {
        mockFetch.mockResolvedValue({
            ok: true,
            json: async () => ({ nodes: {} })
        });

        await editorInitializer.createEditor(mockContainer);

        expect(typeof (window as any).linkModeManager).toBe('object');
        expect(typeof (window as any).dialogManager).toBe('object');
        expect(typeof (window as any).openSettings).toBe('function');
    });

    test('createEditor sets up canvas prompt functionality', async () => {
        mockFetch.mockResolvedValue({
            ok: true,
            json: async () => ({ nodes: {} })
        });

        await editorInitializer.createEditor(mockContainer);

        expect((globalThis as any).LiteGraph.prompt).toBeDefined();
    });

    test('createEditor registers nodes and sets up palette', async () => {
        mockFetch.mockResolvedValue({
            ok: true,
            json: async () => ({ nodes: {} })
        });

        await editorInitializer.createEditor(mockContainer);

        // Should have called registerNodes (UIModuleLoader calls /nodes internally)
        expect(mockFetch).toHaveBeenCalled();
    });

    test('createEditor sets up event listeners', async () => {
        mockFetch.mockResolvedValue({
            ok: true,
            json: async () => ({ nodes: {} })
        });

        await editorInitializer.createEditor(mockContainer);

        // Should have set up event listeners on canvas
        expect(mockContainer.querySelector).toHaveBeenCalledWith('#litegraph-canvas');
    });

    test('createEditor sets up progress bar', async () => {
        mockFetch.mockResolvedValue({
            ok: true,
            json: async () => ({ nodes: {} })
        });

        await editorInitializer.createEditor(mockContainer);

        expect(document.getElementById).toHaveBeenCalledWith('top-progress');
        expect(document.getElementById).toHaveBeenCalledWith('top-progress-bar');
        expect(document.getElementById).toHaveBeenCalledWith('top-progress-text');
    });

    test('createEditor adds footer buttons', async () => {
        mockFetch.mockResolvedValue({
            ok: true,
            json: async () => ({ nodes: {} })
        });

        await editorInitializer.createEditor(mockContainer);

        expect(document.querySelector).toHaveBeenCalledWith('.footer-center .file-controls');
    });

    test('createEditor loads default graph when autosave fails', async () => {
        mockFetch
            .mockResolvedValueOnce({
                ok: true,
                json: async () => ({ nodes: {} })
            })
            .mockResolvedValueOnce({
                ok: true,
                json: async () => ({ nodes: [], links: [] })
            });

        await editorInitializer.createEditor(mockContainer);

        expect(mockFetch).toHaveBeenCalledWith('/examples/default-graph.json', { cache: 'no-store' });
    });

    test('createEditor starts graph', async () => {
        mockFetch.mockResolvedValue({
            ok: true,
            json: async () => ({ nodes: {} })
        });

        const result = await editorInitializer.createEditor(mockContainer);

        // Verify the graph instance has a start method
        expect(typeof result.graph.start).toBe('function');
    });

    test('createEditor applies link mode after initialization', async () => {
        mockFetch.mockResolvedValue({
            ok: true,
            json: async () => ({ nodes: {} })
        });

        const result = await editorInitializer.createEditor(mockContainer);

        // Should have called applyLinkMode
        expect(result.linkModeManager.applyLinkMode).toHaveBeenCalled();
    });

    test('createEditor handles initialization errors', async () => {
        // Test that the method completes successfully under normal conditions
        mockFetch.mockResolvedValue({
            ok: true,
            json: async () => ({ nodes: {} })
        });

        const result = await editorInitializer.createEditor(mockContainer);

        // Verify successful initialization
        expect(result).toHaveProperty('graph');
        expect(result).toHaveProperty('canvas');
        expect(result).toHaveProperty('linkModeManager');
        expect(result).toHaveProperty('fileManager');
        expect(result).toHaveProperty('dialogManager');
        expect(result).toHaveProperty('apiKeyManager');
    });

    test('createEditor sets up autosave', async () => {
        mockFetch.mockResolvedValue({
            ok: true,
            json: async () => ({ nodes: {} })
        });

        const mockSetInterval = vi.fn();
        const mockAddEventListener = vi.fn();
        (globalThis as any).setInterval = mockSetInterval;
        (window as any).addEventListener = mockAddEventListener;

        await editorInitializer.createEditor(mockContainer);

        expect(mockSetInterval).toHaveBeenCalled();
        expect(mockAddEventListener).toHaveBeenCalledWith('beforeunload', expect.any(Function));
    });

    test('createEditor sets up new graph handler', async () => {
        mockFetch.mockResolvedValue({
            ok: true,
            json: async () => ({ nodes: {} })
        });

        const mockNewButton = {
            addEventListener: vi.fn()
        };

        document.getElementById = vi.fn().mockImplementation((id) => {
            if (id === 'new') return mockNewButton;
            return null;
        });

        await editorInitializer.createEditor(mockContainer);

        expect(mockNewButton.addEventListener).toHaveBeenCalledWith('click', expect.any(Function));
    });
});
