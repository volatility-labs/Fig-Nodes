// components/editor/add-node.ts
// Shared utility for adding a node to the Rete editor.

import type { ReteAdapter } from './rete-adapter';
import type { NodeSchemaMap } from '../../types/nodes';

export function addNodeToEditor(
  adapter: ReteAdapter,
  type: string,
  position: [number, number],
  nodeMetadata: NodeSchemaMap,
): void {
  const meta = nodeMetadata[type];
  const id = `${type.toLowerCase()}_${Date.now()}`;
  adapter.addNode(id, {
    type,
    params: meta?.params
      ? Object.fromEntries(meta.params.filter(p => p.default !== undefined).map(p => [p.name, p.default]))
      : {},
    position,
  });
}
