import { LGraph, LGraphCanvas, LiteGraph } from '@comfyorg/litegraph';
import BaseCustomNode from './nodes/BaseCustomNode';
import { setupWebSocket } from './websocket';
import { setupResize, setupKeyboard, updateStatus } from '@utils/uiUtils';
import { setupPalette } from './utils/paletteUtils';

async function createEditor(container: HTMLElement) {
    try {
        updateStatus('loading', 'Initializing...');

        const graph = new LGraph();
        const canvasElement = container.querySelector('#litegraph-canvas') as HTMLCanvasElement;
        const canvas = new LGraphCanvas(canvasElement, graph);
        (canvas as any).showSearchBox = () => { };

        let currentGraphName = 'untitled.json';
        const AUTOSAVE_KEY = 'fig-nodes:autosave:v1';
        let lastSavedGraphJson = '';
        let initialLoadCancelled = false;

        const getGraphName = () => currentGraphName;
        const updateGraphName = (name: string) => {
            currentGraphName = name;
            const graphNameEl = document.getElementById('graph-name');
            if (graphNameEl) graphNameEl.textContent = name;
        };

        const safeLocalStorageSet = (key: string, value: string) => {
            try {
                localStorage.setItem(key, value);
            } catch (err) {
                console.error('Autosave failed:', err);
                updateStatus('disconnected', 'Autosave failed: Check storage settings');
            }
        };
        const safeLocalStorageGet = (key: string): string | null => {
            try { return localStorage.getItem(key); } catch { return null; }
        };
        const doAutosave = () => {
            try {
                const data = graph.serialize();
                const json = JSON.stringify(data);
                if (json !== lastSavedGraphJson) {
                    const payload = { graph: data, name: getGraphName() }; // Removed timestamp
                    safeLocalStorageSet(AUTOSAVE_KEY, JSON.stringify(payload));
                    lastSavedGraphJson = json;
                }
            } catch { }
        };

        let lastMouseEvent: MouseEvent | null = null;
        canvasElement.addEventListener('mousemove', (e: MouseEvent) => { lastMouseEvent = e; });
        (canvas as any).getLastMouseEvent = () => lastMouseEvent;

        function showQuickPrompt(title: string, value: any, callback: (v: any) => void, options?: any) {
            const numericOnly = (options && (options.type === 'number' || options.input === 'number')) || typeof value === 'number';

            const overlay = document.createElement('div');
            overlay.className = 'quick-input-overlay';

            const dialog = document.createElement('div');
            dialog.className = 'quick-input-dialog';

            const label = document.createElement('div');
            label.className = 'quick-input-label';
            label.textContent = title || 'Value';

            const input = document.createElement('input');
            input.className = 'quick-input-field';
            input.type = numericOnly ? 'number' : 'text';
            input.value = (value !== undefined && value !== null) ? String(value) : '';
            if (numericOnly) {
                input.setAttribute('step', options?.step?.toString() || '1');
                input.setAttribute('min', options?.min?.toString() || '0');
            }

            const okButton = document.createElement('button');
            okButton.className = 'quick-input-ok';
            okButton.textContent = 'OK';

            const submit = () => {
                let out: any = input.value;
                if (numericOnly) {
                    const n = Number(out);
                    if (!Number.isFinite(n)) return;
                    out = Math.floor(n);
                }
                if (overlay.parentNode) document.body.removeChild(overlay);
                try { callback(out); } catch { }
            };
            const cancel = () => { if (overlay.parentNode) document.body.removeChild(overlay); };

            okButton.addEventListener('click', submit);
            input.addEventListener('keydown', (ev) => {
                ev.stopPropagation();
                if (ev.key === 'Enter') submit();
                else if (ev.key === 'Escape') cancel();
            });
            overlay.addEventListener('click', (ev) => {
                if (ev.target === overlay) cancel();
            });

            dialog.appendChild(label);
            dialog.appendChild(input);
            dialog.appendChild(okButton);
            overlay.appendChild(dialog);
            document.body.appendChild(overlay);

            const ev = lastMouseEvent;
            if (ev) {
                dialog.style.position = 'absolute';
                dialog.style.left = `${ev.clientX}px`;
                dialog.style.top = `${ev.clientY - 28}px`;
                overlay.style.background = 'transparent';
                (overlay.style as any).pointerEvents = 'none';
                (dialog.style as any).pointerEvents = 'auto';
            }

            input.focus();
            input.select();
        }

        (canvas as any).prompt = showQuickPrompt;
        (LiteGraph as any).prompt = showQuickPrompt;

        const { allItems, categorizedNodes } = await registerNodes();

        const palette = setupPalette(allItems, canvas, graph);

        setupEventListeners(canvasElement, canvas, graph, palette);

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

        setupWebSocket(graph, canvas);
        setupResize(canvasElement, canvas);
        setupKeyboard(graph);

        // Attempt to restore from autosave first; fallback to default graph
        let restoredFromAutosave = false;
        try {
            const saved = safeLocalStorageGet(AUTOSAVE_KEY);
            if (saved) {
                const parsed = JSON.parse(saved);
                if (parsed && Array.isArray(parsed.graph?.nodes) && Array.isArray(parsed.graph?.links)) {
                    // Set name immediately so UI reflects autosave even if configure fails
                    updateGraphName(parsed.name || 'autosave.json');
                    try {
                        graph.configure(parsed.graph);
                    } catch (configError) {
                        // Keep going without throwing; we still consider autosave restored to avoid overwriting with default graph
                        console.error('Failed to configure graph from autosave:', configError);
                    }
                    try { canvas.draw(true); } catch { /* ignore */ }
                    try { lastSavedGraphJson = JSON.stringify(graph.serialize()); } catch { lastSavedGraphJson = ''; }
                    restoredFromAutosave = true;
                }
            }
        } catch {
            restoredFromAutosave = false;
        }

        if (!restoredFromAutosave) {
            try {
                const resp = await fetch('/examples/default-graph.json', { cache: 'no-store' });
                if (!resp.ok) throw new Error('Response not OK');
                const json = await resp.json();
                if (initialLoadCancelled) {
                    // User initiated a new graph before default graph finished loading; skip applying default
                } else if (json && json.nodes && json.links) {
                    graph.configure(json);
                    canvas.draw(true);
                    updateGraphName('default-graph.json');
                    try { lastSavedGraphJson = JSON.stringify(graph.serialize()); } catch { lastSavedGraphJson = ''; }
                }
            } catch (e) { }
        }

        // Autosave on interval and on unload
        const autosaveInterval = window.setInterval(doAutosave, 2000);
        window.addEventListener('beforeunload', () => {
            doAutosave();
            window.clearInterval(autosaveInterval);
        });

        // New graph handler
        const newBtn = document.getElementById('new');
        if (newBtn) {
            newBtn.addEventListener('click', () => {
                initialLoadCancelled = true;
                graph.clear();
                canvas.draw(true);
                updateGraphName('untitled.json');
                lastSavedGraphJson = '';
                doAutosave();
            });
        }

        const setupFileHandling = (graph: LGraph, canvas: LGraphCanvas, updateGraphName: (name: string) => void, getGraphName: () => string) => {
            document.getElementById('save')?.addEventListener('click', () => {
                const graphData = graph.serialize();
                const blob = new Blob([JSON.stringify(graphData, null, 2)], { type: 'application/json' });
                const url = URL.createObjectURL(blob);
                const a = document.createElement('a');
                a.href = url;
                a.download = getGraphName();
                a.click();
                URL.revokeObjectURL(url);
            });

            const fileInput = document.getElementById('graph-file') as HTMLInputElement;
            document.getElementById('load')?.addEventListener('click', () => {
                fileInput.click();
            });

            fileInput.addEventListener('change', async (event) => {
                const file = (event.target as HTMLInputElement).files?.[0];
                if (file) {
                    const processContent = async (content: string) => {
                        try {
                            const graphData = JSON.parse(content);
                            graph.configure(graphData);
                            try { lastSavedGraphJson = JSON.stringify(graph.serialize()); } catch { lastSavedGraphJson = ''; }
                            canvas.draw(true);
                            updateGraphName(file.name);
                        } catch (_error) {
                            try { alert('Invalid graph file'); } catch { /* ignore in tests */ }
                        }
                    };

                    if (typeof (file as any).text === 'function') {
                        const content = await (file as any).text();
                        await processContent(content);
                    } else {
                        const reader = new FileReader();
                        reader.onload = async (e) => { await processContent(e.target?.result as string); };
                        reader.readAsText(file);
                    }
                }
            });
        };

        setupFileHandling(graph, canvas, updateGraphName, getGraphName);

        graph.start();
        updateStatus('connected', 'Ready');
    } catch (error) {
        updateStatus('disconnected', 'Initialization failed');
    }
}

async function registerNodes() {
    const response = await fetch('/nodes');
    if (!response.ok) throw new Error(`Failed to fetch nodes: ${response.statusText}`);
    const meta = await response.json();

    const categorizedNodes: { [key: string]: string[] } = {};
    const allItems: { name: string; category: string; description?: string }[] = [];
    for (const name in meta.nodes) {
        const data = meta.nodes[name];
        let NodeClass = BaseCustomNode;

        if (data.uiModule) {
            try {
                const module = await import(`./nodes/${data.uiModule}.ts`);
                NodeClass = module.default || NodeClass;
            } catch (error) {
                // Silent fail to base class
            }
        }

        const CustomClass = class extends NodeClass { constructor() { super(name, data); } };
        LiteGraph.registerNodeType(name, CustomClass as any);

        const category = data.category || 'Utilities';
        if (!categorizedNodes[category]) categorizedNodes[category] = [];
        categorizedNodes[category].push(name);
        allItems.push({ name, category, description: data.description });
    }
    return { allItems, categorizedNodes };
}

function setupEventListeners(canvasElement: HTMLCanvasElement, canvas: LGraphCanvas, graph: LGraph, palette: ReturnType<typeof setupPalette>) {
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
            const selectedNodes = (canvas as any).selected_nodes || {};
            const nodesToDelete = Object.values(selectedNodes);
            if (nodesToDelete.length > 0) {
                nodesToDelete.forEach((node: any) => {
                    graph.remove(node);
                });
                canvas.draw(true, true);
            }
        }
    });

    canvasElement.addEventListener('contextmenu', (_e: MouseEvent) => { });

    const findNodeUnderEvent = (e: MouseEvent): any | null => {
        const p = canvas.convertEventToCanvasOffset(e) as unknown as number[];
        const x = p[0];
        const y = p[1];
        const getNodeOnPos = (graph as any).getNodeOnPos?.bind(graph);
        if (typeof getNodeOnPos === 'function') {
            try {
                const nodeAtPos = getNodeOnPos(x, y);
                if (nodeAtPos) return nodeAtPos;
            } catch { }
        }
        const nodes = (graph as any)._nodes as any[] || [];
        for (let i = nodes.length - 1; i >= 0; i--) {
            const node = nodes[i];
            if (typeof node.isPointInside === 'function' && node.isPointInside(x, y)) return node;
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
                    const canvasPos = canvas.convertEventToCanvasOffset(e) as unknown as number[];
                    const localPos = [canvasPos[0] - node.pos[0], canvasPos[1] - node.pos[1]];
                    const handled = node.onDblClick(e, localPos, canvas);
                    if (handled) return;
                } catch { }
            }
            return;
        }
        palette.openPalette(e);
    });

    canvasElement.addEventListener('click', () => {
        canvasElement.focus();
    });
}

document.addEventListener('DOMContentLoaded', () => {
    const container = document.querySelector('.app-container') as HTMLElement;
    if (container) createEditor(container);
    else console.error('Canvas container not found');
});