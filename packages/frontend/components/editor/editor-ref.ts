// components/editor/editor-ref.ts
// Module-level ref for the ReteAdapter instance.
// Allows FileManager, WebSocketClient, and other services to access the adapter
// without prop-drilling or React context.

import type { ReteAdapter } from './rete-adapter';

let _adapter: ReteAdapter | null = null;

export function setEditorAdapter(a: ReteAdapter): void {
  _adapter = a;
}

export function getEditorAdapter(): ReteAdapter | null {
  return _adapter;
}
