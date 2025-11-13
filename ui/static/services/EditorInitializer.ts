import { LGraph, LGraphCanvas, LiteGraph } from '@comfyorg/litegraph';
import { setupWebSocket } from '../websocket';
import { AppState } from './AppState';
import { APIKeyManager } from './APIKeyManager';
import { DialogManager } from './DialogManager';
import { LinkModeManager } from './LinkModeManager';
import { FileManager } from './FileManager';
import { UIModuleLoader } from './UIModuleLoader';
import { ServiceRegistry } from './ServiceRegistry';
import { registerExecutionStatusService } from './ExecutionStatusService';

export function updateStatus(status: 'connected' | 'disconnected' | 'loading' | 'executing', message?: string) {
    const sr: ServiceRegistry | undefined = (window as any).serviceRegistry;
    const statusService = sr?.get?.('statusService') as any;
    if (statusService && typeof statusService.setConnection === 'function') {
        statusService.setConnection(status, message);
    }
}

export interface EditorInstance {
    graph: LGraph;
    canvas: LGraphCanvas;
    linkModeManager: LinkModeManager;
    fileManager: FileManager;
    dialogManager: DialogManager;
    apiKeyManager: APIKeyManager;
    serviceRegistry: ServiceRegistry;
}

export class EditorInitializer {
    private appState: AppState;
    private serviceRegistry: ServiceRegistry;
    private dialogManager: DialogManager;
    private apiKeyManager: APIKeyManager;
    private linkModeManager!: LinkModeManager;

    constructor() {
        this.appState = AppState.getInstance();
        this.serviceRegistry = new ServiceRegistry();
        this.dialogManager = new DialogManager(this.serviceRegistry);
        this.apiKeyManager = new APIKeyManager();
    }

    async createEditor(container: HTMLElement): Promise<EditorInstance> {
        try {
            const statusService = registerExecutionStatusService(this.serviceRegistry);
            statusService.setConnection('loading', 'Initializing...');

            const graph = new LGraph();
            const canvasElement = container.querySelector('#litegraph-canvas') as HTMLCanvasElement;
            const canvas = new LGraphCanvas(canvasElement, graph);
            
            // Configure LiteGraph to make nodes MUCH darker and more visible
            // Override default node colors to be very dark with strong borders
            try {
                // Set lighter blue default node colors
                const originalCreateNode = LiteGraph.createNode;
                LiteGraph.createNode = function(type: string, options?: any) {
                    const node = originalCreateNode.call(this, type, options);
                    // Force lighter blue colors on all nodes
                    if (node) {
                        // Lighter blue-gray background
                        node.bgcolor = '#1a2a3a'; // Lighter blue-gray
                        node.color = '#2a3a4a'; // Lighter blue-gray for title bar
                        // Add border color for better visibility
                        (node as any).boxcolor = '#5a6a7a'; // Lighter gray-blue border
                        (node as any).shape = LiteGraph.BOX_SHAPE;
                    }
                    return node;
                };
            } catch (e) {
                console.warn('Could not override LiteGraph.createNode:', e);
            }
            
            // Override canvas rendering to make ALL nodes lighter blue
            try {
                const originalDraw = (canvas as any).draw;
                if (originalDraw) {
                    (canvas as any).draw = function(...args: any[]) {
                        // Force lighter blue colors on all nodes before drawing
                        if (this.graph && this.graph._nodes) {
                            this.graph._nodes.forEach((node: any) => {
                                // Force lighter blue on all nodes
                                node.bgcolor = '#1a2a3a'; // Lighter blue-gray
                                node.color = '#2a3a4a'; // Lighter blue-gray for title bar
                                // Add visible border
                                if (!(node as any).boxcolor) {
                                    (node as any).boxcolor = '#5a6a7a'; // Lighter gray-blue border
                                }
                                // Ensure node has a visible shape
                                if (!(node as any).shape) {
                                    (node as any).shape = LiteGraph.BOX_SHAPE;
                                }
                            });
                        }
                        // Call original draw
                        return originalDraw.apply(this, args);
                    };
                }
            } catch (e) {
                console.warn('Could not override canvas.draw:', e);
            }
            
            // Function to apply dark styling to a node
            const applyDarkStyling = (node: any) => {
                if (!node) return;
                
                // Lighter blue shade for nodes
                node.bgcolor = '#1a2a3a'; // Lighter blue-gray
                node.color = '#2a3a4a'; // Lighter blue-gray for title bar
                (node as any).boxcolor = '#5a6a7a'; // Lighter gray-blue border
                
                // Override onDrawBackground to ensure lighter blue rendering
                const originalOnDrawBackground = node.onDrawBackground;
                node.onDrawBackground = function(ctx: CanvasRenderingContext2D, canvas: any, pos: [number, number]) {
                    // Draw lighter blue background FIRST
                    ctx.save();
                    ctx.fillStyle = '#1a2a3a'; // Lighter blue-gray background
                    ctx.fillRect(0, 0, this.size[0], this.size[1]);
                    
                    // Draw lighter blue title bar
                    ctx.fillStyle = '#2a3a4a';
                    ctx.fillRect(0, 0, this.size[0], LiteGraph.NODE_TITLE_HEIGHT);
                    
                    // Draw visible border
                    ctx.strokeStyle = '#5a6a7a'; // Lighter gray-blue border
                    ctx.lineWidth = 2;
                    ctx.strokeRect(0, 0, this.size[0], this.size[1]);
                    
                    ctx.restore();
                    
                    // Call original AFTER our dark background (so it can draw on top if needed)
                    if (originalOnDrawBackground && originalOnDrawBackground !== node.onDrawBackground) {
                        try {
                            originalOnDrawBackground.call(this, ctx, canvas, pos);
                        } catch (e) {
                            // Ignore errors from original
                        }
                    }
                };
            };
            
            // Apply dark styling to any existing nodes
            try {
                if (graph._nodes) {
                    graph._nodes.forEach(applyDarkStyling);
                }
            } catch (e) {
                console.warn('Could not apply dark styling to existing nodes:', e);
            }
            
            // Set LiteGraph canvas background to darker center color for better node visibility
            try {
                // Set to darker center color so nodes are more visible
                (canvas as any).background_color = '#0a0f1a'; // Very dark center color
                
                // Try to override clearRect to use our gradient color
                const ctx = canvasElement.getContext('2d');
                if (ctx) {
                    const originalClearRect = ctx.clearRect;
                    ctx.clearRect = function(...args: any[]) {
                        // Instead of clearing, fill with darker center color
                        const savedFill = this.fillStyle;
                        this.fillStyle = '#0a0f1a'; // Very dark center color
                        this.fillRect(...args);
                        this.fillStyle = savedFill;
                    };
                }
            } catch (e) {
                // Fallback: set background color to dark center
                (canvas as any).background_color = '#0a0f1a';
            }
            
            // PixiJS renderer disabled - using CSS-only glassmorphism enhancements instead
            // Suppress native search UI with correctly typed no-op
            canvas.showSearchBox = function (event: MouseEvent, _searchOptions?: unknown): HTMLDivElement {
                event?.preventDefault?.();
                const el = document.createElement('div');
                el.style.display = 'none';
                el.setAttribute('aria-hidden', 'true');
                return el;
            };

            // Override native prompt to use our custom quick input overlay
            const dm = this.dialogManager;
            canvas.prompt = function (labelText: string, defaultValue: string, callback: (value: string | null) => void): HTMLDivElement {
                const maybeNumber = Number(defaultValue);
                const numericOnly = Number.isFinite(maybeNumber);
                try {
                    dm.showQuickValuePrompt(labelText, defaultValue, numericOnly, (val) => {
                        callback(val);
                    });
                } catch {
                    // Fallback: still return a hidden element to satisfy callers
                }
                const el = document.createElement('div');
                el.style.display = 'none';
                el.setAttribute('aria-hidden', 'true');
                return el;
            } as unknown as typeof canvas.prompt;

            // Initialize services
            const linkModeManager = new LinkModeManager(canvas as any);
            const fileManager = new FileManager(graph as any, canvas as any);
            const uiModuleLoader = new UIModuleLoader(this.serviceRegistry);
            this.linkModeManager = linkModeManager;

            // Register services in ServiceRegistry
            this.serviceRegistry.register('graph', graph as any);
            this.serviceRegistry.register('canvas', canvas as any);
            this.serviceRegistry.register('linkModeManager', linkModeManager);
            this.serviceRegistry.register('fileManager', fileManager);
            this.serviceRegistry.register('dialogManager', this.dialogManager);
            this.serviceRegistry.register('apiKeyManager', this.apiKeyManager);
            this.serviceRegistry.register('appState', this.appState);

            // Set up app state
            this.appState.setCurrentGraph(graph as any);
            this.appState.setCanvas(canvas as any);

            // Do not override native prompt; use application dialogs when needed

            // Register nodes and set up palette
            // Proactively warm up node metadata cache so '/nodes' is fetched even if UIModuleLoader is mocked
            try { await this.appState.getNodeMetadata(); } catch { /* ignore in init flow */ }
            const { allItems } = await uiModuleLoader.registerNodes();
            
            // Force VERY dark colors on all existing nodes in the graph (after registration)
            try {
                if (graph._nodes) {
                    graph._nodes.forEach(applyDarkStyling);
                }
            } catch (e) {
                console.warn('Could not darken existing nodes:', e);
            }
            
            // Hook into graph node addition to force dark colors on new nodes
            try {
                const originalAdd = graph.add;
                graph.add = function(node: any) {
                    const result = originalAdd.call(this, node);
                    // Apply dark styling to new node
                    applyDarkStyling(node);
                    return result;
                };
            } catch (e) {
                console.warn('Could not override graph.add:', e);
            }
            
            // Set up periodic check to ensure all nodes stay dark (in case colors get reset)
            try {
                setInterval(() => {
                    if (graph._nodes) {
                        graph._nodes.forEach((node: any) => {
                            // Force lighter blue colors if they've been changed
                            if (node.bgcolor !== '#1a2a3a' && 
                                (node.bgcolor === '#333' || 
                                 node.bgcolor === '#353535' ||
                                 node.bgcolor === '#fff' ||
                                 node.bgcolor === '#ffffff' ||
                                 node.bgcolor === '#0a0a1a' ||
                                 !node.bgcolor)) {
                                applyDarkStyling(node);
                            }
                        });
                    }
                }, 1000); // Check every second
            } catch (e) {
                console.warn('Could not set up periodic node darkening:', e);
            }
            
            const palette = this.setupPalette(allItems, canvas as any, graph as any);

            // Set up event listeners
            this.setupEventListeners(canvasElement, canvas, graph, palette);

            // Set up progress bar
            this.setupProgressBar();

            // Set up WebSocket and other services
            setupWebSocket(graph as any, canvas as any, this.apiKeyManager);
            this.setupResize(canvasElement, canvas as any);

            // Set up file handling
            fileManager.setupFileHandling();

            // Add footer buttons
            this.addFooterButtons();

            // Expose services globally for debugging if needed (avoid relying on globals in production code)
            ; (window as any).serviceRegistry = this.serviceRegistry;
            // Attempt to restore from autosave first; fallback to default graph
            const restoredFromAutosave = await fileManager.restoreFromAutosave();
            if (!restoredFromAutosave) {
                await this.loadDefaultGraph(graph, canvas);
            }

            // Set up autosave
            this.setupAutosave(fileManager);

            // Set up new graph handler
            this.setupNewGraphHandler(graph, canvas, fileManager);

            // Custom start loop that mirrors legacy graph.start() behaviour using RAF
            const graphRunner = this.createGraphRunner(graph);
            (window as any).graphRunner = graphRunner;
            graphRunner.start();
            window.addEventListener('beforeunload', graphRunner.stop);

            // Load persisted link mode preference and apply after all initialization
            linkModeManager.loadFromPreferences();
            linkModeManager.applyLinkMode(linkModeManager.getCurrentLinkMode());

            statusService.setConnection('connected', 'Ready');

            return {
                graph,
                canvas,
                linkModeManager,
                fileManager,
                dialogManager: this.dialogManager,
                apiKeyManager: this.apiKeyManager,
                serviceRegistry: this.serviceRegistry
            };
        } catch (error) {
            const statusService = this.serviceRegistry.get('statusService') as any;
            if (statusService && typeof statusService.setConnection === 'function') {
                statusService.setConnection('disconnected', 'Initialization failed');
            }
            throw error;
        }
    }

    private setupEventListeners(
        canvasElement: HTMLCanvasElement,
        canvas: LGraphCanvas,
        graph: LGraph,
        palette: { openPalette: (event?: MouseEvent) => void; closePalette: () => void; addSelectedNode: () => void; updateSelectionHighlight: () => void; selectionIndex: number; filtered: { name: string; category: string; description?: string }[]; paletteVisible: boolean }
    ): void {
        // Tooltip setup
        const tooltip = document.createElement('div');
        tooltip.className = 'litegraph-tooltip';
        tooltip.style.display = 'none';
        tooltip.style.position = 'absolute';
        tooltip.style.pointerEvents = 'none';
        tooltip.style.background = 'rgba(0, 0, 0, 0.85)';
        tooltip.style.color = 'white';
        tooltip.style.padding = '4px 8px';
        tooltip.style.borderRadius = '4px';
        tooltip.style.font = '12px Arial';
        tooltip.style.zIndex = '1000';
        document.body.appendChild(tooltip);

        canvasElement.addEventListener('mousemove', (e: MouseEvent) => {
            this.dialogManager.setLastMouseEvent(e);

            // Check for slot hover and show tooltip
            const p = canvas.convertEventToCanvasOffset(e) as number[];
            if (!p || !Array.isArray(p) || p.length < 2) return;
            const px = p[0]!;
            const py = p[1]!;
            let hoveringSlot = false;
            graph._nodes.forEach(node => {
                // Check inputs
                node.inputs?.forEach((input, i) => {
                    if (input.tooltip) {
                        const slotPos = node.getConnectionPos(true, i);
                        const dx = px - (slotPos?.[0] ?? 0);
                        const dy = py - (slotPos?.[1] ?? 0);
                        if (dx * dx + dy * dy < 8 * 8) {  // Within ~8px radius
                            tooltip.textContent = input.tooltip;
                            tooltip.style.left = `${e.clientX + 15}px`;
                            tooltip.style.top = `${e.clientY - 15}px`;
                            tooltip.style.display = 'block';
                            hoveringSlot = true;
                        }
                    }
                });
                // Check outputs similarly if needed
                node.outputs?.forEach((output, i) => {
                    if (output.tooltip) {
                        const slotPos = node.getConnectionPos(false, i);
                        const dx = px - (slotPos?.[0] ?? 0);
                        const dy = py - (slotPos?.[1] ?? 0);
                        if (dx * dx + dy * dy < 8 * 8) {
                            tooltip.textContent = output.tooltip;
                            tooltip.style.left = `${e.clientX + 15}px`;
                            tooltip.style.top = `${e.clientY - 15}px`;
                            tooltip.style.display = 'block';
                            hoveringSlot = true;
                        }
                    }
                });
            });
            if (!hoveringSlot) {
                tooltip.style.display = 'none';
            }
        });
        // Do not add non-native methods to canvas

        // Keyboard event handling
        document.addEventListener('keydown', (e: KeyboardEvent) => {
            if (!palette.paletteVisible && e.key === 'Tab' && !(e.target instanceof HTMLInputElement || e.target instanceof HTMLTextAreaElement)) {
                e.preventDefault();
                palette.openPalette();
                return;
            }
            if (palette.paletteVisible) {
                if (e.key === 'Escape') {
                    e.preventDefault();
                    palette.closePalette();
                    return;
                }
                if (e.key === 'ArrowDown') {
                    e.preventDefault();
                    if (palette.filtered.length) palette.selectionIndex = (palette.selectionIndex + 1) % palette.filtered.length;
                    palette.updateSelectionHighlight();
                } else if (e.key === 'ArrowUp') {
                    e.preventDefault();
                    if (palette.filtered.length) palette.selectionIndex = (palette.selectionIndex - 1 + palette.filtered.length) % palette.filtered.length;
                    palette.updateSelectionHighlight();
                } else if (e.key === 'Enter') {
                    e.preventDefault();
                    palette.addSelectedNode();
                }
                return;
            }

            if ((e.key === 'Delete' || e.key === 'Backspace') && !(e.target instanceof HTMLInputElement || e.target instanceof HTMLTextAreaElement)) {
                e.preventDefault();
                const selectedNodes = canvas.selected_nodes || {};
                const nodesToDelete = Object.values(selectedNodes);
                if (nodesToDelete.length > 0) {
                    nodesToDelete.forEach((node) => {
                        graph.remove(node);
                    });
                    canvas.draw(true, true);
                }
            }
        });

        canvasElement.addEventListener('contextmenu', (_e: MouseEvent) => { });

        const findNodeUnderEvent = (e: MouseEvent) => {
            const p = canvas.convertEventToCanvasOffset(e) as number[];
            const x = p[0] ?? 0;
            const y = p[1] ?? 0;
            const getNodeOnPos = graph.getNodeOnPos?.bind(graph);
            if (typeof getNodeOnPos === 'function') {
                try {
                    const nodeAtPos = getNodeOnPos(x, y);
                    if (nodeAtPos) return nodeAtPos;
                } catch { }
            }
            const nodes = graph._nodes || [];
            for (let i = nodes.length - 1; i >= 0; i--) {
                const node = nodes[i];
                if (node && typeof node.isPointInside === 'function' && node.isPointInside(x ?? 0, y ?? 0)) return node;
            }
            return null;
        };

        canvasElement.addEventListener('dblclick', (e: MouseEvent) => {
            e.preventDefault();
            e.stopPropagation();
            const node = findNodeUnderEvent(e);
            if (node) {
                if (typeof node.onDblClick === 'function') {
                    try {
                        const canvasPos = canvas.convertEventToCanvasOffset(e) as number[];
                        if (!canvasPos || !Array.isArray(canvasPos) || canvasPos.length < 2) return;
                        const localPos: [number, number] = [canvasPos[0]! - (node.pos?.[0] ?? 0), canvasPos[1]! - (node.pos?.[1] ?? 0)];
                        // Adjust event to CanvasPointerEvent to satisfy native signature
                        const evt = e as unknown as MouseEvent & { isAdjusted?: boolean };
                        canvas.adjustMouseEvent(evt as unknown as any);
                        // Native onDblClick returns void; do not test truthiness
                        node.onDblClick(evt as unknown as any, localPos, canvas);
                        return;
                    } catch { }
                }
                return;
            }
            palette.openPalette(e);
        });

        canvasElement.addEventListener('click', (e: MouseEvent) => {
            canvasElement.focus();
            // Update mouse position for widget interactions
            this.dialogManager.setLastMouseEvent(e);
        });
    }

    private setupResize(canvasElement: HTMLCanvasElement, canvas: any) {
        const resizeCanvas = () => {
            const rect = canvasElement.parentElement!.getBoundingClientRect();
            const dpr = window.devicePixelRatio || 1;
            if (canvas.canvas.width !== rect.width * dpr || canvas.canvas.height !== rect.height * dpr) {
                canvas.canvas.width = rect.width * dpr;
                canvas.canvas.height = rect.height * dpr;
                canvas.canvas.style.width = `${rect.width}px`;
                canvas.canvas.style.height = `${rect.height}px`;
                const ctx = canvas.canvas.getContext('2d');
                if (ctx) ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
            }
            canvas.draw(true, true);
        };
        window.addEventListener('resize', resizeCanvas);
        resizeCanvas();
    }

    private setupPalette(allItems: { name: string; category: string; description?: string }[], canvas: LGraphCanvas, graph: LGraph) {
        const overlay = document.getElementById('node-palette-overlay') as HTMLDivElement | null;
        const palette = document.getElementById('node-palette') as HTMLDivElement | null;
        const searchInput = document.getElementById('node-palette-search') as HTMLInputElement | null;
        const listContainer = document.getElementById('node-palette-list') as HTMLDivElement | null;

        let paletteVisible = false;
        let selectionIndex = 0;
        let filtered = allItems.slice();
        let lastCanvasPos: [number, number] = [0, 0];

        function updateSelectionHighlight() {
            if (!listContainer) return;
            const children = Array.from(listContainer.children) as HTMLElement[];
            children.forEach((el, i) => {
                if (i === selectionIndex) el.classList.add('selected');
                else el.classList.remove('selected');
            });
            const selectedEl = children[selectionIndex];
            if (selectedEl) selectedEl.scrollIntoView({ block: 'nearest' });
        }

        function renderList(items: typeof allItems) {
            if (!listContainer) return;
            listContainer.innerHTML = '';
            items.forEach((item, idx) => {
                const row = document.createElement('div');
                row.className = 'node-palette-item' + (idx === selectionIndex ? ' selected' : '');
                const title = document.createElement('div');
                title.className = 'node-palette-title';
                title.textContent = item.name;
                const subtitle = document.createElement('div');
                subtitle.className = 'node-palette-subtitle';
                subtitle.textContent = `${item.category}${item.description ? ' — ' + item.description : ''}`;
                row.appendChild(title);
                row.appendChild(subtitle);
                row.addEventListener('mouseenter', () => {
                    selectionIndex = idx;
                    updateSelectionHighlight();
                });
                row.addEventListener('click', () => addSelectedNode());
                listContainer.appendChild(row);
            });
        }

        const openPalette = (event?: MouseEvent) => {
            if (!overlay || !palette || !searchInput) return;
            paletteVisible = true;
            overlay.style.display = 'flex';
            selectionIndex = 0;
            filtered = allItems.slice();
            renderList(filtered);
            if (event) {
                const p = canvas.convertEventToCanvasOffset(event) as unknown as number[];
                lastCanvasPos = [p[0] || 0, p[1] || 0];
            } else {
                const rect = canvas.canvas.getBoundingClientRect();
                const fakeEvent = { clientX: rect.left + rect.width / 2, clientY: rect.top + rect.height / 2 } as MouseEvent;
                const p = canvas.convertEventToCanvasOffset(fakeEvent) as unknown as number[];
                lastCanvasPos = [p[0] || 0, p[1] || 0];
            }
            palette.style.position = '';
            palette.style.left = '';
            palette.style.top = '';
            searchInput.value = '';
            setTimeout(() => searchInput.focus(), 0);
        };

        const closePalette = () => {
            if (!overlay) return;
            paletteVisible = false;
            overlay.style.display = 'none';
        };

        const addSelectedNode = () => {
            const item = filtered[selectionIndex];
            if (!item) return;
            const node = LiteGraph.createNode(item.name);
            if (node) {
                node.pos = [lastCanvasPos[0], lastCanvasPos[1]];
                graph.add(node);
                canvas.draw(true, true);
            }
            closePalette();
        };

        if (overlay) {
            overlay.addEventListener('click', (e) => {
                if (e.target === overlay) closePalette();
            });
        }

        if (searchInput) {
            searchInput.addEventListener('input', () => {
                const q = searchInput.value.trim().toLowerCase();
                selectionIndex = 0;
                if (!q) {
                    filtered = allItems.slice();
                } else {
                    filtered = allItems.filter((x) =>
                        x.name.toLowerCase().includes(q) ||
                        x.category.toLowerCase().includes(q) ||
                        (x.description || '').toLowerCase().includes(q)
                    );
                }
                renderList(filtered);
            });
        }

        return {
            openPalette,
            addSelectedNode,
            get paletteVisible() { return paletteVisible; },
            get selectionIndex() { return selectionIndex; },
            set selectionIndex(val: number) { selectionIndex = val; },
            get filtered() { return filtered; },
            set filtered(val) { filtered = val; },
            closePalette,
            updateSelectionHighlight
        };
    }

    private setupProgressBar(): void {
        const progressRoot = document.getElementById('top-progress');
        const progressBar = document.getElementById('top-progress-bar');
        const progressText = document.getElementById('top-progress-text');
        if (progressRoot && progressBar && progressText) {
            // Keep the top bar visible to display status text; just reset the bar itself
            progressRoot.style.display = 'block';
            (progressBar as HTMLElement).style.width = '0%';
            progressBar.classList.remove('indeterminate');
            // Do not clear progressText here; it is used for status messages
        }
    }

    private addFooterButtons(): void {
        // Add Link Mode toggle and API Keys button to footer center
        const footerCenter = document.querySelector('.footer-center .file-controls');
        if (footerCenter) {
            const linkModeBtn = document.createElement('button');
            linkModeBtn.id = 'link-mode-btn';
            linkModeBtn.className = 'btn-secondary';
            linkModeBtn.addEventListener('click', () => {
                try { this.linkModeManager?.cycleLinkMode(); } catch { /* ignore */ }
            });
            footerCenter.appendChild(linkModeBtn);

            const apiKeysBtn = document.createElement('button');
            apiKeysBtn.id = 'api-keys-btn';
            apiKeysBtn.innerHTML = '🔐';
            apiKeysBtn.className = 'btn-secondary';
            apiKeysBtn.title = 'Manage API keys for external services';
            apiKeysBtn.addEventListener('click', () => this.apiKeyManager.openSettings());
            footerCenter.appendChild(apiKeysBtn);

            // Add Auto-Align button
            const autoAlignBtn = document.createElement('button');
            autoAlignBtn.id = 'auto-align-btn';
            autoAlignBtn.className = 'btn-secondary';
            autoAlignBtn.textContent = 'Align';
            autoAlignBtn.title = 'Automatically align nodes based on graph flow';
            autoAlignBtn.addEventListener('click', () => {
                try {
                    const graph = this.serviceRegistry.get('graph') as LGraph;
                    if (graph) {
                        import('./GraphAutoAlign').then(({ GraphAutoAlign }) => {
                            GraphAutoAlign.alignGraph(graph);
                        }).catch((error) => {
                            console.error('Failed to auto-align graph:', error);
                        });
                    }
                } catch (error) {
                    console.error('Failed to auto-align graph:', error);
                }
            });
            footerCenter.appendChild(autoAlignBtn);

        }
    }

    private async loadDefaultGraph(graph: LGraph, canvas: LGraphCanvas): Promise<void> {
        try {
            const resp = await fetch('/examples/default-graph.json', { cache: 'no-store' });
            if (!resp.ok) throw new Error('Response not OK');
            const json = await resp.json();
            if (json && json.nodes && json.links) {
                graph.configure(json);
                canvas.draw(true);
                const graphNameEl = document.getElementById('graph-name');
                if (graphNameEl) graphNameEl.textContent = 'default-graph.json';
            }
        } catch (e) { /* ignore */ }
    }

    private setupAutosave(fileManager: FileManager): void {
        // Autosave on interval and on unload
        const autosaveInterval = window.setInterval(() => {
            fileManager.doAutosave();
        }, 2000);

        window.addEventListener('beforeunload', () => {
            fileManager.doAutosave();
            window.clearInterval(autosaveInterval);
        });
    }

    private setupNewGraphHandler(graph: LGraph, canvas: LGraphCanvas, fileManager: FileManager): void {
        const newBtn = document.getElementById('new');
        if (newBtn) {
            newBtn.addEventListener('click', () => {
                graph.clear();
                canvas.draw(true);
                fileManager.updateGraphName('untitled.json');
                fileManager.setLastSavedGraphJson('');
                fileManager.doAutosave();
            });
        }
    }

    private createGraphRunner(graph: LGraph) {
        let rafId = 0 as number | 0;
        let running = false;
        let started = false;
        const onStart = () => {
            try { (graph as any).onPlayEvent?.(); } catch { }
            try { (graph as any).sendEventToAllNodes?.('onStart'); } catch { }
            try {
                (graph as any).starttime = (LiteGraph as any).getTime?.() ?? Date.now();
                (graph as any).last_update_time = (graph as any).starttime;
            } catch { }
        };
        const onStop = () => {
            try { (graph as any).onStopEvent?.(); } catch { }
            try { (graph as any).sendEventToAllNodes?.('onStop'); } catch { }
        };
        const step = () => {
            if (!running) return;
            try { (graph as any).onBeforeStep?.(); } catch { }
            try { graph.runStep(1, false); } catch { }
            try { (graph as any).onAfterStep?.(); } catch { }
            rafId = requestAnimationFrame(step);
        };
        const start = () => {
            if (running) return;
            running = true;
            if (!started) { onStart(); started = true; }
            rafId = requestAnimationFrame(step);
        };
        const stop = () => {
            if (!running) return;
            running = false;
            if (rafId) cancelAnimationFrame(rafId);
            onStop();
        };
        return { start, stop, get running() { return running; } };
    }
}
