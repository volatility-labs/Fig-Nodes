import type { NodeRegistry, SerialisableGraph } from '../types';
/**
 * Get all required API keys for a given graph by inspecting the
 * `required_keys` static property on each node class used in the graph.
 */
export declare function getRequiredKeysForGraph(graph: SerialisableGraph, nodeRegistry: NodeRegistry): string[];
