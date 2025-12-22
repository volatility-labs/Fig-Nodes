import { LGraph, LGraphCanvas, LiteGraph } from '@fig-node/litegraph';
import { setupWebSocket } from '../websocket';
import { AppState } from './AppState';
import { APIKeyManager } from './APIKeyManager';
import { DialogManager } from './DialogManager';
import { LinkModeManager } from './LinkModeManager';
import { AlignModeManager } from './AlignModeManager';
import { FileManager } from './FileManager';
import { UIModuleLoader } from './UIModuleLoader';
import { ServiceRegistry } from './ServiceRegistry';
import { registerExecutionStatusService } from './ExecutionStatusService';
import { ThemeManager } from './ThemeManager';
import { TypeColorRegistry } from './TypeColorRegistry';
import { CanvasScrollbars } from './CanvasScrollbars';
import { PerformanceProfiler } from './PerformanceProfiler';

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
    themeManager: ThemeManager;
    serviceRegistry: ServiceRegistry;
}

export class EditorInitializer {
    private appState: AppState;
    private serviceRegistry: ServiceRegistry;
    private dialogManager: DialogManager;
    private apiKeyManager: APIKeyManager;
    private themeManager: ThemeManager;
    private linkModeManager!: LinkModeManager;
    private alignModeManager!: AlignModeManager;

    constructor() {
        this.appState = AppState.getInstance();
        this.serviceRegistry = new ServiceRegistry();
        this.dialogManager = new DialogManager(this.serviceRegistry);
        this.apiKeyManager = new APIKeyManager();
        this.themeManager = new ThemeManager();
    }

    async createEditor(container: HTMLElement): Promise<EditorInstance> {
        try {
            const statusService = registerExecutionStatusService(this.serviceRegistry);
            statusService.setConnection('loading', 'Initializing...');

            // Set navigation mode to "standard" for proper scroll behavior:
            // - Regular scroll = PAN
            // - Shift + scroll = ZOOM
            LiteGraph.canvasNavigationMode = "standard";
            
            const graph = new LGraph();
            const canvasElement = container.querySelector('#litegraph-canvas') as HTMLCanvasElement;
            const canvas = new LGraphCanvas(canvasElement, graph);
            // Disable LiteGraph's native searchbox to allow our custom palette to work
            canvas.allow_searchbox = false;
            // Suppress native search UI with correctly typed no-op
            canvas.showSearchBox = function (event: MouseEvent, _searchOptions?: unknown): HTMLDivElement {
                event?.preventDefault?.();
                event?.stopPropagation?.();
                const el = document.createElement('div');
                el.style.display = 'none';
                el.style.visibility = 'hidden';
                el.style.opacity = '0';
                el.style.pointerEvents = 'none';
                el.setAttribute('aria-hidden', 'true');
                el.className = 'litegraph litesearchbox'; // Add class so CSS can hide it
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
            const alignModeManager = new AlignModeManager(graph);
            const fileManager = new FileManager(graph as any, canvas as any);
            const uiModuleLoader = new UIModuleLoader(this.serviceRegistry);
            this.linkModeManager = linkModeManager;
            this.alignModeManager = alignModeManager;

            // Apply theme (must be done after canvas creation)
            this.themeManager.applyTheme(canvas, graph);

            // Initialize canvas scrollbars
            const mainContent = container.querySelector('#main-content') as HTMLElement;
            if (mainContent) {
                mainContent.style.position = 'relative';
                const scrollbars = new CanvasScrollbars(canvas, mainContent);
                // Store scrollbars in service registry for cleanup if needed
                this.serviceRegistry.register('canvasScrollbars', scrollbars);
            }

            // Register services in ServiceRegistry
            this.serviceRegistry.register('graph', graph as any);
            this.serviceRegistry.register('canvas', canvas as any);
            this.serviceRegistry.register('linkModeManager', linkModeManager);
            this.serviceRegistry.register('fileManager', fileManager);
            this.serviceRegistry.register('dialogManager', this.dialogManager);
            this.serviceRegistry.register('apiKeyManager', this.apiKeyManager);
            this.serviceRegistry.register('themeManager', this.themeManager);
            this.serviceRegistry.register('appState', this.appState);

            // Set up app state
            this.appState.setCurrentGraph(graph as any);
            this.appState.setCanvas(canvas as any);

            // Do not override native prompt; use application dialogs when needed

            // Register nodes and set up palette
            // Proactively warm up node metadata cache so '/nodes' is fetched even if UIModuleLoader is mocked
            try { await this.appState.getNodeMetadata(); } catch { /* ignore in init flow */ }
            const { allItems } = await uiModuleLoader.registerNodes();
            
            // Initialize TypeColorRegistry after nodes are registered
            const typeColorRegistry = new TypeColorRegistry();
            const nodeMetadata = uiModuleLoader.getNodeMetadata();
            if (nodeMetadata) {
                typeColorRegistry.initialize(nodeMetadata, canvas as any);
            }
            this.serviceRegistry.register('typeColorRegistry', typeColorRegistry);
            
            // Connect ThemeManager with TypeColorRegistry for connector theming
            this.themeManager.setTypeColorRegistry(typeColorRegistry);
            
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
            
            // Set up theme selector
            this.setupThemeSelector(canvas, graph);

            // Expose services globally for debugging if needed (avoid relying on globals in production code)
            ; (window as any).serviceRegistry = this.serviceRegistry;
            
            // Expose performance profiler globally for debugging
            const profiler = PerformanceProfiler.getInstance();
            (window as any).performanceProfiler = profiler;
            
            // Add console commands for profiling
            (window as any).startProfiling = () => {
                profiler.start();
                console.log('✅ Profiling started. Run stopProfiling() to stop and see results.');
            };
            (window as any).stopProfiling = () => {
                profiler.stop();
                profiler.logResults();
            };
            (window as any).getProfilingStats = () => {
                return profiler.getStats();
            };
            (window as any).exportProfilingData = () => {
                const data = profiler.exportData();
                const blob = new Blob([data], { type: 'application/json' });
                const url = URL.createObjectURL(blob);
                const a = document.createElement('a');
                a.href = url;
                a.download = `profiling-${Date.now()}.json`;
                a.click();
                URL.revokeObjectURL(url);
                console.log('📊 Profiling data exported');
            };
            
            console.log('🔍 Performance profiler available. Commands:');
            console.log('  startProfiling() - Start profiling');
            console.log('  stopProfiling() - Stop profiling and show results');
            console.log('  getProfilingStats() - Get current stats');
            console.log('  exportProfilingData() - Export profiling data as JSON');
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
                themeManager: this.themeManager,
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

        // Listen to LiteGraph's empty-double-click event on the DOM canvas element
        // LiteGraph dispatches custom events on the canvas DOM element (canvas.canvas)
        canvasElement.addEventListener('litegraph:canvas', ((e: CustomEvent) => {
            const detail = e.detail as { subType?: string; originalEvent?: MouseEvent };
            if (detail?.subType !== 'empty-double-click') return;
            
            const originalEvent = detail.originalEvent as MouseEvent | undefined;
            if (!originalEvent) return;
            
            // Open palette if clicking on empty space (no node under cursor)
            const node = findNodeUnderEvent(originalEvent);
            if (!node) {
                palette.openPalette(originalEvent);
            }
        }) as EventListener);
        
        // Also keep native dblclick as fallback for cases where LiteGraph's event doesn't fire
        canvasElement.addEventListener('dblclick', (e: MouseEvent) => {
            // Only handle if no node is under the event (empty space)
            const node = findNodeUnderEvent(e);
            if (!node) {
                e.preventDefault();
                e.stopPropagation();
                palette.openPalette(e);
            }
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
            // Check if buttons already exist (e.g., from React component) before creating
            let linkModeBtn = document.getElementById('link-mode-btn') as HTMLButtonElement;
            if (!linkModeBtn) {
                linkModeBtn = document.createElement('button');
            linkModeBtn.id = 'link-mode-btn';
            linkModeBtn.className = 'btn-secondary';
                linkModeBtn.innerHTML = '🔗';
                linkModeBtn.title = 'Link mode';
            footerCenter.appendChild(linkModeBtn);
            }
            // Attach event listener (clone to remove old listeners first)
            const linkModeHandler = () => {
                try { this.linkModeManager?.cycleLinkMode(); } catch { /* ignore */ }
            };
            const newLinkModeBtn = linkModeBtn.cloneNode(true) as HTMLButtonElement;
            linkModeBtn.parentNode?.replaceChild(newLinkModeBtn, linkModeBtn);
            newLinkModeBtn.addEventListener('click', linkModeHandler);

            let apiKeysBtn = document.getElementById('api-keys-btn') as HTMLButtonElement;
            if (!apiKeysBtn) {
                apiKeysBtn = document.createElement('button');
            apiKeysBtn.id = 'api-keys-btn';
            apiKeysBtn.className = 'btn-secondary';
                apiKeysBtn.innerHTML = '🔐';
            apiKeysBtn.title = 'Manage API keys for external services';
            footerCenter.appendChild(apiKeysBtn);
            }
            // Attach event listener (clone to remove old listeners first)
            const apiKeysHandler = () => this.apiKeyManager.openSettings();
            const newApiKeysBtn = apiKeysBtn.cloneNode(true) as HTMLButtonElement;
            apiKeysBtn.parentNode?.replaceChild(newApiKeysBtn, apiKeysBtn);
            newApiKeysBtn.addEventListener('click', apiKeysHandler);

            // Add Auto-Align button (cycles between Align and Compact)
            let autoAlignBtn = document.getElementById('auto-align-btn') as HTMLButtonElement;
            if (!autoAlignBtn) {
                autoAlignBtn = document.createElement('button');
            autoAlignBtn.id = 'auto-align-btn';
            autoAlignBtn.className = 'btn-secondary';
            autoAlignBtn.textContent = 'Align';
            autoAlignBtn.title = 'Layout mode: Align (click to cycle)';
                footerCenter.appendChild(autoAlignBtn);
            }
            // Attach event listener (clone to remove old listeners first)
            const autoAlignHandler = () => {
                try {
                    if (this.alignModeManager) {
                        this.alignModeManager.cycleAlignMode();
                    }
                } catch (error) {
                    console.error('Failed to cycle align mode:', error);
                }
            };
            const newAutoAlignBtn = autoAlignBtn.cloneNode(true) as HTMLButtonElement;
            autoAlignBtn.parentNode?.replaceChild(newAutoAlignBtn, autoAlignBtn);
            newAutoAlignBtn.addEventListener('click', autoAlignHandler);
            autoAlignBtn = newAutoAlignBtn; // Update reference for later use
            
            // Update button label from saved preference
            if (this.alignModeManager) {
                // Use setTimeout to ensure button is in DOM
                setTimeout(() => {
                    const modeName = this.alignModeManager.getModeName();
                    autoAlignBtn.textContent = modeName;
                    autoAlignBtn.title = `Layout mode: ${modeName} (click to cycle)`;
                }, 0);
            }

            // Reset button removed - Fit View button handles this functionality
            // Remove any existing reset button if present
            const existingResetBtn = document.getElementById('reset-charts-btn');
            if (existingResetBtn) {
                existingResetBtn.remove();
            }
        }
    }

    private fitAllNodesToView(graph: LGraph, canvas: LGraphCanvas): void {
        if (!graph._nodes || graph._nodes.length === 0) {
            console.log('No nodes to fit to view');
            return;
        }

        let minX = Infinity;
        let minY = Infinity;
        let maxX = -Infinity;
        let maxY = -Infinity;

        graph._nodes.forEach((node: any) => {
            if (node.pos && node.size) {
                const x = node.pos[0] || 0;
                const y = node.pos[1] || 0;
                const w = node.size[0] || 0;
                const h = node.size[1] || 0;
                
                minX = Math.min(minX, x);
                minY = Math.min(minY, y);
                maxX = Math.max(maxX, x + w);
                maxY = Math.max(maxY, y + h);
            }
        });

        if (!isFinite(minX) || !isFinite(minY) || !isFinite(maxX) || !isFinite(maxY)) {
            console.warn('Could not calculate valid bounds for nodes');
            return;
        }

        const padding = 50;
        const bounds: [number, number, number, number] = [
            minX - padding,
            minY - padding,
            maxX - minX + (padding * 2),
            maxY - minY + (padding * 2)
        ];
        
        console.log('Calculated bounds:', bounds);
        
        if (canvas.animateToBounds && typeof canvas.animateToBounds === 'function') {
            canvas.animateToBounds(bounds, {
                duration: 300,
                zoom: 0.95, // Less aggressive zoom - closer to 1.0 for better view
                easing: 'easeInOutQuad'
            });
            
            // Ensure minimum zoom after animation to keep text visible
            // low_quality threshold is 0.6, so we enforce 0.7 minimum
            setTimeout(() => {
                const ds = (canvas as any).ds;
                if (ds && ds.scale < 0.7) {
                    ds.scale = 0.7;
                    canvas.setDirty(true, true);
                }
            }, 350); // Wait for animation to complete (300ms + buffer)
        } else if (canvas.ds && canvas.ds.fitToBounds && typeof canvas.ds.fitToBounds === 'function') {
            canvas.ds.fitToBounds(bounds, { zoom: 0.95 }); // Less aggressive zoom
            // Ensure minimum zoom to keep text visible (low_quality threshold is 0.6)
            if (canvas.ds.scale < 0.7) {
                canvas.ds.scale = 0.7;
            }
            canvas.setDirty(true, true);
        } else {
            console.warn('No method available to fit bounds to view');
        }
    }

    private setupThemeSelector(canvas: LGraphCanvas, graph: LGraph): void {
        const footerLeft = document.querySelector('.footer-left');
        if (!footerLeft) return;

        // Create theme selector container
        const themeContainer = document.createElement('div');
        themeContainer.className = 'theme-selector';
        themeContainer.style.marginLeft = '12px';
        themeContainer.style.paddingLeft = '12px';
        themeContainer.style.borderLeft = '1px solid var(--theme-border, #30363d)';
        themeContainer.style.display = 'flex';
        themeContainer.style.alignItems = 'center';
        themeContainer.style.gap = '6px';

        const themeLabel = document.createElement('span');
        themeLabel.textContent = 'Theme:';
        themeLabel.style.color = 'var(--theme-text-secondary, #768390)';
        themeLabel.style.fontSize = '11px';
        themeLabel.style.fontFamily = "'Consolas', 'Monaco', 'Courier New', monospace";

        const themeSelect = document.createElement('select');
        themeSelect.id = 'theme-selector';
        themeSelect.className = 'theme-select';
        themeSelect.style.background = 'var(--theme-bg-tertiary, #1c2128)';
        themeSelect.style.border = '1px solid var(--theme-border-secondary, #373e47)';
        themeSelect.style.color = 'var(--theme-text, #adbac7)';
        themeSelect.style.padding = '4px 8px';
        themeSelect.style.borderRadius = '2px';
        themeSelect.style.fontSize = '11px';
        themeSelect.style.fontFamily = "'Consolas', 'Monaco', 'Courier New', monospace";
        themeSelect.style.cursor = 'pointer';
        themeSelect.style.outline = 'none';
        themeSelect.style.minWidth = '140px';

        // Add theme options
        const themes = this.themeManager.getAvailableThemes();
        themes.forEach(theme => {
            const option = document.createElement('option');
            option.value = theme.name;
            option.textContent = theme.displayName;
            themeSelect.appendChild(option);
        });

        // Set current theme
        themeSelect.value = this.themeManager.getCurrentTheme().name;

        // Handle theme change
        themeSelect.addEventListener('change', (e) => {
            const themeName = (e.target as HTMLSelectElement).value;
            this.themeManager.setTheme(themeName);
        });

        // Add hover styles via JavaScript (since CSS variables are dynamic)
        themeSelect.addEventListener('mouseenter', () => {
            themeSelect.style.borderColor = 'var(--theme-accent, #545d68)';
            themeSelect.style.background = 'var(--theme-bg-hover, #22272e)';
        });
        themeSelect.addEventListener('mouseleave', () => {
            themeSelect.style.borderColor = 'var(--theme-border-secondary, #373e47)';
            themeSelect.style.background = 'var(--theme-bg-tertiary, #1c2128)';
        });
        
        // Update theme selector colors when theme changes
        const updateThemeSelectorColors = () => {
            themeSelect.style.background = 'var(--theme-bg-tertiary, #1c2128)';
            themeSelect.style.borderColor = 'var(--theme-border-secondary, #373e47)';
            themeSelect.style.color = 'var(--theme-text, #adbac7)';
            themeLabel.style.color = 'var(--theme-text-secondary, #768390)';
            themeContainer.style.borderLeftColor = 'var(--theme-border, #30363d)';
        };
        
        // Listen for theme changes and update selector styling
        const themeManager = this.themeManager;
        const originalSetTheme = themeManager.setTheme.bind(themeManager);
        themeManager.setTheme = (themeName: string) => {
            originalSetTheme(themeName);
            // Small delay to ensure CSS variables are updated
            setTimeout(updateThemeSelectorColors, 50);
        };

        themeContainer.appendChild(themeLabel);
        themeContainer.appendChild(themeSelect);
        footerLeft.appendChild(themeContainer);
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
        // Increased interval to 10s to prevent lag during heavy graph operations (e.g. scans)
        const autosaveInterval = window.setInterval(() => {
            fileManager.doAutosave();
        }, 10000);

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
