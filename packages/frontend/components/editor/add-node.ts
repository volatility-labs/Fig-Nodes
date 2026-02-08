// components/editor/add-node.ts
// Shared utility for adding a node to the Rete editor.

import type { ReteAdapter } from './rete-adapter';
import type { NodeMetadataMap } from '../../types/nodes';

export function addNodeToEditor(
  adapter: ReteAdapter,
  type: string,
  position: [number, number],
  nodeMetadata: NodeMetadataMap,
): void {
  const meta = nodeMetadata[type];
  const id = `${type.toLowerCase()}_${Date.now()}`;
  adapter.addNode(id, {
    type,
    params: meta?.defaultParams ? { ...meta.defaultParams } : {},
    position,
  });
}
