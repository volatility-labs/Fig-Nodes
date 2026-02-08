/**
 * WebSocket Client for Graph Execution
 *
 * Handles WebSocket communication between the frontend and backend execution queue.
 * Serializes graph from Rete (the single source of truth) via the adapter.
 */

import { useGraphStore } from '../stores/graphStore';
import { getEditorAdapter } from '../components/editor/editor-ref';
import {
  ProgressState,
  isErrorMessage,
  isStatusMessage,
  isStoppedMessage,
  isDataMessage,
  isProgressMessage,
  isQueuePositionMessage,
  isSessionMessage,
  type ExecutionResults,
  type ClientMessage,
  type ServerMessage,
  type ServerStatusMessage,
  type ServerErrorMessage,
  type ServerQueuePositionMessage,
} from '@fig-node/core';
import type { ExecutionStatusService } from './ExecutionStatusService';

// ============ State ============

let ws: WebSocket | null = null;
let stopPromiseResolver: (() => void) | null = null;
let sessionId: string | null = localStorage.getItem('session_id');
let statusService: ExecutionStatusService | null = null;
let reconnectAttempts = 0;
const MAX_RECONNECT_ATTEMPTS = 5;
const BASE_RECONNECT_DELAY_MS = 1000;

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
      const message: ClientMessage = { type: 'stop' };
      ws.send(JSON.stringify(message));
    } else {
      closeWebSocket();
      forceCleanup();
      resolve();
    }
  });
}

function forceCleanup() {
  useGraphStore.getState().setIsExecuting(false);
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

function handleErrorMessage(data: ServerErrorMessage) {
  console.error('Execution error:', data.message);
  statusService?.error(null, data.message);

  if (data.code === 'MISSING_API_KEYS') {
    useGraphStore.getState().setNotification({ message: data.message || 'Missing API keys. Check your .env file.', type: 'error' });
  } else {
    useGraphStore.getState().setNotification({ message: 'Error: ' + data.message, type: 'error' });
  }

  closeWebSocket();
  forceCleanup();
}

function handleStatusMessage(message: ServerStatusMessage) {
  if (statusService?.getCurrentJobId() !== message.job_id) {
    statusService?.adoptJob(message.job_id);
  }
  statusService?.updateFromBackendState(message.state, message.message, message.job_id);

  if (message.state === 'finished' || message.state === 'error') {
    useGraphStore.getState().setIsExecuting(false);
  }
}

function handleStoppedMessage(_data: { message: string }) {
  useGraphStore.getState().setIsExecuting(false);
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
  node_id: string;
  progress?: number;
  text?: string;
  state?: ProgressState;
  meta?: Record<string, unknown>;
}) {
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

  // Forward string metadata entries to the store
  if (data.meta) {
    const store = useGraphStore.getState();
    for (const [key, val] of Object.entries(data.meta)) {
      if (typeof val === 'string') {
        store.setMetaStatus(key, val);
      }
    }
  }
}

function handleQueuePositionMessage(message: ServerQueuePositionMessage) {
  const position = message.position;
  if (position === 0) {
    statusService?.setQueuePosition(statusService.getCurrentJobId() ?? -1, 0);
  } else {
    statusService?.setQueuePosition(statusService.getCurrentJobId() ?? -1, position);
  }
}

// ============ WebSocket Wiring ============

function getWsUrl(): string {
  const protocol = window.location.protocol === 'https:' ? 'wss' : 'ws';
  const backendHost = window.location.hostname;
  return `${protocol}://${backendHost}${window.location.port === '8000' ? '' : ':8000'}/execute`;
}

function dispatchMessage(data: ServerMessage) {
  if (isErrorMessage(data)) handleErrorMessage(data);
  else if (isStatusMessage(data)) handleStatusMessage(data);
  else if (isStoppedMessage(data)) handleStoppedMessage(data);
  else if (isDataMessage(data)) handleDataMessage(data);
  else if (isProgressMessage(data)) handleProgressMessage(data);
  else if (isQueuePositionMessage(data)) handleQueuePositionMessage(data);
}

/**
 * Create a new WebSocket and wire up handlers.
 * The only variation between initial connect and reconnect is the status label
 * shown after session establishment and the optional close/error callbacks.
 */
function connectWebSocket(
  doc: import('@fig-node/core').Graph,
  sessionLabel: string,
  opts?: { onClose?: () => void; onError?: () => void },
) {
  ws = new WebSocket(getWsUrl());

  ws.onopen = () => {
    reconnectAttempts = 0;
    const connectMessage: ClientMessage = sessionId
      ? { type: 'connect', session_id: sessionId }
      : { type: 'connect' };
    ws?.send(JSON.stringify(connectMessage));
  };

  ws.onmessage = (event) => {
    const data: ServerMessage = JSON.parse(event.data as string);

    if (isSessionMessage(data)) {
      sessionId = data.session_id;
      localStorage.setItem('session_id', sessionId);
      statusService?.setConnection('executing', sessionLabel);
      const message: ClientMessage = { type: 'graph', graph_data: doc };
      ws?.send(JSON.stringify(message));
      return;
    }

    dispatchMessage(data);
  };

  ws.onclose = (event) => {
    if (event.code !== 1000) {
      opts?.onClose?.();
      attemptReconnect(doc);
    }
  };

  ws.onerror = () => {
    opts?.onError?.();
    closeWebSocket();
  };
}

// ============ Reconnection ============

function attemptReconnect(doc: import('@fig-node/core').Graph) {
  if (reconnectAttempts >= MAX_RECONNECT_ATTEMPTS) {
    console.warn(`Max reconnect attempts (${MAX_RECONNECT_ATTEMPTS}) reached`);
    forceCleanup();
    return;
  }

  const delay = BASE_RECONNECT_DELAY_MS * Math.pow(2, reconnectAttempts);
  reconnectAttempts++;
  statusService?.setConnection('disconnected', `Reconnecting in ${Math.round(delay / 1000)}s...`);

  setTimeout(() => {
    if (!useGraphStore.getState().isExecuting) return;
    connectWebSocket(doc, 'Reconnected \u2014 re-executing...');
  }, delay);
}

// ============ Setup ============

export function setupWebSocket(service: ExecutionStatusService) {
  statusService = service;

  window.addEventListener('fig:execute', async () => {
    if (statusService?.getState() === 'stopping') {
      console.warn('Cannot start execution while stopping previous one');
      return;
    }

    const adapter = getEditorAdapter();
    if (!adapter) {
      console.error('No editor adapter available');
      return;
    }
    const { docName, docId } = useGraphStore.getState();
    const doc = adapter.serializeGraph(docName, docId);

    useGraphStore.getState().clearNodeStatus();
    useGraphStore.getState().clearDisplayResults();
    useGraphStore.getState().setIsExecuting(true);
    statusService?.startConnecting();
    reconnectAttempts = 0;

    if (!ws || ws.readyState !== WebSocket.OPEN) {
      connectWebSocket(doc, 'Executing...', {
        onClose: () => statusService?.setConnection('disconnected', 'Disconnected'),
        onError: () => statusService?.setConnection('disconnected', 'Connection error'),
      });
    } else {
      statusService?.setConnection('executing', 'Executing...');
      const message: ClientMessage = { type: 'graph', graph_data: doc };
      ws.send(JSON.stringify(message));
    }
  });
}
