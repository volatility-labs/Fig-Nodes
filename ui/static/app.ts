import { LGraph, LGraphCanvas, LiteGraph } from '@comfyorg/litegraph';
import BaseCustomNode from './nodes/BaseCustomNode';
import { setupWebSocket } from './websocket';
import { setupResize, setupKeyboard, updateStatus } from '@utils/uiUtils';

// For extensibility: To customize error handling, import { showError } from './utils/uiUtils' and reassign it to your custom function, e.g., showError = (msg) => { console.log(msg); alert(msg); };

async function createEditor(container: HTMLElement) {
    try {
        updateStatus('loading', 'Initializing...');

        const graph = new LGraph();
        const canvasElement = container.querySelector('#litegraph-canvas') as HTMLCanvasElement;
        const canvas = new LGraphCanvas(canvasElement, graph);
        // Disable LiteGraph native search box on double click
        (canvas as any).showSearchBox = () => { };

        // Track last mouse position for positioning quick inputs and dropdowns near cursor
        let lastMouseEvent: MouseEvent | null = null;
        canvasElement.addEventListener('mousemove', (e: MouseEvent) => { lastMouseEvent = e; });

        // Make last mouse event accessible for dropdown positioning
        (canvas as any).getLastMouseEvent = () => lastMouseEvent;

        // ComfyUI-like quick prompt to replace LiteGraph default bottom prompt
        const showQuickPrompt = (title: string, value: any, callback: (v: any) => void, options?: any) => {
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
                    if (!Number.isFinite(n)) return; // keep open if invalid
                    out = Math.floor(n);
                }
                if (overlay.parentNode) document.body.removeChild(overlay);
                try { callback(out); } catch { /* no-op */ }
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

            // Position near cursor if we have one
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
        };

        // Override both canvas and LiteGraph prompt hooks
        (canvas as any).prompt = showQuickPrompt;
        (LiteGraph as any).prompt = showQuickPrompt;

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
                } catch {
                    try {
                        const moduleAlt = await import(`./nodes/${data.uiModule}`);
                        NodeClass = moduleAlt.default || NodeClass;
                    } catch {
                        // Fallback to BaseCustomNode if UI module cannot be loaded in this environment
                    }
                }
            }

            const CustomClass = class extends NodeClass { constructor() { super(name, data); } };
            LiteGraph.registerNodeType(name, CustomClass as any);

            const category = data.category || 'Utilities';
            if (!categorizedNodes[category]) categorizedNodes[category] = [];
            categorizedNodes[category].push(name);
            allItems.push({ name, category, description: data.description });
        }

        // Node palette elements and state
        const overlay = document.getElementById('node-palette-overlay') as HTMLDivElement | null;
        const palette = document.getElementById('node-palette') as HTMLDivElement | null;
        const searchInput = document.getElementById('node-palette-search') as HTMLInputElement | null;
        const listContainer = document.getElementById('node-palette-list') as HTMLDivElement | null;

        let paletteVisible = false;
        let selectionIndex = 0;
        let filtered: { name: string; category: string; description?: string }[] = [];
        let lastCanvasPos: [number, number] = [0, 0];

        const updateSelectionHighlight = () => {
            if (!listContainer) return;
            const children = Array.from(listContainer.children) as HTMLElement[];
            children.forEach((el, i) => {
                if (i === selectionIndex) el.classList.add('selected');
                else el.classList.remove('selected');
            });
            const selectedEl = children[selectionIndex];
            if (selectedEl) selectedEl.scrollIntoView({ block: 'nearest' });
        };

        const renderList = (items: typeof allItems) => {
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
        };

        const openPalette = (event?: MouseEvent) => {
            if (!overlay || !palette || !searchInput) return;
            paletteVisible = true;
            overlay.style.display = 'flex';
            selectionIndex = 0;
            filtered = allItems.slice();
            renderList(filtered);
            if (event) {
                const p = canvas.convertEventToCanvasOffset(event) as unknown as number[];
                lastCanvasPos = [p[0], p[1]];
            } else {
                const rect = canvas.canvas.getBoundingClientRect();
                const fakeEvent = { clientX: rect.left + rect.width / 2, clientY: rect.top + rect.height / 2 } as MouseEvent;
                const p = canvas.convertEventToCanvasOffset(fakeEvent) as unknown as number[];
                lastCanvasPos = [p[0], p[1]];
            }
            // Always let CSS center the palette
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
                graph.add(node as any);
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

        document.addEventListener('keydown', (e: KeyboardEvent) => {
            // Handle palette-specific keys
            if (!paletteVisible && e.key === 'Tab' && !(e.target instanceof HTMLInputElement || e.target instanceof HTMLTextAreaElement)) {
                e.preventDefault();
                openPalette();
                return;
            }
            if (paletteVisible) {
                if (e.key === 'Escape') {
                    e.preventDefault();
                    closePalette();
                    return;
                }
                if (e.key === 'ArrowDown') {
                    e.preventDefault();
                    if (filtered.length) selectionIndex = (selectionIndex + 1) % filtered.length;
                    updateSelectionHighlight();
                } else if (e.key === 'ArrowUp') {
                    e.preventDefault();
                    if (filtered.length) selectionIndex = (selectionIndex - 1 + filtered.length) % filtered.length;
                    updateSelectionHighlight();
                } else if (e.key === 'Enter') {
                    e.preventDefault();
                    addSelectedNode();
                }
                return;
            }

            // Handle delete key for selected nodes
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

        // Remove right-click palette opening (native context menu will show)
        canvasElement.addEventListener('contextmenu', (_e: MouseEvent) => {
            // Do not open palette on right-click
            // Allow default context menu or other handlers
        });
        // Helper: find topmost node under event (prefer graph hit-test for accurate title detection)
        const findNodeUnderEvent = (e: MouseEvent): any | null => {
            const p = canvas.convertEventToCanvasOffset(e) as unknown as number[];
            const x = p[0];
            const y = p[1];
            // Prefer graph's hit-test which includes title height and precise bounds
            const getNodeOnPos = (graph as any).getNodeOnPos?.bind(graph);
            if (typeof getNodeOnPos === 'function') {
                try {
                    const nodeAtPos = getNodeOnPos(x, y);
                    if (nodeAtPos) return nodeAtPos;
                } catch { /* fall through to manual scan */ }
            }
            // Fallback: scan using node.isPointInside (uses boundingRect incl. title)
            const nodes = (graph as any)._nodes as any[] || [];
            for (let i = nodes.length - 1; i >= 0; i--) {
                const node = nodes[i];
                if (typeof node.isPointInside === 'function' && node.isPointInside(x, y)) return node;
            }
            return null;
        };

        // Open palette on double-click only when not on a node
        canvasElement.addEventListener('dblclick', (e: MouseEvent) => {
            e.preventDefault();
            e.stopPropagation();
            const node = findNodeUnderEvent(e);
            if (node) {
                if (typeof node.onDblClick === 'function') {
                    try {
                        // Convert event to local node coordinates
                        const canvasPos = canvas.convertEventToCanvasOffset(e) as unknown as number[];
                        const localPos = [canvasPos[0] - node.pos[0], canvasPos[1] - node.pos[1]];
                        const handled = node.onDblClick(e, localPos, canvas);
                        if (handled) return;
                    } catch { }
                }
                // If double-click occurred on a node, do not open the palette
                return;
            }
            // Only open palette when double-clicking empty canvas
            openPalette();
        });

        // Ensure canvas can receive keyboard events by focusing it on click
        canvasElement.addEventListener('click', () => {
            canvasElement.focus();
        });
        // Ensure progress bar is hidden on load
        const progressRoot = document.getElementById('top-progress');
        const progressBar = document.getElementById('top-progress-bar');
        const progressText = document.getElementById('top-progress-text');
        if (progressRoot && progressBar && progressText) {
            progressRoot.style.display = 'none';
            (progressBar as HTMLElement).style.width = '0%';
            progressBar.classList.remove('indeterminate');
            progressText.textContent = '';
        }

        setupWebSocket(graph, canvas);
        setupResize(canvasElement, canvas);
        setupKeyboard(graph);

        document.getElementById('save')?.addEventListener('click', () => {
            const graphData = graph.serialize();
            const blob = new Blob([JSON.stringify(graphData, null, 2)], { type: 'application/json' });
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = 'graph.json';
            a.click();
            URL.revokeObjectURL(url);
        });

        const fileInput = document.getElementById('graph-file') as HTMLInputElement;
        document.getElementById('load')?.addEventListener('click', () => {
            fileInput.click();
        });

        fileInput.addEventListener('change', (event) => {
            const file = (event.target as HTMLInputElement).files?.[0];
            if (file) {
                const reader = new FileReader();
                reader.onload = (e) => {
                    try {
                        const graphData = JSON.parse(e.target?.result as string);
                        graph.configure(graphData);
                        canvas.draw(true);
                    } catch (error) {
                        console.error('Failed to load graph:', error);
                        alert('Invalid graph file');
                    }
                };
                reader.readAsText(file);
            }
        });

        graph.start();
        updateStatus('connected', 'Ready');
    } catch (error) {
        console.error('Failed to initialize editor:', error);
        updateStatus('disconnected', 'Initialization failed');
    }
}

document.addEventListener('DOMContentLoaded', () => {
    const container = document.querySelector('.app-container') as HTMLElement;
    if (container) createEditor(container);
    else console.error('Canvas container not found');
});