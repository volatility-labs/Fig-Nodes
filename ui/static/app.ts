import { LGraph, LGraphCanvas, LGraphNode, LiteGraph, IContextMenuValue, ContextMenu, } from '@comfyorg/litegraph';
import BaseCustomNode from './nodes/BaseCustomNode';

// Node categories for better organization
const NODE_CATEGORIES = {
    'Data': ['DefaultDataServiceNode', 'BinanceDataProviderNode'],
    'Indicators': ['DefaultIndicatorsNode'],
    'Trading': ['DefaultTradingNode'],
    'Scoring': ['DefaultScoringNode'],
    'Utilities': ['SampleNode', 'UniverseNode']  // Assuming plugins
};

// Assuming LiteGraph is loaded globally or imported correctly

// Status management functions
function updateStatus(status: 'connected' | 'disconnected' | 'loading', message?: string) {
    const indicator = document.getElementById('status-indicator');
    if (indicator) {
        indicator.className = `status-indicator ${status}`;
        indicator.textContent = message || status.charAt(0).toUpperCase() + status.slice(1);
    }
}

// Loading overlay management
function showLoading(show: boolean) {
    const overlay = document.getElementById('loading-overlay');
    if (overlay) {
        overlay.style.display = show ? 'flex' : 'none';
    }
}

// Replace the previous incomplete BaseCustomNode with full definition

// In createEditor, update the loop to handle dynamic imports

// In execute handler, use if (node && node.displayResults)

// ComfyUI style context menu for the canvas
function getCanvasMenuOptions(canvas: LGraphCanvas, graph: LGraph, categorizedNodes: { [key: string]: string[] }): (e: MouseEvent) => void {
    return (e: MouseEvent) => {
        e.preventDefault();
        const options: IContextMenuValue[] = [
            {
                content: "Add Node",
                has_submenu: true,
                callback: (value, options, event, parentMenu) => {
                    const submenu: IContextMenuValue[] = [];
                    for (const category in categorizedNodes) {
                        submenu.push({
                            content: category,
                            has_submenu: true,
                            callback: (value, options, event, parentMenu) => {
                                const subsubmenu: IContextMenuValue[] = [];
                                categorizedNodes[category].forEach((name: string) => {
                                    subsubmenu.push({
                                        content: name,
                                        callback: () => {
                                            const newNode = LiteGraph.createNode(name);
                                            if (newNode && event) {
                                                newNode.pos = canvas.convertEventToCanvasOffset(event as unknown as MouseEvent);
                                                graph.add(newNode as any);
                                            }
                                        }
                                    });
                                });
                                new ContextMenu(subsubmenu, { event, parentMenu });
                            }
                        });
                    }
                    new ContextMenu(submenu, { event, parentMenu });
                }
            },
            { content: "Fit to window", callback: () => canvas.setZoom(1, [0, 0]) }
        ];
        new ContextMenu(options, { event: e, title: "Canvas Menu" });
    };
}

async function createEditor(container: HTMLElement) {
    try {
        showLoading(true);
        updateStatus('loading', 'Initializing...');

        const graph = new LGraph();
        const canvasElement = container.querySelector('#litegraph-canvas') as HTMLCanvasElement;
        const canvas = new LGraphCanvas(canvasElement, graph);

        // Fetch available nodes from backend
        updateStatus('loading', 'Loading nodes...');
        const response = await fetch('/nodes');
        if (!response.ok) {
            throw new Error(`Failed to fetch nodes: ${response.statusText}`);
        }
        const meta = await response.json();

        // Create node to category map
        const nodeToCategory: { [key: string]: string } = {};
        Object.entries(NODE_CATEGORIES).forEach(([cat, nodes]) => {
            nodes.forEach((n: string) => nodeToCategory[n] = cat);
        });

        // Register custom nodes with enhanced features
        for (const name in meta.nodes) {
            const data = meta.nodes[name];
            let NodeClass = BaseCustomNode;

            if (data.uiModule) {
                const module = await import(`./nodes/${data.uiModule}.ts`);
                NodeClass = module.default;
            }

            // Apply metadata flags
            const CustomClass = class extends NodeClass {
                constructor() {
                    super(name, data);
                }
            };

            // @ts-ignore: Dynamic class extension
            LiteGraph.registerNodeType(name, CustomClass);
        }

        // Populate menu with categories
        const nodeList = document.getElementById('node-list') as HTMLUListElement;

        // Group nodes by category
        const categorizedNodes: { [key: string]: string[] } = {};
        for (const name in meta.nodes) {
            const category = nodeToCategory[name] || 'Utilities';
            if (!categorizedNodes[category]) {
                categorizedNodes[category] = [];
            }
            categorizedNodes[category].push(name);
        }

        if (nodeList) {
            nodeList.innerHTML = ''; // Clear existing content

            // Create categorized menu
            for (const category in categorizedNodes) {
                // Add category header
                const categoryHeader = document.createElement('div');
                categoryHeader.className = 'node-category';
                categoryHeader.textContent = category;
                nodeList.appendChild(categoryHeader);

                // Add nodes in category
                categorizedNodes[category].forEach(name => {
                    const li = document.createElement('li');
                    const btn = document.createElement('button');
                    btn.textContent = name;
                    btn.title = meta.nodes[name].description || name;
                    btn.addEventListener('click', () => {
                        const node = LiteGraph.createNode(name);
                        if (node) {
                            node.pos = [Math.random() * 300 + 100, Math.random() * 300 + 100];
                            graph.add(node);
                        }
                    });
                    li.appendChild(btn);
                    nodeList.appendChild(li);
                });
            }
        }

        // Override for context menu on background
        canvasElement.addEventListener('contextmenu', getCanvasMenuOptions(canvas, graph, categorizedNodes));

        // Load saved or default graph
        const defaultGraph = {
            id: 'default-graph-1',
            revision: 1,
            last_node_id: 1,
            last_link_id: 0,
            nodes: [
                {
                    id: 1,
                    type: "DefaultDataServiceNode",
                    pos: [200, 200],
                    size: [200, 100],
                    flags: {},
                    order: 0,
                    mode: 0,
                    outputs: [{ name: "result", type: "data", links: null }],
                    properties: { prewarm_days: "30" }
                }
            ],
            links: [],
            groups: [],
            config: {},
            extra: {},
            version: 0.4
        };
        graph.configure(defaultGraph as any);
        updateStatus('connected', 'Ready');

        // Add keyboard support for deleting selected nodes
        document.addEventListener('keydown', (e: KeyboardEvent) => {
            if (e.key === 'Delete' || e.key === 'Backspace') {
                const selected = canvas.selected_nodes || {};
                Object.values(selected).forEach((node: LGraphNode) => {
                    graph.remove(node);
                });
            }
        });

        // Enhanced event handlers
        document.getElementById('save')?.addEventListener('click', () => {
            try {
                const graphData = graph.serialize();
                const blob = new Blob([JSON.stringify(graphData, null, 2)], { type: 'application/json' });
                const url = URL.createObjectURL(blob);
                const a = document.createElement('a');
                a.href = url;
                a.download = 'graph.json';
                a.click();
                URL.revokeObjectURL(url);
                updateStatus('connected', 'Graph saved');
                console.log('Graph saved successfully');
            } catch (e) {
                console.error('Failed to save graph:', e);
                updateStatus('disconnected', 'Save failed');
            }
        });

        const fileInput = document.getElementById('graph-file') as HTMLInputElement;
        fileInput.addEventListener('change', (e: Event) => {
            const target = e.target as HTMLInputElement;
            const file = target.files?.[0];
            if (file) {
                const reader = new FileReader();
                reader.onload = (ev) => {
                    try {
                        const data = JSON.parse(ev.target?.result as string);
                        graph.configure(data);
                        updateStatus('connected', 'Graph loaded');
                        console.log('Graph loaded successfully');
                    } catch (err) {
                        console.error('Failed to load graph:', err);
                        updateStatus('disconnected', 'Load failed');
                    }
                };
                reader.readAsText(file);
                target.value = ''; // Reset input
            }
        });

        document.getElementById('load')?.addEventListener('click', () => {
            fileInput.click();
        });

        document.getElementById('execute')?.addEventListener('click', async () => {
            try {
                showLoading(true);
                updateStatus('loading', 'Executing...');
                const graphData = graph.serialize();
                const res = await fetch('/execute', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(graphData),
                });
                if (!res.ok) {
                    throw new Error(`Execution failed: ${res.statusText}`);
                }
                const result = await res.json();
                updateStatus('connected', 'Execution complete');
                console.log('Execution result:', result);

                if (result.results) {
                    for (const nodeId in result.results) {
                        const node: any = graph.getNodeById(parseInt(nodeId));
                        if (node && node.displayResults) {
                            node.result = result.results[nodeId];
                            let text = JSON.stringify(node.result, null, 2);
                            if (node.type === 'LoggingNode' && node.result.output) {
                                text = node.result.output;
                            } else if (node.type === 'BinancePerpsUniverseNode' && node.result.symbols) {
                                text = node.result.symbols.map((s: any) => s.ticker).join('\n');
                            }
                            node.displayText = text;
                            const maxLineWidth = 50 * 7;
                            const tempCtx = document.createElement('canvas').getContext('2d')!;
                            tempCtx.font = "12px Arial";
                            let lines = (node as any).wrapText(text, maxLineWidth, tempCtx);
                            if (lines.length > 20) {
                                lines = lines.slice(0, 20);
                                lines.push('... (truncated)');
                            }
                            const lineHeight = 15;
                            const padding = 10;
                            const textHeight = lines.length * lineHeight + padding * 2;
                            const textWidth = Math.max(...lines.map((line: string) => tempCtx.measureText(line).width)) + padding * 2;
                            let baseHeight = LiteGraph.NODE_TITLE_HEIGHT + 4;
                            if (node.widgets) {
                                baseHeight += node.widgets.length * LiteGraph.NODE_WIDGET_HEIGHT;
                            }
                            node.size = [
                                Math.max(node.size[0] || 200, textWidth, 200),
                                baseHeight + textHeight
                            ];
                            node.displayText = lines.join('\n');
                            node.color = "#3a533a";
                            node.bgcolor = "#2a422a";
                            node.setDirtyCanvas(true, true);
                        }
                    }
                }
            } catch (e) {
                console.error('Execution failed:', e);
                updateStatus('disconnected', 'Execution failed');
            } finally {
                showLoading(false);
            }
        });

        // Function to handle canvas resizing and sharp rendering
        const resizeCanvas = () => {
            const rect = canvasElement.parentElement!.getBoundingClientRect();
            const dpr = window.devicePixelRatio || 1;

            if (canvas.canvas.width !== rect.width * dpr || canvas.canvas.height !== rect.height * dpr) {
                canvas.canvas.width = rect.width * dpr;
                canvas.canvas.height = rect.height * dpr;
                canvas.canvas.style.width = rect.width + 'px';
                canvas.canvas.style.height = rect.height + 'px';

                const ctx = canvas.canvas.getContext('2d');
                if (ctx) {
                    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
                }
            }
            canvas.draw(true, true);
        };

        // Handle window resize for sharp rendering
        window.addEventListener('resize', resizeCanvas);
        resizeCanvas();

        // Start the graph and set initial state
        graph.start();
        updateStatus('connected', 'Ready');
        canvas.setZoom(1, [0, 0]); // Fit graph to view on load

    } catch (error) {
        console.error('Failed to initialize editor:', error);
        updateStatus('disconnected', 'Failed to initialize');
    } finally {
        showLoading(false);
    }
}

function makeDraggable(element: HTMLElement, handle: HTMLElement) {
    let pos1 = 0, pos2 = 0, pos3 = 0, pos4 = 0;

    handle.onmousedown = (e: MouseEvent) => {
        e.preventDefault();
        pos3 = e.clientX;
        pos4 = e.clientY;
        document.onmouseup = closeDragElement;
        document.onmousemove = elementDrag;
    };

    function elementDrag(e: MouseEvent) {
        e.preventDefault();
        pos1 = pos3 - e.clientX;
        pos2 = pos4 - e.clientY;
        pos3 = e.clientX;
        pos4 = e.clientY;

        element.style.top = (element.offsetTop - pos2) + "px";
        element.style.left = (element.offsetLeft - pos1) + "px";
    }

    function closeDragElement() {
        document.onmouseup = null;
        document.onmousemove = null;
    }
}

// Initialize the editor when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    const container = document.querySelector('.app-container') as HTMLElement;
    if (container) {
        createEditor(container);
        const menu = document.getElementById('menu') as HTMLElement;
        const menuHeader = menu.querySelector('h3') as HTMLElement;
        if (menu && menuHeader) {
            makeDraggable(menu, menuHeader);
        }
    } else {
        console.error('Canvas container not found');
    }
}); 