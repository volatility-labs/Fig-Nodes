/**
 * FileManager - Graph save/load using Graph format
 *
 * Serializes from Rete (the single source of truth) via the adapter.
 *
 * Supports:
 * - Saving Graph as JSON
 * - Loading Graph
 * - Autosave to localStorage
 */

import { validateGraph } from '@fig-node/core';
import type { Graph } from '@fig-node/core';
import { useGraphStore } from '../stores/graphStore';
import { getEditorAdapter } from '../components/editor/editor-ref';
import { isDirty, clearDirty } from '../components/editor/editor-actions';
import type { NodeMetadataMap } from '../types/nodes';

let lastSavedJson = '';
let autosaveInterval: ReturnType<typeof setInterval> | null = null;

// ============ Helpers ============

function getSerializedDoc(): Graph | null {
  const adapter = getEditorAdapter();
  if (!adapter) return null;
  const { docName, docId } = useGraphStore.getState();
  return adapter.serializeGraph(docName, docId);
}

// ============ Save ============

export function saveGraph(): void {
  const doc = getSerializedDoc();
  if (!doc) return;

  const json = JSON.stringify(doc, null, 2);
  const blob = new Blob([json], { type: 'application/json' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = doc.name.endsWith('.json') ? doc.name : `${doc.name}.json`;
  a.click();
  URL.revokeObjectURL(url);
  lastSavedJson = json;
  clearDirty();
}

// ============ Load ============

export async function loadGraphFromFile(
  file: File,
  _nodeMetadata?: NodeMetadataMap,
): Promise<void> {
  try {
    const content = await file.text();
    const data = JSON.parse(content);

    let doc: Graph;

    // Validate Graph format (version === 2, nodes as Record)
    if (data.version === 2 && data.nodes && !Array.isArray(data.nodes)) {
      const validation = validateGraph(data);
      if (!validation.valid) {
        useGraphStore.getState().setNotification({
          message: 'Invalid graph document: ' + validation.errors.map((e) => e.message).join(', '),
          type: 'error',
        });
        return;
      }
      doc = data as Graph;
    } else {
      useGraphStore.getState().setNotification({
        message: 'Unsupported graph format. Only Graph (version 2) is supported.',
        type: 'error',
      });
      return;
    }

    // Load into Rete (the source of truth)
    const adapter = getEditorAdapter();
    if (adapter) {
      await adapter.loadDocument(doc);
    }

    // Update store identity
    updateGraphName(file.name);
    useGraphStore.getState().setDocId(doc.id);
    useGraphStore.getState().clearDisplayResults();
    useGraphStore.getState().clearNodeStatus();

    try {
      lastSavedJson = JSON.stringify(doc);
    } catch {
      lastSavedJson = '';
    }
    clearDirty();
  } catch {
    useGraphStore.getState().setNotification({ message: 'Invalid graph file', type: 'error' });
  }
}

// ============ Autosave ============

export function startAutosave(): () => void {
  autosaveInterval = setInterval(doAutosave, 30_000);
  return () => {
    if (autosaveInterval !== null) {
      clearInterval(autosaveInterval);
      autosaveInterval = null;
    }
  };
}

function doAutosave(): void {
  try {
    if (!isDirty()) return;

    const doc = getSerializedDoc();
    if (!doc) return;

    const json = JSON.stringify(doc);
    if (json !== lastSavedJson) {
      const payload = { graph: doc, name: doc.name };
      safeLocalStorageSet('fig-nodes:autosave:v2', JSON.stringify(payload));
      lastSavedJson = json;
    }
    clearDirty();
  } catch { /* ignore */ }
}

export function restoreFromAutosave(): boolean {
  try {
    const saved = safeLocalStorageGet('fig-nodes:autosave:v2');
    if (saved) {
      const parsed = JSON.parse(saved);
      if (parsed?.graph?.version === 2) {
        const validation = validateGraph(parsed.graph);
        if (validation.valid) {
          const doc = parsed.graph as Graph;

          // Load into Rete via adapter
          const adapter = getEditorAdapter();
          if (adapter) {
            adapter.loadDocument(doc);
          }

          updateGraphName(parsed.name || 'autosave.json');
          useGraphStore.getState().setDocId(doc.id);
          lastSavedJson = JSON.stringify(doc);
          return true;
        }
      }
    }

  } catch {
    return false;
  }
  return false;
}

// ============ Helpers ============

function updateGraphName(name: string): void {
  useGraphStore.getState().setDocName(name);
}

function safeLocalStorageSet(key: string, value: string): void {
  try {
    localStorage.setItem(key, value);
  } catch (err) {
    console.error('Autosave failed:', err);
  }
}

function safeLocalStorageGet(key: string): string | null {
  try {
    return localStorage.getItem(key);
  } catch {
    return null;
  }
}
