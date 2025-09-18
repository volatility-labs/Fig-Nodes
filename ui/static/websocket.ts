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

export function setupWebSocket(graph: LGraph, _canvas: LGraphCanvas) {
    const progressRoot = document.getElementById('top-progress');
    const progressBar = document.getElementById('top-progress-bar');
    const progressText = document.getElementById('top-progress-text');

    const showProgress = (label: string, determinate: boolean) => {
        if (progressRoot && progressBar && progressText) {
            progressRoot.style.display = 'block';
            progressText.textContent = label;
            if (determinate) {
                progressBar.classList.remove('indeterminate');
                (progressBar as HTMLElement).style.width = '1%';
            } else {
                progressBar.classList.add('indeterminate');
                (progressBar as HTMLElement).style.width = '100%';
            }
        }
    };

    const setProgress = (percent: number, label?: string) => {
        if (progressBar) {
            progressBar.classList.remove('indeterminate');
            (progressBar as HTMLElement).style.width = `${Math.max(0, Math.min(100, percent)).toFixed(1)}%`;
        }
        if (progressText && label) progressText.textContent = label;
    };

    const hideProgress = () => {
        if (progressRoot && progressBar) {
            (progressBar as HTMLElement).style.width = '0%';
            progressRoot.style.display = 'none';
        }
    };

    document.getElementById('execute')?.addEventListener('click', async () => {
        // Reset LoggingNode UIs before each execution so logs start fresh
        const nodes = ((graph as any)._nodes as any[]) || [];
        nodes.forEach((node: any) => {
            if (node && node.type === 'LoggingNode' && typeof node.reset === 'function') {
                try { node.reset(); } catch { }
            }
        });

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
        showProgress('Starting...', false);
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
                // Keep progress visible and reflect coarse states
                const msg: string = data.message || '';
                if (/starting/i.test(msg)) {
                    showProgress('Starting...', false);
                } else if (/executing batch/i.test(msg)) {
                    showProgress('Executing...', false);
                } else if (/stream starting/i.test(msg)) {
                    showProgress('Stream starting...', false);
                } else if (/finished/i.test(msg)) {
                    setProgress(100, 'Finished');
                    setTimeout(hideProgress, 350);
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
                    showProgress('Streaming...', false);
                    return;
                }
                const results = data.results;
                for (const nodeId in results) {
                    const node: any = graph.getNodeById(parseInt(nodeId));
                    if (node) {
                        if (data.stream) {
                            // Streaming tick: only append using onStreamUpdate if available
                            if (typeof node.onStreamUpdate === 'function') {
                                node.onStreamUpdate(results[nodeId]);
                            } else {
                                node.updateDisplay(results[nodeId]);
                            }
                            if (typeof node.pulseHighlight === 'function') {
                                try { node.pulseHighlight(); } catch { }
                            }
                        } else {
                            // Initial/batch: set full snapshot
                            node.updateDisplay(results[nodeId]);
                            if (typeof node.pulseHighlight === 'function') {
                                try { node.pulseHighlight(); } catch { }
                            }
                        }
                    }
                }
                // Progress behavior
                if (data.stream) {
                    // Ongoing stream: keep indeterminate
                    showProgress('Streaming...', false);
                } else {
                    // Initial static results (non-streaming part). Do not mark completed here.
                    // Keep showing determinate progress only if we can infer percentage (not available now),
                    // otherwise keep indeterminate until a finished status arrives.
                    showProgress('Running...', false);
                }
            } else if (data.type === 'error') {
                console.error('Execution error:', data.message);
                showError(data.message);
                if (indicator) {
                    indicator.className = `status-indicator disconnected`;
                    indicator.textContent = `Error: ${data.message}`;
                }
                stopExecution();
                hideProgress();
            }
        };

        ws.onclose = () => {
            stopExecution();
            hideProgress();
        };

        ws.onerror = (err) => {
            console.error('WebSocket error:', err);
            if (indicator) {
                indicator.className = `status-indicator disconnected`;
                indicator.textContent = 'Connection error';
            }
            stopExecution();
            hideProgress();
        };
    });

    document.getElementById('stop')?.addEventListener('click', stopExecution);
}
