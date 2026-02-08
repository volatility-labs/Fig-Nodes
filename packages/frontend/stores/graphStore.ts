// stores/graphStore.ts
// Execution-related reactive state only.
// Graph structure lives in Rete (the single source of truth).

import { create } from 'zustand';
import type { ConnectionStatus } from '../services/ExecutionStatusService';

export interface ExecutionUI {
  status: ConnectionStatus;
  message: string;
  progress: number | null;
  determinate: boolean;
}

export interface Notification {
  message: string;
  type: 'error' | 'warning' | 'info';
}

interface GraphStore {
  /** Document name for toolbar display / save file naming */
  docName: string;
  /** Document ID for serialization */
  docId: string;

  /** Per-node display results from execution */
  displayResults: Record<string, Record<string, unknown>>;
  /** Per-node execution state */
  nodeStatus: Record<string, { executing: boolean; progress?: number; error?: string }>;

  /** Whether the graph is currently executing */
  isExecuting: boolean;

  /** Generic metadata status entries (e.g. data provider status) */
  metaStatus: Record<string, string>;

  /** Execution UI state (status indicator + progress bar) */
  executionUI: ExecutionUI;

  /** Toast notification */
  notification: Notification | null;

  // Document identity
  setDocName: (name: string) => void;
  setDocId: (id: string) => void;

  // Execution state
  setDisplayResult: (nodeId: string, result: Record<string, unknown>) => void;
  clearDisplayResults: () => void;
  setNodeExecuting: (nodeId: string, executing: boolean) => void;
  setNodeProgress: (nodeId: string, progress: number) => void;
  setNodeError: (nodeId: string, error: string) => void;
  clearNodeStatus: () => void;

  // Toolbar state
  setIsExecuting: (v: boolean) => void;
  setMetaStatus: (key: string, value: string) => void;
  clearMetaStatus: () => void;
  setExecutionUI: (ui: Partial<ExecutionUI>) => void;

  // Notifications
  setNotification: (n: Notification | null) => void;
  clearNotification: () => void;
}

export const useGraphStore = create<GraphStore>((set) => ({
  docName: 'untitled',
  docId: crypto.randomUUID(),
  displayResults: {},
  nodeStatus: {},
  isExecuting: false,
  metaStatus: {},
  executionUI: {
    status: 'connected',
    message: 'Ready',
    progress: 0,
    determinate: true,
  },
  notification: null,

  setDocName: (name) => set({ docName: name }),
  setDocId: (id) => set({ docId: id }),

  setDisplayResult: (nodeId, result) =>
    set((state) => ({
      displayResults: { ...state.displayResults, [nodeId]: result },
    })),

  clearDisplayResults: () => set({ displayResults: {} }),

  setNodeExecuting: (nodeId, executing) =>
    set((state) => ({
      nodeStatus: {
        ...state.nodeStatus,
        [nodeId]: { ...state.nodeStatus[nodeId], executing, progress: undefined, error: undefined },
      },
    })),

  setNodeProgress: (nodeId, progress) =>
    set((state) => ({
      nodeStatus: {
        ...state.nodeStatus,
        [nodeId]: { ...state.nodeStatus[nodeId], executing: true, progress },
      },
    })),

  setNodeError: (nodeId, error) =>
    set((state) => ({
      nodeStatus: {
        ...state.nodeStatus,
        [nodeId]: { executing: false, error },
      },
    })),

  clearNodeStatus: () => set({ nodeStatus: {} }),

  setIsExecuting: (v) => set({ isExecuting: v }),
  setMetaStatus: (key, value) =>
    set((state) => ({
      metaStatus: { ...state.metaStatus, [key]: value },
    })),
  clearMetaStatus: () => set({ metaStatus: {} }),
  setExecutionUI: (ui) =>
    set((state) => ({
      executionUI: { ...state.executionUI, ...ui },
    })),

  setNotification: (n) => set({ notification: n }),
  clearNotification: () => set({ notification: null }),
}));
