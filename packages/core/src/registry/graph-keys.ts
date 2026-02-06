// src/registry/graph-keys.ts
// Pure function to extract required credential keys from a GraphDocument

import type { NodeRegistry } from '../types';
import type { GraphDocument } from '../types/graph-document';

/**
 * Get all required API keys for a GraphDocument by inspecting the
 * `required_keys` static property on each node class used in the graph.
 */
export function getRequiredKeysForDocument(
  doc: GraphDocument,
  nodeRegistry: NodeRegistry
): string[] {
  const requiredKeys = new Set<string>();

  for (const node of Object.values(doc.nodes)) {
    const NodeClass = nodeRegistry[node.type];
    if (!NodeClass) continue;

    const keys = (NodeClass as unknown as { required_keys?: string[] }).required_keys ?? [];
    for (const key of keys) {
      if (typeof key === 'string' && key) {
        requiredKeys.add(key);
      }
    }
  }

  return Array.from(requiredKeys);
}
