import { LGraph, LGraphCanvas, LiteGraph } from '@comfyorg/litegraph';
import { setupWebSocket } from '../websocket';
import { setupResize, updateStatus } from '../utils/uiUtils';
import { setupPalette } from '../utils/paletteUtils';
import { AppState } from './AppState';
import { APIKeyManager } from './APIKeyManager';
import { DialogManager } from './DialogManager';
import { LinkModeManager } from './LinkModeManager';
import { FileManager } from './FileManager';
import { UIModuleLoader } from './UIModuleLoader';
import { ServiceRegistry } from './ServiceRegistry';
import type { ExtendedLGraphCanvas, ExtendedLGraph, ExtendedLiteGraph } from '../types/litegraph-extensions';

export interface EditorInstance {
    graph: ExtendedLGraph;
    canvas: ExtendedLGraphCanvas;
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

    constructor() {
        this.appState = AppState.getInstance();
        this.serviceRegistry = new ServiceRegistry();
        this.dialogManager = new DialogManager(this.serviceRegistry);
        this.apiKeyManager = new APIKeyManager();
    }

    async createEditor(container: HTMLElement): Promise<EditorInstance> {
        try {
            updateStatus('loading', 'Initializing...');

            const graph = new LGraph() as unknown as ExtendedLGraph;
            const canvasElement = container.querySelector('#litegraph-canvas') as HTMLCanvasElement;
            const canvas = new LGraphCanvas(canvasElement, graph as any) as unknown as ExtendedLGraphCanvas;
            canvas.showSearchBox = () => { };

            // Initialize services
            const linkModeManager = new LinkModeManager(canvas as any);
            const fileManager = new FileManager(graph as any, canvas as any);
            const uiModuleLoader = new UIModuleLoader(this.serviceRegistry);

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

            // Set up canvas prompt functionality
            this.setupCanvasPrompt(canvas);

            // Register nodes and set up palette
            // Proactively warm up node metadata cache so '/nodes' is fetched even if UIModuleLoader is mocked
            try { await this.appState.getNodeMetadata(); } catch { /* ignore in init flow */ }
            const { allItems } = await uiModuleLoader.registerNodes();
            const palette = setupPalette(allItems, canvas as any, graph as any);

            // Set up event listeners
            this.setupEventListeners(canvasElement, canvas, graph, palette);

            // Set up progress bar
            this.setupProgressBar();

            // Set up WebSocket and other services
            setupWebSocket(graph as any, canvas as any);
            setupResize(canvasElement, canvas as any);

            // Set up file handling
            fileManager.setupFileHandling();

            // Add footer buttons
            this.addFooterButtons();

            // Expose services globally for debugging and external access (before autosave restoration)
            window.linkModeManager = linkModeManager;
            window.dialogManager = this.dialogManager;
            window.openSettings = () => this.apiKeyManager.openSettings();
            this.appState.exposeGlobally();

            // Attempt to restore from autosave first; fallback to default graph
            const restoredFromAutosave = await fileManager.restoreFromAutosave();
            if (!restoredFromAutosave) {
                await this.loadDefaultGraph(graph, canvas, linkModeManager);
            }

            // Set up autosave
            this.setupAutosave(fileManager);

            // Set up new graph handler
            this.setupNewGraphHandler(graph, canvas, fileManager);

            graph.start();

            // Ensure button label reflects current link mode after all initialization
            linkModeManager.applyLinkMode(linkModeManager.getCurrentLinkMode());

            updateStatus('connected', 'Ready');

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
            updateStatus('disconnected', 'Initialization failed');
            throw error;
        }
    }

    private setupCanvasPrompt(canvas: ExtendedLGraphCanvas): void {
        const showQuickPrompt = (
            title: string,
            value: unknown,
            callback: (v: unknown) => void,
            options?: { type?: 'number' | 'text'; input?: 'number' | 'text'; step?: number; min?: number }
        ) => {
            const numericOnly = (options && (options.type === 'number' || options.input === 'number')) || typeof value === 'number';
            this.dialogManager.showQuickValuePrompt(title, String(value ?? ''), numericOnly, (val) => callback(val));
        };

        canvas.prompt = showQuickPrompt;
        (LiteGraph as unknown as ExtendedLiteGraph).prompt = showQuickPrompt;
    }

    private setupEventListeners(
        canvasElement: HTMLCanvasElement,
        canvas: ExtendedLGraphCanvas,
        graph: ExtendedLGraph,
        palette: ReturnType<typeof setupPalette>
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

        let lastMouseEvent: MouseEvent | null = null;

        canvasElement.addEventListener('mousemove', (e: MouseEvent) => {
            lastMouseEvent = e;
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
        canvas.getLastMouseEvent = () => lastMouseEvent;

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
                        const handled = node.onDblClick(e, localPos, canvas);
                        if (handled) return;
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
                window.linkModeManager?.cycleLinkMode();
            });
            footerCenter.appendChild(linkModeBtn);

            const apiKeysBtn = document.createElement('button');
            apiKeysBtn.id = 'api-keys-btn';
            apiKeysBtn.innerHTML = '🔐';
            apiKeysBtn.className = 'btn-secondary';
            apiKeysBtn.title = 'Manage API keys for external services';
            apiKeysBtn.addEventListener('click', () => this.apiKeyManager.openSettings());
            footerCenter.appendChild(apiKeysBtn);
        }
    }

    private async loadDefaultGraph(graph: ExtendedLGraph, canvas: ExtendedLGraphCanvas, linkModeManager: LinkModeManager): Promise<void> {
        try {
            const resp = await fetch('/examples/default-graph.json', { cache: 'no-store' });
            if (!resp.ok) throw new Error('Response not OK');
            const json = await resp.json();
            if (json && json.nodes && json.links) {
                graph.configure(json);
                // Restore link mode if saved
                linkModeManager.restoreFromGraphConfig(json);
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

    private setupNewGraphHandler(graph: ExtendedLGraph, canvas: ExtendedLGraphCanvas, fileManager: FileManager): void {
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
}
