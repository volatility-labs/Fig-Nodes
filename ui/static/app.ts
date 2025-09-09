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

        const response = await fetch('/nodes');
        if (!response.ok) throw new Error(`Failed to fetch nodes: ${response.statusText}`);
        const meta = await response.json();

        const categorizedNodes: { [key: string]: string[] } = {};
        const allItems: { name: string; category: string; description?: string }[] = [];
        for (const name in meta.nodes) {
            const data = meta.nodes[name];
            let NodeClass = BaseCustomNode;

            if (data.uiModule) {
                const module = await import(`./nodes/${data.uiModule}.ts`);
                NodeClass = module.default;
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
            if (!paletteVisible && e.key === 'Tab' && !(e.target instanceof HTMLInputElement || e.target instanceof HTMLTextAreaElement)) {
                e.preventDefault();
                openPalette();
                return;
            }
            if (!paletteVisible) return;
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
        });

        // Open palette on right-click within canvas
        canvasElement.addEventListener('contextmenu', (e: MouseEvent) => {
            e.preventDefault();
            openPalette(e);
        });
        // Open palette on double-click within canvas
        canvasElement.addEventListener('dblclick', (e: MouseEvent) => {
            e.preventDefault();
            e.stopPropagation();
            openPalette(e);
        });
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
