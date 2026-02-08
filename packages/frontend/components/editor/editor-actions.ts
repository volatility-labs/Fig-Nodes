// components/editor/editor-actions.ts
// Non-component editor utilities (dirty flag, undo/redo, auto-arrange).
// Separated from ReteEditor.tsx so React Fast Refresh doesn't choke on
// mixed component + function exports.

import type { NodeEditor } from 'rete';
import type { AreaPlugin } from 'rete-area-plugin';
import { AreaExtensions } from 'rete-area-plugin';
import type { HistoryPlugin } from 'rete-history-plugin';
import type { AutoArrangePlugin } from 'rete-auto-arrange-plugin';
import type { FrontendSchemes, AreaExtra } from './rete-adapter';

// ============ Shared refs (set by ReteEditor on mount) ============

export const editorRefs = {
  editor: null as NodeEditor<FrontendSchemes> | null,
  area: null as AreaPlugin<FrontendSchemes, AreaExtra> | null,
  history: null as HistoryPlugin<FrontendSchemes> | null,
  arrange: null as AutoArrangePlugin<FrontendSchemes> | null,
};

// ============ Dirty flag for autosave ============

let _dirty = false;

export function isDirty(): boolean {
  return _dirty;
}

export function clearDirty(): void {
  _dirty = false;
}

export function markDirty(): void {
  _dirty = true;
}

// ============ Undo / Redo ============

export function undo(): void {
  editorRefs.history?.undo();
}

export function redo(): void {
  editorRefs.history?.redo();
}

// ============ Auto-arrange ============

export async function autoArrange(): Promise<void> {
  const { arrange, area, editor } = editorRefs;
  if (!arrange || !area || !editor) return;

  // Sync node.width / node.height from actual rendered DOM dimensions
  // so ELK doesn't overlap nodes with many ports/widgets.
  for (const node of editor.getNodes()) {
    const view = area.nodeViews.get(node.id);
    if (view?.element) {
      const rect = view.element.getBoundingClientRect();
      const k = area.area.transform.k;
      node.width = rect.width / k;
      node.height = rect.height / k;
    }
  }

  await arrange.layout();
  await AreaExtensions.zoomAt(area as any, editor.getNodes());
  markDirty();
}
