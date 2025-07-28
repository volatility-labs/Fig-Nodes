"use strict";
const litegraph = window.litegraph.js;
const LGraph = litegraph.LGraph;
const LGraphCanvas = litegraph.LGraphCanvas;
const LGraphNode = litegraph.LGraphNode;
const LiteGraph = litegraph.LiteGraph;
// Enhanced Trading Bot Workflow Editor - TypeScript Implementation
// Node categories for better organization
const NODE_CATEGORIES = {
    'Data': ['DefaultDataServiceNode', 'BinanceDataProviderNode'],
    'Indicators': ['DefaultIndicatorsNode'],
    'Trading': ['DefaultTradingNode'],
    'Scoring': ['DefaultScoringNode'],
    'Utilities': ['SampleNode', 'UniverseNode'] // Assuming plugins
};
// Enhanced LiteGraph configuration
function configureLiteGraph() {
    // Global LiteGraph settings for ComfyUI-like appearance
    LiteGraph.NODE_TITLE_HEIGHT = 26;
    LiteGraph.NODE_TITLE_TEXT_Y = -4;
    LiteGraph.NODE_SLOT_HEIGHT = 16;
    LiteGraph.NODE_WIDGET_HEIGHT = 20;
    LiteGraph.NODE_WIDTH = 200;
    LiteGraph.NODE_MIN_WIDTH = 160;
    LiteGraph.NODE_COLLAPSED_RADIUS = 10;
    LiteGraph.NODE_COLLAPSED_WIDTH = 80;
    LiteGraph.CANVAS_GRID_SIZE = 10;
    LiteGraph.NODE_TEXT_SIZE = 12;
    LiteGraph.NODE_SUBTEXT_SIZE = 10;
    LiteGraph.DEFAULT_POSITION = [100, 100];
    LiteGraph.VALID_SHAPES = ["default", "box", "round", "card"];
    // Connection settings for clean look
    LiteGraph.CONNECTION_RENDER_MODE = "spline";
    LiteGraph.LINK_RENDER_MODE = 2; // Spline mode
    LiteGraph.MAX_NUMBER_OF_NODES = 1000;
    LiteGraph.DEFAULT_SHADOW_COLOR = "rgba(0,0,0,0.3)";
    LiteGraph.DEFAULT_GROUP_FONT = 24;
    // Performance settings
    LiteGraph.catch_exceptions = true;
    LiteGraph.throw_errors = false;
    LiteGraph.allow_scripts = false;
    LiteGraph.registered_node_types = LiteGraph.registered_node_types || {};
    // Disable ALL built-in panels and dialogs more aggressively
    if (LiteGraph.LGraphCanvas) {
        const LGC = LiteGraph.LGraphCanvas.prototype;
        // Completely disable all panel/dialog functions
        LGC.showNodePanel = function () { return false; };
        LGC.showShowNodePanel = function () { return false; };
        LGC.showEditPropertyValue = function () { return false; };
        LGC.onShowPropertyEditor = function () { return false; };
        LGC.showSubgraphPropertiesDialog = function () { return false; };
        LGC.showSearchBox = function () { return false; };
        LGC.prompt = function () { return false; };
        LGC.showLinkMenu = function () { return false; };
        // Override processNodeDblClicked completely
        LGC.processNodeDblClicked = function (node) {
            // ComfyUI doesn't open panels on double-click - just select
            this.selectNode(node);
            return false;
        };
    }
    // Global overrides
    LiteGraph.show_node_panel = false;
    LiteGraph.show_info = false;
    LiteGraph.alt_drag_do_clone_nodes = false; // Disable alt+drag cloning that might interfere
}
// Assuming LiteGraph is loaded globally or imported correctly
// Status management functions
function updateStatus(status, message) {
    const indicator = document.getElementById('status-indicator');
    if (indicator) {
        indicator.className = `status-indicator ${status}`;
        indicator.textContent = message || status.charAt(0).toUpperCase() + status.slice(1);
    }
}
// Loading overlay management
function showLoading(show) {
    const overlay = document.getElementById('loading-overlay');
    if (overlay) {
        overlay.style.display = show ? 'flex' : 'none';
    }
}
function createCustomNode(name, data) {
    class CustomNode extends LGraphNode {
        constructor() {
            super(name);
            this.title = name;
            this.size = [200, 100];
            // Add inputs with proper types
            data.inputs.forEach((inp) => {
                const inputType = this.inferInputType(inp);
                this.addInput(inp, inputType);
            });
            // Add outputs with proper types
            data.outputs.forEach((out) => {
                const outputType = this.inferOutputType(out);
                this.addOutput(out, outputType);
            });
            // Add parameters as widgets
            data.params.forEach((param) => {
                this.addParameterWidget(param);
            });
            // Initialize properties
            this.properties = this.properties || {};
            data.params.forEach((param) => {
                if (!(param in this.properties)) {
                    this.properties[param] = this.getDefaultValue(param);
                }
            });
            // Add description if available
            if (data.description) {
                this.desc = data.description;
            }
        }
        inferInputType(inputName) {
            const lowerName = inputName.toLowerCase();
            if (lowerName.includes('data') || lowerName.includes('price'))
                return 'data';
            if (lowerName.includes('signal') || lowerName.includes('indicator'))
                return 'signal';
            if (lowerName.includes('config') || lowerName.includes('param'))
                return 'config';
            return 'string';
        }
        inferOutputType(outputName) {
            const lowerName = outputName.toLowerCase();
            if (lowerName.includes('data') || lowerName.includes('price'))
                return 'data';
            if (lowerName.includes('signal') || lowerName.includes('indicator'))
                return 'signal';
            if (lowerName.includes('result') || lowerName.includes('output'))
                return 'result';
            return 'string';
        }
        addParameterWidget(param) {
            const paramLower = param.toLowerCase();
            if (paramLower.includes('enable') || paramLower.includes('active')) {
                this.addWidget('toggle', param, false, (value) => {
                    this.properties[param] = value;
                });
            }
            else if (paramLower.includes('amount') || paramLower.includes('size') || paramLower.includes('threshold')) {
                this.addWidget('number', param, 0, (value) => {
                    this.properties[param] = value;
                });
            }
            else if (paramLower.includes('symbol') || paramLower.includes('pair')) {
                this.addWidget('combo', param, 'BTC/USDT', (value) => {
                    this.properties[param] = value;
                }, { values: ['BTC/USDT', 'ETH/USDT', 'ADA/USDT', 'SOL/USDT'] });
            }
            else {
                this.addWidget('text', param, '', (value) => {
                    this.properties[param] = value;
                });
            }
        }
        getDefaultValue(param) {
            const paramLower = param.toLowerCase();
            if (paramLower.includes('enable') || paramLower.includes('active'))
                return false;
            if (paramLower.includes('days') || paramLower.includes('period'))
                return 30;
            if (paramLower.includes('amount') || paramLower.includes('size'))
                return 100;
            if (paramLower.includes('threshold'))
                return 0.5;
            if (paramLower.includes('symbol') || paramLower.includes('pair'))
                return 'BTC/USDT';
            return '';
        }
        onExecute() {
            // Override in specific node implementations
        }
        onConnectionsChange() {
            // Override for validation logic
        }
        // Right-click context menu
        getExtraMenuOptions(graphcanvas) {
            const options = [
                {
                    content: "Clone",
                    callback: () => {
                        const newNode = LiteGraph.createNode(this.type);
                        if (newNode) {
                            newNode.pos = [this.pos[0] + 30, this.pos[1] + 30];
                            newNode.properties = Object.assign({}, this.properties);
                            this.graph.add(newNode);
                        }
                    }
                },
                {
                    content: "Remove",
                    callback: () => {
                        this.graph.remove(this);
                    }
                },
                null, // separator
                {
                    content: "Properties",
                    callback: () => {
                        // Show inline properties only (already shown as widgets)
                        console.log("Properties:", this.properties);
                    }
                }
            ];
            return options;
        }
    }
    return CustomNode;
}
async function createEditor(container) {
    var _a, _b, _c;
    try {
        showLoading(true);
        updateStatus('loading', 'Initializing...');
        const graph = new LGraph();
        const canvas = new LGraphCanvas(container, graph);
        // Fetch available nodes from backend
        updateStatus('loading', 'Loading nodes...');
        const response = await fetch('/nodes');
        if (!response.ok) {
            throw new Error(`Failed to fetch nodes: ${response.statusText}`);
        }
        const meta = await response.json();
        // Create node to category map
        const nodeToCategory = {};
        Object.entries(NODE_CATEGORIES).forEach(([cat, nodes]) => {
            nodes.forEach((n) => nodeToCategory[n] = cat);
        });
        // Register custom nodes with enhanced features
        for (const name in meta.nodes) {
            const data = meta.nodes[name];
            const CustomNodeClass = createCustomNode(name, data);
            LiteGraph.registerNodeType(name, CustomNodeClass);
        }
        // Populate menu with categories
        const nodeList = document.getElementById('node-list');
        // Group nodes by category
        const categorizedNodes = {};
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
                        node.pos = [Math.random() * 300 + 100, Math.random() * 300 + 100];
                        graph.add(node);
                    });
                    li.appendChild(btn);
                    nodeList.appendChild(li);
                });
            }
        }
        // Override for context menu on background
        const originalProcessContextMenu = canvas.processContextMenu;
        canvas.processContextMenu = function (node, e) {
            if (node) {
                return originalProcessContextMenu.call(this, node, e);
            }
            else {
                const options = [
                    {
                        content: "Add Node",
                        has_submenu: true,
                        callback: function (item, opt, ev, parentMenu) {
                            const submenu = [];
                            for (const category in categorizedNodes) {
                                submenu.push({
                                    content: category,
                                    has_submenu: true,
                                    callback: function (it, o, evt, pm) {
                                        const subsubmenu = [];
                                        categorizedNodes[category].forEach((name) => {
                                            subsubmenu.push({
                                                content: name,
                                                callback: function () {
                                                    const newNode = LiteGraph.createNode(name);
                                                    newNode.pos = canvas.convertEventToCanvasOffset(e);
                                                    graph.add(newNode);
                                                }
                                            });
                                        });
                                        new litegraph.ContextMenu(subsubmenu, { event: evt, parentMenu: pm });
                                    }
                                });
                            }
                            new litegraph.ContextMenu(submenu, { event: ev, parentMenu: parentMenu });
                        }
                    }
                ];
                new litegraph.ContextMenu(options, { event: e, title: "Canvas Menu" });
                return true;
            }
        };
        // Load saved or default graph
        const defaultGraph = {
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
            }
            catch (e) {
                console.warn('Failed to load saved graph:', e);
                graph.configure(defaultGraph);
                updateStatus('connected', 'Default graph loaded');
            }
        }
        else {
            graph.configure(defaultGraph);
            updateStatus('connected', 'Ready');
        }
        // Enhanced event handlers
        (_a = document.getElementById('save')) === null || _a === void 0 ? void 0 : _a.addEventListener('click', () => {
            try {
                const graphData = graph.serialize();
                localStorage.setItem('savedGraph', JSON.stringify(graphData));
                updateStatus('connected', 'Graph saved');
                console.log('Graph saved successfully');
            }
            catch (e) {
                console.error('Failed to save graph:', e);
                updateStatus('disconnected', 'Save failed');
            }
        });
        (_b = document.getElementById('load')) === null || _b === void 0 ? void 0 : _b.addEventListener('click', () => {
            try {
                const savedGraph = localStorage.getItem('savedGraph');
                if (savedGraph) {
                    graph.configure(JSON.parse(savedGraph));
                    updateStatus('connected', 'Graph loaded');
                    console.log('Graph loaded successfully');
                }
                else {
                    updateStatus('disconnected', 'No saved graph');
                }
            }
            catch (e) {
                console.error('Failed to load graph:', e);
                updateStatus('disconnected', 'Load failed');
            }
        });
        (_c = document.getElementById('execute')) === null || _c === void 0 ? void 0 : _c.addEventListener('click', async () => {
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
            }
            catch (e) {
                console.error('Execution failed:', e);
                updateStatus('disconnected', 'Execution failed');
            }
            finally {
                showLoading(false);
            }
        });
        // Handle window resize for sharp rendering
        window.addEventListener('resize', () => {
            const rect = container.getBoundingClientRect();
            const devicePixelRatio = window.devicePixelRatio || 1;
            canvas.canvas.width = rect.width * devicePixelRatio;
            canvas.canvas.height = rect.height * devicePixelRatio;
            canvas.canvas.style.width = rect.width + 'px';
            canvas.canvas.style.height = rect.height + 'px';
            const ctx = canvas.canvas.getContext('2d');
            if (ctx) {
                ctx.scale(devicePixelRatio, devicePixelRatio);
                ctx.imageSmoothingEnabled = false;
            }
            canvas.resize();
        });
        // Start the graph
        graph.start();
        updateStatus('connected', 'Ready');
    }
    catch (error) {
        console.error('Failed to initialize editor:', error);
        updateStatus('disconnected', 'Failed to initialize');
    }
    finally {
        showLoading(false);
    }
}
// Initialize the editor when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    const container = document.querySelector('#litegraph-canvas');
    if (container) {
        createEditor(container);
    }
    else {
        console.error('Canvas container not found');
    }
});
