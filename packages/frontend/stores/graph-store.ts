// stores/graph-store.ts
// Single source of truth for the graph document.
// Uses zustand for React-compatible reactive state.

import { create } from 'zustand';
import type {
  GraphDocument,
  GraphNode,
  GraphEdge,
} from '@fig-node/core';
import { createEmptyDocument } from '@fig-node/core';

interface GraphStore {
  doc: GraphDocument;
  /** Per-node display results from execution */
  displayResults: Record<string, Record<string, unknown>>;
  /** Per-node execution state */
  nodeStatus: Record<string, { executing: boolean; progress?: number; error?: string }>;

  // Document mutations
  loadDocument: (doc: GraphDocument) => void;
  addNode: (id: string, node: GraphNode) => void;
  removeNode: (id: string) => void;
  addEdge: (edge: GraphEdge) => void;
  removeEdge: (from: string, to: string) => void;
  setParam: (nodeId: string, key: string, value: unknown) => void;
  updateNodePosition: (nodeId: string, position: [number, number]) => void;
  setDocName: (name: string) => void;

  // Execution state
  setDisplayResult: (nodeId: string, result: Record<string, unknown>) => void;
  clearDisplayResults: () => void;
  setNodeExecuting: (nodeId: string, executing: boolean) => void;
  setNodeProgress: (nodeId: string, progress: number) => void;
  setNodeError: (nodeId: string, error: string) => void;
  clearNodeStatus: () => void;
}

export const useGraphStore = create<GraphStore>((set) => ({
  doc: createEmptyDocument(),
  displayResults: {},
  nodeStatus: {},

  loadDocument: (doc) =>
    set({ doc, displayResults: {}, nodeStatus: {} }),

  addNode: (id, node) =>
    set((state) => ({
      doc: {
        ...state.doc,
        nodes: { ...state.doc.nodes, [id]: node },
      },
    })),

  removeNode: (id) =>
    set((state) => {
      const { [id]: _, ...remainingNodes } = state.doc.nodes;
      const prefix = `${id}.`;
      const edges = state.doc.edges.filter(
        (e) => !e.from.startsWith(prefix) && !e.to.startsWith(prefix),
      );
      return {
        doc: { ...state.doc, nodes: remainingNodes, edges },
      };
    }),

  addEdge: (edge) =>
    set((state) => {
      const exists = state.doc.edges.some(
        (e) => e.from === edge.from && e.to === edge.to,
      );
      if (exists) return state;
      return {
        doc: { ...state.doc, edges: [...state.doc.edges, edge] },
      };
    }),

  removeEdge: (from, to) =>
    set((state) => ({
      doc: {
        ...state.doc,
        edges: state.doc.edges.filter(
          (e) => !(e.from === from && e.to === to),
        ),
      },
    })),

  setParam: (nodeId, key, value) =>
    set((state) => {
      const node = state.doc.nodes[nodeId];
      if (!node) return state;
      return {
        doc: {
          ...state.doc,
          nodes: {
            ...state.doc.nodes,
            [nodeId]: {
              ...node,
              params: { ...node.params, [key]: value },
            },
          },
        },
      };
    }),

  updateNodePosition: (nodeId, position) =>
    set((state) => {
      const node = state.doc.nodes[nodeId];
      if (!node) return state;
      return {
        doc: {
          ...state.doc,
          nodes: {
            ...state.doc.nodes,
            [nodeId]: { ...node, position },
          },
        },
      };
    }),

  setDocName: (name) =>
    set((state) => ({ doc: { ...state.doc, name } })),

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
}));

// ============ Selectors ============

export function getDocument(): GraphDocument {
  return useGraphStore.getState().doc;
}
