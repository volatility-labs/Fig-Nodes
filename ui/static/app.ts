import { LGraph, LGraphCanvas, LGraphNode, LiteGraph, IContextMenuValue, ContextMenu } from '@comfyorg/litegraph';
import BaseCustomNode from './nodes/BaseCustomNode';
import { setupWebSocket } from './websocket';
import { createNodeList } from '@components/NodeList';
import { getCanvasMenuOptions } from '@utils/menuUtils';
import { setupResize, setupKeyboard, updateStatus, showLoading } from '@utils/uiUtils';

// For extensibility: To customize error handling, import { showError } from './utils/uiUtils' and reassign it to your custom function, e.g., showError = (msg) => { console.log(msg); alert(msg); };

async function createEditor(container: HTMLElement) {
    try {
        updateStatus('loading', 'Initializing...');

        const graph = new LGraph();
        const canvasElement = container.querySelector('#litegraph-canvas') as HTMLCanvasElement;
        const canvas = new LGraphCanvas(canvasElement, graph);

        const response = await fetch('/nodes');
        if (!response.ok) throw new Error(`Failed to fetch nodes: ${response.statusText}`);
        const meta = await response.json();

        const categorizedNodes: { [key: string]: string[] } = {};
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
        }

        createNodeList(meta, graph);

        canvasElement.addEventListener('contextmenu', getCanvasMenuOptions(canvas, graph, categorizedNodes));
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
