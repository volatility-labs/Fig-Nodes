/**
 * FileManager - Graph save/load using GraphDocument format
 *
 * Supports:
 * - Saving GraphDocument as JSON
 * - Loading GraphDocument
 * - Autosave to localStorage
 */

import { validateGraphDocument } from '@fig-node/core';
import type { GraphDocument } from '@fig-node/core';
import { useGraphStore } from '../stores/graph-store';
import type { NodeMetadataMap } from '../types/node-metadata';
import { APIKeyManager } from './APIKeyManager';

let lastSavedJson = '';
let autosaveInterval: ReturnType<typeof setInterval> | null = null;
const apiKeyManager = new APIKeyManager();

// ============ Save ============

export function saveGraph(): void {
  const doc = useGraphStore.getState().doc;
  const json = JSON.stringify(doc, null, 2);
  const blob = new Blob([json], { type: 'application/json' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = doc.name.endsWith('.json') ? doc.name : `${doc.name}.json`;
  a.click();
  URL.revokeObjectURL(url);
  lastSavedJson = json;
}

// ============ Load ============

export async function loadGraphFromFile(
  file: File,
  _nodeMetadata?: NodeMetadataMap,
): Promise<void> {
  try {
    const content = await file.text();
    const data = JSON.parse(content);

    let doc: GraphDocument;

    // Validate GraphDocument format (version === 2, nodes as Record)
    if (data.version === 2 && data.nodes && !Array.isArray(data.nodes)) {
      const validation = validateGraphDocument(data);
      if (!validation.valid) {
        try {
          alert('Invalid graph document: ' + validation.errors.map((e) => e.message).join(', '));
        } catch { /* ignore in tests */ }
        return;
      }
      doc = data as GraphDocument;
    } else {
      try { alert('Unsupported graph format. Only GraphDocument (version 2) is supported.'); } catch { /* ignore in tests */ }
      return;
    }

    useGraphStore.getState().loadDocument(doc);
    updateGraphName(file.name);

    try {
      lastSavedJson = JSON.stringify(doc);
    } catch {
      lastSavedJson = '';
    }

    // Proactive API key check after load
    try {
      const requiredKeys = await apiKeyManager.getRequiredKeysForGraph(data);
      if (requiredKeys.length > 0) {
        const missing = await apiKeyManager.checkMissingKeys(requiredKeys);
        if (missing.length > 0) {
          try {
            alert(`Missing API keys for this graph: ${missing.join(', ')}. Please set them in the settings menu.`);
          } catch { /* ignore in tests */ }
          apiKeyManager.openSettings(missing);
        }
      }
    } catch { /* ignore */ }
  } catch {
    try { alert('Invalid graph file'); } catch { /* ignore in tests */ }
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
    const doc = useGraphStore.getState().doc;
    const json = JSON.stringify(doc);
    if (json !== lastSavedJson) {
      const payload = { graph: doc, name: doc.name };
      safeLocalStorageSet('fig-nodes:autosave:v2', JSON.stringify(payload));
      lastSavedJson = json;
    }
  } catch { /* ignore */ }
}

export function restoreFromAutosave(): boolean {
  try {
    const saved = safeLocalStorageGet('fig-nodes:autosave:v2');
    if (saved) {
      const parsed = JSON.parse(saved);
      if (parsed?.graph?.version === 2) {
        const validation = validateGraphDocument(parsed.graph);
        if (validation.valid) {
          useGraphStore.getState().loadDocument(parsed.graph as GraphDocument);
          updateGraphName(parsed.name || 'autosave.json');
          lastSavedJson = JSON.stringify(parsed.graph);
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
  const graphNameEl = document.getElementById('graph-name');
  if (graphNameEl) graphNameEl.textContent = name;
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
