import { LGraph, LGraphCanvas, LGraphNode, LiteGraph, IContextMenuValue, ContextMenu, LGraphGroup } from '@comfyorg/litegraph';

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

function createCustomNode(name: string, data: any) {
    class CustomNode extends LGraphNode {
        constructor() {
            super(name);
            this.title = name;
            this.size = [200, 100];

            // Add inputs with proper types
            if (data.inputs) {
                data.inputs.forEach((inp: string) => {
                    const inputType = this.inferInputType(inp);
                    this.addInput(inp, inputType);
                });
            }

            // Add outputs with proper types
            if (data.outputs) {
                data.outputs.forEach((out: string) => {
                    const outputType = this.inferOutputType(out);
                    this.addOutput(out, outputType);
                });
            }

            // Add parameters as widgets
            if (data.params) {
                data.params.forEach((param: string) => {
                    this.addParameterWidget(param);
                });
            }

            // Initialize properties
            this.properties = this.properties || {};
            if (data.params) {
                data.params.forEach((param: any) => {
                    if (!(param in this.properties)) {
                        this.properties[param] = this.getDefaultValue(param);
                    }
                });
            }
        }

        inferInputType(inputName: string): string {
            const lowerName = inputName.toLowerCase();
            if (lowerName.includes('data') || lowerName.includes('price')) return 'data';
            if (lowerName.includes('signal') || lowerName.includes('indicator')) return 'signal';
            if (lowerName.includes('config') || lowerName.includes('param')) return 'config';
            return 'string';
        }

        inferOutputType(outputName: string): string {
            const lowerName = outputName.toLowerCase();
            if (lowerName.includes('data') || lowerName.includes('price')) return 'data';
            if (lowerName.includes('signal') || lowerName.includes('indicator')) return 'signal';
            if (lowerName.includes('result') || lowerName.includes('output')) return 'result';
            return 'string';
        }

        addParameterWidget(param: string) {
            const paramLower = param.toLowerCase();

            if (paramLower.includes('enable') || paramLower.includes('active')) {
                this.addWidget('toggle', param, false, (value: boolean) => {
                    this.properties[param] = value;
                });
            } else if (paramLower.includes('amount') || paramLower.includes('size') || paramLower.includes('threshold')) {
                this.addWidget('number', param, 0, (value: number) => {
                    this.properties[param] = value;
                });
            } else if (paramLower.includes('symbol') || paramLower.includes('pair')) {
                this.addWidget('combo', param, 'BTC/USDT', (value: string) => {
                    this.properties[param] = value;
                }, { values: ['BTC/USDT', 'ETH/USDT', 'ADA/USDT', 'SOL/USDT'] });
            } else {
                this.addWidget('text', param, '', (value: any) => {
                    this.properties[param] = value;
                });
            }
        }

        getDefaultValue(param: string): any {
            const paramLower = param.toLowerCase();
            if (paramLower.includes('enable') || paramLower.includes('active')) return false;
            if (paramLower.includes('days') || paramLower.includes('period')) return 30;
            if (paramLower.includes('amount') || paramLower.includes('size')) return 100;
            if (paramLower.includes('threshold')) return 0.5;
            if (paramLower.includes('symbol') || paramLower.includes('pair')) return 'BTC/USDT';
            return '';
        }

        onExecute() {
            // Override in specific node implementations
        }

        onConnectionsChange() {
            // Override for validation logic
        }

        // Right-click context menu
        getExtraMenuOptions(graphcanvas: LGraphCanvas): IContextMenuValue[] {
            const options: (IContextMenuValue | null)[] = [
                {
                    content: "Clone",
                    callback: () => {
                        const newNode = LiteGraph.createNode(this.type);
                        if (newNode && this.graph) {
                            newNode.pos = [this.pos[0] + 30, this.pos[1] + 30];
                            newNode.properties = { ...this.properties };
                            this.graph.add(newNode as any);
                        }
                    }
                },
                {
                    content: "Remove",
                    callback: () => {
                        if (this.graph) {
                            this.graph.remove(this);
                        }
                    }
                }
            ];
            return options.filter(o => o) as IContextMenuValue[];
        }
    }
    return CustomNode;
}

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
            const CustomNodeClass = createCustomNode(name, data);
            LiteGraph.registerNodeType(name, CustomNodeClass);
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
        const saved = localStorage.getItem('savedGraph');
        if (saved) {
            try {
                graph.configure(JSON.parse(saved));
                updateStatus('connected', 'Graph loaded');
            } catch (e) {
                console.warn('Failed to load saved graph:', e);
                graph.configure(defaultGraph as any);
                updateStatus('connected', 'Default graph loaded');
            }
        } else {
            graph.configure(defaultGraph as any);
            updateStatus('connected', 'Ready');
        }

        // Enhanced event handlers
        document.getElementById('save')?.addEventListener('click', () => {
            try {
                const graphData = graph.serialize();
                localStorage.setItem('savedGraph', JSON.stringify(graphData));
                updateStatus('connected', 'Graph saved');
                console.log('Graph saved successfully');
            } catch (e) {
                console.error('Failed to save graph:', e);
                updateStatus('disconnected', 'Save failed');
            }
        });

        document.getElementById('load')?.addEventListener('click', () => {
            try {
                const savedGraph = localStorage.getItem('savedGraph');
                if (savedGraph) {
                    graph.configure(JSON.parse(savedGraph));
                    updateStatus('connected', 'Graph loaded');
                    console.log('Graph loaded successfully');
                } else {
                    updateStatus('disconnected', 'No saved graph');
                }
            } catch (e) {
                console.error('Failed to load graph:', e);
                updateStatus('disconnected', 'Load failed');
            }
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
                // Highlight executed nodes
                if (result.results) {
                    for (const nodeId in result.results) {
                        const node = graph.getNodeById(parseInt(nodeId));
                        if (node) {
                            node.setDirtyCanvas(true, true);
                            (node as any).color = "#3a533a";
                            (node as any).bgcolor = "#2a422a";
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

// Initialize the editor when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    const container = document.querySelector('.app-container') as HTMLElement;
    if (container) {
        createEditor(container);
    } else {
        console.error('Canvas container not found');
    }
}); 