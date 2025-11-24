/**
 * WebSocket Client for Graph Execution
 * 
 * Handles WebSocket communication between the frontend and backend execution queue.
 * Manages execution state, progress updates, and result handling.
 * 
 * SERVER → CLIENT MESSAGE SHAPES:
 * 
 * 1. ServerToClientStatusMessage
 *    - type: "status"
 *    - message: string (status text)
 *    Examples: "Executing batch", "Batch finished"
 * 
 * 2. ServerToClientErrorMessage
 *    - type: "error"
 *    - message: string (error description)
 *    - code?: "MISSING_API_KEYS" (optional error code)
 *    - missing_keys?: string[] (optional list of missing API keys)
 * 
 * 3. ServerToClientStoppedMessage
 *    - type: "stopped"
 *    - message: string (stop confirmation message)
 *    Example: "Execution stopped: user"
 * 
 * 4. ServerToClientDataMessage
 *    - type: "data"
 *    - results: ExecutionResults (node results keyed by node ID)
 * 
 * 5. ServerToClientProgressMessage
 *    - type: "progress"
 *    - node_id?: number (optional node ID for progress update)
 *    - progress?: number (optional progress percentage 0-100)
 *    - text?: string (optional progress text)
 *    - state?: ProgressState (optional progress state: "start", "update", "done", "error", "stopped")
 *    - meta?: Record<string, unknown> (optional additional metadata)
 * 
 * 6. ServerToClientQueuePositionMessage
 *    - type: "queue_position"
 *    - position: number (position in execution queue, 0 = running)
 * 
 * CLIENT → SERVER MESSAGE SHAPES:
 * 
 * 1. ClientToServerGraphMessage
 *    - type: "graph"
 *    - graph_data: SerialisableGraph (graph to execute)
 * 
 * 2. ClientToServerStopMessage
 *    - type: "stop"
 */

import { LGraph, LGraphCanvas } from '@fig-node/litegraph';
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
    isProgressMessage,
    isQueuePositionMessage,
    isSessionMessage,
    ProgressState,
    type ServerToClientStatusMessage,
    type ServerToClientQueuePositionMessage
} from './types/websocketType';
import type { ExecutionStatusService } from './services/ExecutionStatusService';
import type { ConnectionStatus } from './services/ExecutionStatusService';


// State
let ws: WebSocket | null = null;
let stopPromiseResolver: (() => void) | null = null;
let sessionId: string | null = localStorage.getItem('session_id');
let graphInstance: LGraph | null = null;

function getStatusService(): ExecutionStatusService | null {
    const sr: ServiceRegistry | undefined = (window as any).serviceRegistry;
    return (sr?.get?.('statusService') as ExecutionStatusService) || null;
}

function getExecutionState(): ConnectionStatus {
    const statusService = getStatusService();
    return statusService?.getState() ?? 'connected';
}


function showExecuteButton() {
    const execute = document.getElementById('execute');
    const stop = document.getElementById('stop');
    if (execute) execute.style.display = 'inline-block';
    if (stop) stop.style.display = 'none';
}

function showStopButton() {
    const execute = document.getElementById('execute');
    const stop = document.getElementById('stop');
    if (execute) execute.style.display = 'none';
    if (stop) stop.style.display = 'inline-block';
}

function hideOverlay() {
    const overlay = document.getElementById('loading-overlay');
    if (overlay) overlay.style.display = 'none';
}

function clearAllHighlights() {
    if (!graphInstance) return;
    const nodes = ((graphInstance as any)._nodes as any[]) || [];
    nodes.forEach((node: any) => {
        try {
            if (typeof node.clearHighlight === 'function') {
                node.clearHighlight();
            } else {
                // Fallback: clear highlight properties directly
                if (node.highlightStartTs !== undefined) {
                    node.highlightStartTs = null;
                }
                if (node.isExecuting !== undefined) {
                    node.isExecuting = false;
                }
                if (typeof node.setDirtyCanvas === 'function') {
                    node.setDirtyCanvas(true, true);
                }
            }
        } catch (err) {
            console.warn('Error clearing highlight on node:', err);
        }
    });
}

// Stop Execution
async function stopExecution(): Promise<void> {
    const currentState = getExecutionState();
    if (currentState === 'connected' || currentState === 'stopping') {
        console.log('Stop execution: Already idle or stopping, skipping');
        return;
    }

    const statusService = getStatusService();
    statusService?.setStopping();

    return new Promise((resolve) => {
        stopPromiseResolver = resolve;
        if (ws && ws.readyState === WebSocket.OPEN) {
            console.log('Stop execution: Sending stop message to backend');
            const message: ClientToServerMessage = { type: 'stop' };
            ws.send(JSON.stringify(message));
        } else {
            console.log('Stop execution: No active WebSocket, forcing cleanup');
            closeWebSocket();
            forceCleanup();
            resolve();
        }
    });
}

function forceCleanup() {
    hideOverlay();
    showExecuteButton();
    clearAllHighlights();
    const statusService = getStatusService();
    statusService?.setIdle();
    // Don't clear polygon status - keep it visible

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
    
    const statusService = getStatusService();
    statusService?.error(null, data.message);
    
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
    
    try {
        const sr: ServiceRegistry | undefined = (window as any).serviceRegistry;
        const dm = sr?.get?.('dialogManager');
        if (dm && typeof (dm as any).showError === 'function') {
            (dm as any).showError(data.message);
        }
    } catch { /* ignore */ }
    
    closeWebSocket();
    forceCleanup();
}

function handleStatusMessage(message: ServerToClientStatusMessage) {
    const statusService = getStatusService();
    
    // Adopt job on first message if needed
    if (statusService?.getCurrentJobId() !== message.job_id) {
        statusService?.adoptJob(message.job_id);
    }
    
    // Update state from backend message using explicit state
    statusService?.updateFromBackendState(message.state, message.message, message.job_id);
    
    // Show execute button when execution finishes or errors
    if (message.state === 'finished' || message.state === 'error') {
        showExecuteButton();
        // Don't clear polygon status - keep it visible
    }
}

function handleStoppedMessage(data: any) {
    console.log('Stop execution: Received stopped confirmation from backend:', data.message);
    
    // Show execute button and hide stop button
    showExecuteButton();
    
    // Clear all pulsating highlights
    clearAllHighlights();
    
    // Clean up UI state
    const statusService = getStatusService();
    statusService?.stopped(null);
    // Don't clear polygon status - keep it visible
    
    // Resolve the stop promise
    if (stopPromiseResolver) {
        stopPromiseResolver();
        stopPromiseResolver = null;
    }
}

function handleDataMessage(data: any, graph: LGraph) {
    const statusService = getStatusService();
    
    if (Object.keys(data.results).length === 0) {
        statusService?.setProgress(null, undefined, 'Running...');
        return;
    }

    const results: ExecutionResults = data.results;
    for (const nodeId in results) {
        const node: any = graph.getNodeById(parseInt(nodeId));
        if (!node) continue;

        // Streaming nodes always receive results via onStreamUpdate
        // Only call onStreamUpdate for actual streaming nodes (not just nodes that have the method)
        if (node.isStreaming === true && typeof node.onStreamUpdate === 'function') {
            node.onStreamUpdate.call(node, results[nodeId]);
        }
        
        // Call updateDisplay if node has the method
        // Nodes with displayResults=false can still override updateDisplay for custom rendering (e.g., images)
        // Base implementation handles displayResults=false correctly (won't display text)
        if (typeof node.updateDisplay === 'function') {
            node.updateDisplay.call(node, results[nodeId]);
        }
    }

    statusService?.setProgress(null, undefined, 'Running...');
}

function handleProgressMessage(data: any, graph: LGraph) {
    const node: any = graph.getNodeById(data.node_id as number);
    if (!node) return;
    
    // Handle progress updates
    if (typeof node.setProgress === 'function') {
        const progress = data.progress ?? 0;
        // Only pass text if it's explicitly provided and non-empty
        if (data.text !== undefined && data.text !== '') {
            node.setProgress(progress, data.text);
        } else {
            node.setProgress(progress);
        }
    }
    
    // Handle highlight based on execution state
    const state = data.state as ProgressState | undefined;
    if ((state === ProgressState.START || state === ProgressState.UPDATE) && typeof node.pulseHighlight === 'function') {
        // Node is starting or actively executing - pulse highlight
        node.pulseHighlight();
    } else if (
        (state === ProgressState.DONE || state === ProgressState.ERROR || state === ProgressState.STOPPED) &&
        typeof node.clearHighlight === 'function'
    ) {
        // Node execution finished - clear highlight
        node.clearHighlight();
    }
    
    // Handle polygon data status metadata
    if (data.meta?.polygon_data_status) {
        updatePolygonStatus(data.meta.polygon_data_status);
    }
}

function updatePolygonStatus(status: string) {
    const element = document.getElementById('polygon-status');
    if (!element) {
        return;
    }

    element.className = `polygon-status ${status}`;

    const labels: Record<string, string> = {
        'real-time': 'Real-Time',
        'delayed': 'Delayed',
        'market-closed': 'Market Closed',
        'unknown': 'Unknown',
        'na': 'N/A',
        'polygon-status-na': 'N/A'
    };

    element.textContent = labels[status] || status;
    element.setAttribute('title', `Polygon Data Status: ${labels[status] || status}`);
}

function handleQueuePositionMessage(message: ServerToClientQueuePositionMessage) {
    const statusService = getStatusService();
    const position = message.position;
    
    // Position 0 means the job is currently running
    if (position === 0) {
        statusService?.setQueuePosition(statusService.getCurrentJobId() ?? -1, 0);
    } else {
        // Position > 0 means queued (showing how many jobs ahead)
        statusService?.setQueuePosition(statusService.getCurrentJobId() ?? -1, position);
    }
}

// Setup
export function setupWebSocket(graph: LGraph, _canvas: LGraphCanvas, apiKeyManager: APIKeyManager) {
    graphInstance = graph;
    document.getElementById('execute')?.addEventListener('click', async () => {
        if (getExecutionState() === 'stopping') {
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

        // Reset all nodes' visual state before starting new execution
        const nodes = ((graph as any)._nodes as any[]) || [];
        nodes.forEach((node: any) => {
            try {
                // Clear progress indicators
                if (typeof node.clearProgress === 'function') {
                    node.clearProgress();
                }
                
                // Clear error state
                if (typeof node.setError === 'function') {
                    node.setError('');
                } else if (node.error !== undefined) {
                    node.error = '';
                }
                
                // Reset color to original (restore default color)
                if (node.color !== undefined) {
                    node.color = undefined;
                }
                
                // Clear highlight timestamps
                if (node.highlightStartTs !== undefined) {
                    node.highlightStartTs = null;
                }
                
                // For Logging nodes specifically, also reset display text and results
                if (node?.type === 'Logging' && typeof node.reset === 'function') {
                    node.reset();
                }
                
                // Force canvas redraw
                if (typeof node.setDirtyCanvas === 'function') {
                    node.setDirtyCanvas(true, true);
                }
            } catch (err) {
                console.warn('Error resetting node:', err);
            }
        });

        // Update UI state
        hideOverlay();
        showStopButton();
        
        const statusService = getStatusService();
        statusService?.startConnecting();

        // Reuse existing WebSocket connection or create new one
        const protocol = window.location.protocol === 'https:' ? 'wss' : 'ws';
        const backendHost = window.location.hostname;
        const wsUrl = `${protocol}://${backendHost}${window.location.port === '8000' ? '' : ':8000'}/execute`;
        
        if (!ws || ws.readyState !== WebSocket.OPEN) {
            // Create new WebSocket connection
            ws = new WebSocket(wsUrl);

            ws.onopen = () => {
                // Send connect message first to establish session
                const connectMessage: ClientToServerMessage = sessionId 
                    ? { type: 'connect', session_id: sessionId }
                    : { type: 'connect' };
                ws?.send(JSON.stringify(connectMessage));
            };

            ws.onmessage = (event) => {
                const data: ServerToClientMessage = JSON.parse(event.data);

                // Handle session message
                if (isSessionMessage(data)) {
                    sessionId = data.session_id;
                    localStorage.setItem('session_id', sessionId);
                    console.log('Session established:', sessionId);
                    
                    // Now send the graph execution message
                    const statusService = getStatusService();
                    statusService?.setConnection('executing', 'Executing...');
                    const message: ClientToServerMessage = { type: 'graph', graph_data: graphData as any };
                    ws?.send(JSON.stringify(message));
                    return;
                }

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
                } else if (isQueuePositionMessage(data)) {
                    handleQueuePositionMessage(data);
                }
            };

            ws.onclose = (event) => {
                console.log(`WebSocket closed: code=${event.code}, reason=${event.reason}`);
                if (event.code !== 1000) {
                    const statusService = getStatusService();
                    statusService?.setConnection('disconnected', 'Disconnected');
                }
            };

            ws.onerror = (err) => {
                console.error('WebSocket error:', err);
                const statusService = getStatusService();
                statusService?.setConnection('disconnected', 'Connection error');
                closeWebSocket();
                forceCleanup();
            };
        } else {
            // Reuse existing connection - send graph execution directly
            const statusService = getStatusService();
            statusService?.setConnection('executing', 'Executing...');
            const message: ClientToServerMessage = { type: 'graph', graph_data: graphData as any };
            ws.send(JSON.stringify(message));
        }
    });

    document.getElementById('stop')?.addEventListener('click', () => {
        stopExecution().catch(err => console.error('Error stopping execution:', err));
    });
}
