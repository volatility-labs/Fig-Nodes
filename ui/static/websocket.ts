import { LGraph, LGraphCanvas } from '@comfyorg/litegraph';
import { showError } from './utils/uiUtils';

let ws: WebSocket | null = null;

function stopExecution() {
    if (ws) {
        ws.close();
        ws = null;
    }
    const overlay = document.getElementById('loading-overlay');
    if (overlay) overlay.style.display = 'none';
    document.getElementById('execute')!.style.display = 'inline-block';
    document.getElementById('stop')!.style.display = 'none';
    const indicator = document.getElementById('status-indicator');
    if (indicator) {
        indicator.className = `status-indicator connected`;
        indicator.textContent = 'Ready';
    }
}

export function setupWebSocket(graph: LGraph, canvas: LGraphCanvas) {
    document.getElementById('execute')?.addEventListener('click', async () => {
        const overlay = document.getElementById('loading-overlay');
        const overlayText = overlay?.querySelector('span');
        if (overlay && overlayText) {
            overlay.style.display = 'flex';
            overlayText.textContent = 'Executing...';
        }
        const indicator = document.getElementById('status-indicator');
        if (indicator) {
            indicator.className = `status-indicator executing`;
            indicator.textContent = 'Connecting...';
        }
        document.getElementById('execute')!.style.display = 'none';
        document.getElementById('stop')!.style.display = 'inline-block';

        const graphData = graph.serialize();
        const protocol = window.location.protocol === 'https:' ? 'wss' : 'ws';
        const backendHost = window.location.hostname;
        const wsUrl = `${protocol}://${backendHost}${window.location.port === '8000' ? '' : ':8000'}/execute`;
        ws = new WebSocket(wsUrl);

        ws.onopen = () => {
            if (indicator) {
                indicator.className = `status-indicator executing`;
                indicator.textContent = 'Running...';
            }
            ws?.send(JSON.stringify(graphData));
        };

        ws.onmessage = (event) => {
            const data = JSON.parse(event.data);

            if (data.type === 'status') {
                if (indicator) {
                    indicator.className = `status-indicator executing`;
                    indicator.textContent = data.message;
                }
                if (data.message.includes('finished')) {
                    stopExecution();
                }
            } else if (data.type === 'data') {
                if (overlay) overlay.style.display = 'none';
                if (Object.keys(data.results).length === 0) {
                    if (indicator) {
                        indicator.className = `status-indicator executing`;
                        indicator.textContent = 'Stream started...';
                    }
                    return;
                }
                const results = data.results;
                for (const nodeId in results) {
                    const node: any = graph.getNodeById(parseInt(nodeId));
                    if (node) {
                        node.updateDisplay(results[nodeId]);
                        if (node.onStreamUpdate) {
                            node.onStreamUpdate(node.result);
                        }
                    }
                }
            } else if (data.type === 'error') {
                console.error('Execution error:', data.message);
                showError(data.message);
                if (indicator) {
                    indicator.className = `status-indicator disconnected`;
                    indicator.textContent = `Error: ${data.message}`;
                }
                stopExecution();
            }
        };

        ws.onclose = () => {
            stopExecution();
        };

        ws.onerror = (err) => {
            console.error('WebSocket error:', err);
            if (indicator) {
                indicator.className = `status-indicator disconnected`;
                indicator.textContent = 'Connection error';
            }
            stopExecution();
        };
    });

    document.getElementById('stop')?.addEventListener('click', stopExecution);
}
