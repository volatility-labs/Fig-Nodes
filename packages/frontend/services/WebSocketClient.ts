/**
 * WebSocket Client for Graph Execution
 *
 * Handles WebSocket communication between the frontend and backend execution queue.
 * Uses GraphDocument store instead of LiteGraph.
 */

import { useGraphStore } from '../stores/graph-store';
import { APIKeyManager } from './APIKeyManager';
import type { ExecutionResults } from '../types/resultTypes';
import type {
  ClientToServerMessage,
  ServerToClientMessage,
} from '../types/websocketType';
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
  type ServerToClientQueuePositionMessage,
} from '../types/websocketType';
import type { ExecutionStatusService } from './ExecutionStatusService';

// ============ State ============

let ws: WebSocket | null = null;
let stopPromiseResolver: (() => void) | null = null;
let sessionId: string | null = localStorage.getItem('session_id');
let statusService: ExecutionStatusService | null = null;
const apiKeyManager = new APIKeyManager();

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

function clearAllHighlights() {
  useGraphStore.getState().clearNodeStatus();
}

// ============ Stop Execution ============

export async function stopExecution(): Promise<void> {
  const currentState = statusService?.getState() ?? 'connected';
  if (currentState === 'connected' || currentState === 'stopping') return;

  statusService?.setStopping();

  return new Promise((resolve) => {
    stopPromiseResolver = resolve;
    if (ws && ws.readyState === WebSocket.OPEN) {
      const message: ClientToServerMessage = { type: 'stop' };
      ws.send(JSON.stringify(message));
    } else {
      closeWebSocket();
      forceCleanup();
      resolve();
    }
  });
}

function forceCleanup() {
  showExecuteButton();
  clearAllHighlights();
  statusService?.setIdle();
  if (stopPromiseResolver) {
    stopPromiseResolver();
    stopPromiseResolver = null;
  }
}

function closeWebSocket() {
  if (ws) {
    ws.close();
    ws = null;
  }
}

// ============ Message Handlers ============

function handleErrorMessage(data: { message: string; code?: string; missing_keys?: string[] }) {
  console.error('Execution error:', data.message);
  statusService?.error(null, data.message);

  if (data.code === 'MISSING_API_KEYS' && Array.isArray(data.missing_keys)) {
    try { alert(data.message || 'Missing API keys. Opening settings...'); } catch { /* ignore in tests */ }
    apiKeyManager.setLastMissingKeys(data.missing_keys);
    apiKeyManager.openSettings(data.missing_keys);
  } else {
    try { alert('Error: ' + data.message); } catch { /* ignore in tests */ }
  }

  closeWebSocket();
  forceCleanup();
}

function handleStatusMessage(message: ServerToClientStatusMessage) {
  if (statusService?.getCurrentJobId() !== message.job_id) {
    statusService?.adoptJob(message.job_id);
  }
  statusService?.updateFromBackendState(message.state, message.message, message.job_id);

  if (message.state === 'finished' || message.state === 'error') {
    showExecuteButton();
  }
}

function handleStoppedMessage(_data: { message: string }) {
  showExecuteButton();
  clearAllHighlights();
  statusService?.stopped(null);
  if (stopPromiseResolver) {
    stopPromiseResolver();
    stopPromiseResolver = null;
  }
}

function handleDataMessage(data: { results: ExecutionResults }) {
  if (Object.keys(data.results).length === 0) {
    statusService?.setProgress(null, undefined, 'Running...');
    return;
  }

  const store = useGraphStore.getState();
  for (const nodeId in data.results) {
    const result = data.results[nodeId];
    if (result) {
      store.setDisplayResult(nodeId, result);
    }
  }

  statusService?.setProgress(null, undefined, 'Running...');
}

function handleProgressMessage(data: {
  node_id?: string;
  progress?: number;
  text?: string;
  state?: ProgressState;
  meta?: Record<string, unknown>;
}) {
  if (data.node_id === undefined) return;

  const nodeId = data.node_id;
  const store = useGraphStore.getState();
  const state = data.state;

  if (state === ProgressState.START || state === ProgressState.UPDATE) {
    store.setNodeExecuting(nodeId, true);
    if (data.progress !== undefined) {
      store.setNodeProgress(nodeId, data.progress);
    }
  } else if (state === ProgressState.DONE || state === ProgressState.STOPPED) {
    store.setNodeExecuting(nodeId, false);
  } else if (state === ProgressState.ERROR) {
    store.setNodeError(nodeId, data.text ?? 'Error');
  }

  // Handle polygon data status metadata
  if (data.meta?.polygon_data_status) {
    updatePolygonStatus(data.meta.polygon_data_status as string);
  }
}

function updatePolygonStatus(status: string) {
  const element = document.getElementById('polygon-status');
  if (!element) return;

  element.className = `polygon-status ${status}`;
  const labels: Record<string, string> = {
    'real-time': 'Real-Time',
    'delayed': 'Delayed',
    'market-closed': 'Market Closed',
    'unknown': 'Unknown',
    'na': 'N/A',
  };
  element.textContent = labels[status] || status;
  element.setAttribute('title', `Polygon Data Status: ${labels[status] || status}`);
}

function handleQueuePositionMessage(message: ServerToClientQueuePositionMessage) {
  const position = message.position;
  if (position === 0) {
    statusService?.setQueuePosition(statusService.getCurrentJobId() ?? -1, 0);
  } else {
    statusService?.setQueuePosition(statusService.getCurrentJobId() ?? -1, position);
  }
}

// ============ Setup ============

export function setupWebSocket(service: ExecutionStatusService) {
  statusService = service;

  // Listen for execute event from the toolbar
  window.addEventListener('fig:execute', async () => {
    if (statusService?.getState() === 'stopping') {
      console.warn('Cannot start execution while stopping previous one');
      return;
    }

    // Get graph document from store — send directly to backend
    const doc = useGraphStore.getState().doc;

    // Preflight API key check
    try {
      const requiredKeys = await apiKeyManager.getRequiredKeysForGraph(doc as unknown as Record<string, unknown>);
      if (requiredKeys.length > 0) {
        const missing = await apiKeyManager.checkMissingKeys(requiredKeys);
        if (missing.length > 0) {
          try {
            alert(`Missing API keys for this graph: ${missing.join(', ')}. Please set them in the settings menu.`);
          } catch { /* ignore in tests */ }
          apiKeyManager.setLastMissingKeys(missing);
          await apiKeyManager.openSettings(missing);
          showExecuteButton();
          return;
        }
      }
    } catch {
      // Fall back to server-side validation
    }

    // Clear previous execution state
    useGraphStore.getState().clearNodeStatus();
    useGraphStore.getState().clearDisplayResults();

    showStopButton();
    statusService?.startConnecting();

    // WebSocket connection
    const protocol = window.location.protocol === 'https:' ? 'wss' : 'ws';
    const backendHost = window.location.hostname;
    const wsUrl = `${protocol}://${backendHost}${window.location.port === '8000' ? '' : ':8000'}/execute`;

    if (!ws || ws.readyState !== WebSocket.OPEN) {
      ws = new WebSocket(wsUrl);

      ws.onopen = () => {
        const connectMessage: ClientToServerMessage = sessionId
          ? { type: 'connect', session_id: sessionId }
          : { type: 'connect' };
        ws?.send(JSON.stringify(connectMessage));
      };

      ws.onmessage = (event) => {
        const data: ServerToClientMessage = JSON.parse(event.data as string);

        if (isSessionMessage(data)) {
          sessionId = data.session_id;
          localStorage.setItem('session_id', sessionId);
          statusService?.setConnection('executing', 'Executing...');
          const message: ClientToServerMessage = { type: 'graph', graph_data: doc };
          ws?.send(JSON.stringify(message));
          return;
        }

        if (isErrorMessage(data)) handleErrorMessage(data);
        else if (isStatusMessage(data)) handleStatusMessage(data);
        else if (isStoppedMessage(data)) handleStoppedMessage(data);
        else if (isDataMessage(data)) handleDataMessage(data);
        else if (isProgressMessage(data)) handleProgressMessage(data);
        else if (isQueuePositionMessage(data)) handleQueuePositionMessage(data);
      };

      ws.onclose = (event) => {
        if (event.code !== 1000) {
          statusService?.setConnection('disconnected', 'Disconnected');
        }
      };

      ws.onerror = () => {
        statusService?.setConnection('disconnected', 'Connection error');
        closeWebSocket();
        forceCleanup();
      };
    } else {
      statusService?.setConnection('executing', 'Executing...');
      const message: ClientToServerMessage = { type: 'graph', graph_data: doc };
      ws.send(JSON.stringify(message));
    }
  });
}
