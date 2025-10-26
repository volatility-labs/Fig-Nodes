import { LGraph, LGraphCanvas } from '@comfyorg/litegraph';
import { ServiceRegistry } from './services/ServiceRegistry';
import { APIKeyManager } from './services/APIKeyManager';
import type { ExecutionResults } from './types/resultTypes';
import type {
    ClientToServerMessage,
    ServerToClientMessage
} from './types/websocketType';
import {
    isErrorMessage,
    isStatusMessage,
    isStoppedMessage,
    isDataMessage,
    isProgressMessage
} from './types/websocketType';

// Constants
const STATUS_CLASSES = {
    CONNECTED: 'status-indicator connected',
    EXECUTING: 'status-indicator executing',
    DISCONNECTED: 'status-indicator disconnected',
} as const;

const PROGRESS_LABELS = {
    READY: 'Ready',
    STARTING: 'Starting...',
    EXECUTING: 'Executing...',
    STREAMING: 'Streaming...',
    RUNNING: 'Running...',
    STOPPING: 'Stopping...',
    FINISHED: 'Finished',
} as const;

// State
let ws: WebSocket | null = null;
export let executionState: 'idle' | 'connecting' | 'executing' | 'stopping' = 'idle';
let stopPromiseResolver: (() => void) | null = null;

// DOM Element Helpers
function getDOMElements() {
    return {
        execute: document.getElementById('execute'),
        stop: document.getElementById('stop'),
        overlay: document.getElementById('loading-overlay'),
        indicator: document.getElementById('status-indicator'),
        progressRoot: document.getElementById('top-progress'),
        progressBar: document.getElementById('top-progress-bar'),
        progressText: document.getElementById('top-progress-text'),
    };
}

// Progress Bar Management
function showProgress(label: string, determinate: boolean) {
    const { progressRoot, progressBar, progressText } = getDOMElements();
    if (!progressRoot || !progressBar || !progressText) return;

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

function setProgress(percent: number, label?: string) {
    const { progressBar, progressText } = getDOMElements();
    
    if (progressBar) {
        progressBar.classList.remove('indeterminate');
        (progressBar as HTMLElement).style.width = `${Math.max(0, Math.min(100, percent)).toFixed(1)}%`;
    }
    
    if (progressText && label) {
        progressText.textContent = label;
    }
}

function hideProgress() {
    const { progressRoot, progressBar } = getDOMElements();
    if (!progressRoot || !progressBar) return;

    (progressBar as HTMLElement).style.width = '0%';
    progressBar.classList.remove('indeterminate');
    progressRoot.style.display = 'block';
}

function resetProgressToIdle() {
    const { progressRoot, progressBar, progressText } = getDOMElements();
    if (!progressRoot || !progressBar || !progressText) return;

    (progressBar as HTMLElement).style.width = '0%';
    progressBar.classList.remove('indeterminate');
    progressText.textContent = PROGRESS_LABELS.READY;
    progressRoot.style.display = 'block';
}

function updateStatusIndicator(className: string) {
    const { indicator } = getDOMElements();
    if (indicator) {
        indicator.className = className;
    }
}

function showExecuteButton() {
    const { execute, stop } = getDOMElements();
    if (execute) execute.style.display = 'inline-block';
    if (stop) stop.style.display = 'none';
}

function showStopButton() {
    const { execute, stop } = getDOMElements();
    if (execute) execute.style.display = 'none';
    if (stop) stop.style.display = 'inline-block';
}

function hideOverlay() {
    const { overlay } = getDOMElements();
    if (overlay) overlay.style.display = 'none';
}

// Stop Execution
async function stopExecution(): Promise<void> {
    if (executionState === 'idle' || executionState === 'stopping') {
        console.log('Stop execution: Already idle or stopping, skipping');
        return;
    }

    executionState = 'stopping';
    updateStatusIndicator(STATUS_CLASSES.EXECUTING);
    showProgress(PROGRESS_LABELS.STOPPING, false);

    return new Promise((resolve) => {
        stopPromiseResolver = resolve;
        if (ws && ws.readyState === WebSocket.OPEN) {
            console.log('Stop execution: Sending stop message to backend');
            const message: ClientToServerMessage = { type: 'stop' };
            ws.send(JSON.stringify(message));
        } else {
            console.log('Stop execution: No active WebSocket, forcing cleanup');
            closeWebSocket(); // Close if websocket doesn't exist
            forceCleanup();
            resolve();
        }
    });
}

function forceCleanup() {
    // Don't close websocket here - keep connection alive for subsequent executions
    // Only cleanup UI state
    
    executionState = 'idle';
    hideOverlay();
    showExecuteButton();
    updateStatusIndicator(STATUS_CLASSES.CONNECTED);
    resetProgressToIdle();

    if (stopPromiseResolver) {
        stopPromiseResolver();
        stopPromiseResolver = null;
    }
}

function closeWebSocket() {
    // Explicitly close websocket when needed (errors, unexpected disconnects)
    if (ws) {
        ws.close();
        ws = null;
    }
}

// Message Handlers
function handleErrorMessage(data: any, apiKeyManager: APIKeyManager) {
    console.error('Execution error:', data.message);
    
    if (data.code === 'MISSING_API_KEYS' && Array.isArray(data.missing_keys)) {
        try { 
            alert(data.message || 'Missing API keys. Opening settings...'); 
        } catch { /* ignore in tests */ }
        apiKeyManager.setLastMissingKeys(data.missing_keys);
        apiKeyManager.openSettings(data.missing_keys);
    } else {
        try { 
            alert('Error: ' + data.message); 
        } catch { /* ignore in tests */ }
    }
    
    // Try to show error via dialog manager
    try {
        const sr: ServiceRegistry | undefined = (window as any).serviceRegistry;
        const dm = sr?.get?.('dialogManager');
        if (dm && typeof (dm as any).showError === 'function') {
            (dm as any).showError(data.message);
        }
    } catch { /* ignore */ }
    
    updateStatusIndicator(STATUS_CLASSES.DISCONNECTED);
    closeWebSocket(); // Close on error
    forceCleanup();
    hideProgress();
}

function handleStatusMessage(data: any) {
    updateStatusIndicator(STATUS_CLASSES.EXECUTING);
    
    const msg = data.message || '';
    if (/starting/i.test(msg)) {
        showProgress(PROGRESS_LABELS.STARTING, false);
    } else if (/executing batch/i.test(msg)) {
        showProgress(PROGRESS_LABELS.EXECUTING, false);
    } else if (/stream starting/i.test(msg)) {
        showProgress(PROGRESS_LABELS.STREAMING, false);
    } else if (/finished/i.test(msg)) {
        setProgress(100, PROGRESS_LABELS.FINISHED);
        setTimeout(() => {
            hideProgress();
            executionState = 'idle';
        }, 350);
        forceCleanup();
    }
}

function handleStoppedMessage(data: any) {
    console.log('Stop execution: Received stopped confirmation from backend:', data.message);
    // Don't close websocket - server manages connection lifecycle
    // The server may close the connection itself, or keep it open for next execution
    forceCleanup();
}

function handleDataMessage(data: any, graph: LGraph) {
    if (Object.keys(data.results).length === 0) {
        updateStatusIndicator(STATUS_CLASSES.EXECUTING);
        showProgress(PROGRESS_LABELS.STREAMING, false);
        return;
    }

    const results: ExecutionResults = data.results;
    for (const nodeId in results) {
        const node: any = graph.getNodeById(parseInt(nodeId));
        if (!node) continue;

        const allowRender = node.type === 'Logging';
        const updateMethod = node.onStreamUpdate || node.updateDisplay;

        if (allowRender && typeof updateMethod === 'function') {
            updateMethod.call(node, results[nodeId]);
        }

        if (typeof node.pulseHighlight === 'function') {
            try { node.pulseHighlight(); } catch { }
        }
    }

    // Update progress based on stream state
    if (data.stream) {
        showProgress(PROGRESS_LABELS.STREAMING, false);
    } else {
        showProgress(PROGRESS_LABELS.RUNNING, false);
    }
}

function handleProgressMessage(data: any, graph: LGraph) {
    const node: any = graph.getNodeById(data.node_id as number);
    if (node && typeof node.setProgress === 'function') {
        node.setProgress(data.progress ?? 0, data.text ?? '');
    }
}

// Setup
export function setupWebSocket(graph: LGraph, _canvas: LGraphCanvas, apiKeyManager: APIKeyManager) {
    document.getElementById('execute')?.addEventListener('click', async () => {
        if (executionState === 'stopping') {
            console.warn('Cannot start execution while stopping previous one');
            return;
        }

        // Preflight API key check
        const graphData = graph.asSerialisable({ sortNodes: true });
        try {
            const requiredKeys = await apiKeyManager.getRequiredKeysForGraph(graphData as any);
            if (requiredKeys.length > 0) {
                const missing = await apiKeyManager.checkMissingKeys(requiredKeys);
                if (missing.length > 0) {
                    try { 
                        alert(`Missing API keys for this graph: ${missing.join(', ')}. Please set them in the settings menu.`); 
                    } catch { /* ignore in tests */ }
                    apiKeyManager.setLastMissingKeys(missing);
                    await apiKeyManager.openSettings(missing);
                    return;
                }
            }
        } catch {
            // If preflight fails, fall back to server-side validation
        }

        // Reset LoggingNode UIs
        const nodes = ((graph as any)._nodes as any[]) || [];
        nodes.forEach((node: any) => {
            if (node?.type === 'Logging' && typeof node.reset === 'function') {
                try { node.reset(); } catch { }
            }
        });

        // Update UI state
        hideOverlay();
        updateStatusIndicator(STATUS_CLASSES.EXECUTING);
        showStopButton();
        executionState = 'connecting';
        showProgress(PROGRESS_LABELS.STARTING, false);

        // Reuse existing WebSocket connection or create new one
        const protocol = window.location.protocol === 'https:' ? 'wss' : 'ws';
        const backendHost = window.location.hostname;
        const wsUrl = `${protocol}://${backendHost}${window.location.port === '8000' ? '' : ':8000'}/execute`;
        
        if (!ws || ws.readyState !== WebSocket.OPEN) {
            // Create new WebSocket connection
            ws = new WebSocket(wsUrl);

            ws.onopen = () => {
                executionState = 'executing';
                updateStatusIndicator(STATUS_CLASSES.EXECUTING);
                const message: ClientToServerMessage = { type: 'graph', graph_data: graphData };
                ws?.send(JSON.stringify(message));
            };

            ws.onmessage = (event) => {
                const data: ServerToClientMessage = JSON.parse(event.data);

                if (isErrorMessage(data)) {
                    handleErrorMessage(data, apiKeyManager);
                } else if (isStatusMessage(data)) {
                    handleStatusMessage(data);
                } else if (isStoppedMessage(data)) {
                    handleStoppedMessage(data);
                } else if (isDataMessage(data)) {
                    handleDataMessage(data, graph);
                } else if (isProgressMessage(data)) {
                    handleProgressMessage(data, graph);
                }
            };

            ws.onclose = (event) => {
                console.log(`WebSocket closed: code=${event.code}, reason=${event.reason}`);
                // Don't call forceCleanup() on normal close - connection is managed by server
                // Only cleanup if it's an unexpected disconnect
                if (event.code !== 1000) {
                    updateStatusIndicator(STATUS_CLASSES.DISCONNECTED);
                    hideProgress();
                }
            };

            ws.onerror = (err) => {
                console.error('WebSocket error:', err);
                updateStatusIndicator(STATUS_CLASSES.DISCONNECTED);
                closeWebSocket(); // Close on error
                forceCleanup();
                hideProgress();
            };
        } else {
            // Reuse existing connection
            executionState = 'executing';
            updateStatusIndicator(STATUS_CLASSES.EXECUTING);
            const message: ClientToServerMessage = { type: 'graph', graph_data: graphData };
            ws.send(JSON.stringify(message));
        }
    });

    document.getElementById('stop')?.addEventListener('click', () => {
        stopExecution().catch(err => console.error('Error stopping execution:', err));
    });
}
