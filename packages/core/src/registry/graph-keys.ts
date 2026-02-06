// src/registry/graph-keys.ts
// Pure function to extract required credential keys from a graph

import type { NodeRegistry, SerialisableGraph } from '../types';

/**
 * Get all required API keys for a given graph by inspecting the
 * `required_keys` static property on each node class used in the graph.
 */
export function getRequiredKeysForGraph(
  graph: SerialisableGraph,
  nodeRegistry: NodeRegistry
): string[] {
  const requiredKeys = new Set<string>();

  const nodes = graph.nodes ?? [];
  for (const nodeData of nodes) {
    const nodeType = nodeData.type;
    const NodeClass = nodeRegistry[nodeType];

    if (!NodeClass) {
      continue;
    }

    const keys = (NodeClass as unknown as { required_keys?: string[] }).required_keys ?? [];
    for (const key of keys) {
      if (typeof key === 'string' && key) {
        requiredKeys.add(key);
      }
    }
  }

  return Array.from(requiredKeys);
}
