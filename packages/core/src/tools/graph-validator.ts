// src/tools/graph-validator.ts
// Validates GraphDocument structure and semantic correctness

import type { NodeRegistry } from '../types';
import type { GraphDocument, GraphEdge } from '../types/graph-document';
import { parseEdgeEndpoint } from '../types/graph-document';
import { areTypesCompatible } from '../utils/type-utils';

export interface ValidationError {
  path: string;
  message: string;
}

export interface ValidationResult {
  valid: boolean;
  errors: ValidationError[];
}

/**
 * Validate a GraphDocument for structural correctness and (optionally)
 * semantic correctness against a node registry.
 */
export function validateGraphDocument(
  doc: unknown,
  nodeRegistry?: NodeRegistry,
): ValidationResult {
  const errors: ValidationError[] = [];

  // Structural checks
  if (!doc || typeof doc !== 'object') {
    return { valid: false, errors: [{ path: '', message: 'Document must be an object' }] };
  }

  const d = doc as Record<string, unknown>;

  if (typeof d.id !== 'string' || d.id.length === 0) {
    errors.push({ path: 'id', message: 'id must be a non-empty string' });
  }
  if (typeof d.name !== 'string') {
    errors.push({ path: 'name', message: 'name must be a string' });
  }
  if (d.version !== 2) {
    errors.push({ path: 'version', message: 'version must be 2' });
  }
  if (!d.nodes || typeof d.nodes !== 'object' || Array.isArray(d.nodes)) {
    errors.push({ path: 'nodes', message: 'nodes must be a Record<string, GraphNode>' });
    return { valid: false, errors };
  }
  if (!Array.isArray(d.edges)) {
    errors.push({ path: 'edges', message: 'edges must be an array' });
    return { valid: false, errors };
  }

  const nodes = d.nodes as Record<string, unknown>;
  const edges = d.edges as unknown[];

  // Validate each node
  for (const [nodeId, nodeVal] of Object.entries(nodes)) {
    if (!nodeVal || typeof nodeVal !== 'object') {
      errors.push({ path: `nodes.${nodeId}`, message: 'node must be an object' });
      continue;
    }
    const node = nodeVal as Record<string, unknown>;

    if (typeof node.type !== 'string' || node.type.length === 0) {
      errors.push({ path: `nodes.${nodeId}.type`, message: 'type must be a non-empty string' });
    }
    if (node.params !== undefined && (typeof node.params !== 'object' || node.params === null || Array.isArray(node.params))) {
      errors.push({ path: `nodes.${nodeId}.params`, message: 'params must be a Record<string, unknown>' });
    }
    if (node.position !== undefined) {
      if (!Array.isArray(node.position) || node.position.length !== 2 ||
        typeof node.position[0] !== 'number' || typeof node.position[1] !== 'number') {
        errors.push({ path: `nodes.${nodeId}.position`, message: 'position must be [number, number]' });
      }
    }
    if (node.size !== undefined) {
      if (!Array.isArray(node.size) || node.size.length !== 2 ||
        typeof node.size[0] !== 'number' || typeof node.size[1] !== 'number') {
        errors.push({ path: `nodes.${nodeId}.size`, message: 'size must be [number, number]' });
      }
    }

    // Registry-based validation
    if (nodeRegistry && typeof node.type === 'string' && !(node.type in nodeRegistry)) {
      errors.push({ path: `nodes.${nodeId}.type`, message: `Unknown node type: "${node.type}"` });
    }
  }

  // Validate each edge
  for (let i = 0; i < edges.length; i++) {
    const edge = edges[i] as Record<string, unknown>;
    if (!edge || typeof edge !== 'object') {
      errors.push({ path: `edges[${i}]`, message: 'edge must be an object' });
      continue;
    }

    if (typeof edge.from !== 'string') {
      errors.push({ path: `edges[${i}].from`, message: 'from must be a string' });
      continue;
    }
    if (typeof edge.to !== 'string') {
      errors.push({ path: `edges[${i}].to`, message: 'to must be a string' });
      continue;
    }

    // Validate endpoint format
    try {
      const from = parseEdgeEndpoint(edge.from);
      if (!(from.nodeId in nodes)) {
        errors.push({ path: `edges[${i}].from`, message: `References non-existent node: "${from.nodeId}"` });
      }
    } catch {
      errors.push({ path: `edges[${i}].from`, message: `Invalid format: "${edge.from}" (expected "nodeId.portName")` });
    }

    try {
      const to = parseEdgeEndpoint(edge.to);
      if (!(to.nodeId in nodes)) {
        errors.push({ path: `edges[${i}].to`, message: `References non-existent node: "${to.nodeId}"` });
      }
    } catch {
      errors.push({ path: `edges[${i}].to`, message: `Invalid format: "${edge.to}" (expected "nodeId.portName")` });
    }
  }

  // Check for duplicate edges
  const edgeKeys = new Set<string>();
  for (let i = 0; i < edges.length; i++) {
    const edge = edges[i] as GraphEdge;
    if (typeof edge?.from === 'string' && typeof edge?.to === 'string') {
      const key = `${edge.from}->${edge.to}`;
      if (edgeKeys.has(key)) {
        errors.push({ path: `edges[${i}]`, message: `Duplicate edge: ${key}` });
      }
      edgeKeys.add(key);
    }
  }

  // Edge type compatibility checks (when registry is available)
  if (nodeRegistry) {
    const edgeTypeErrors = validateEdgeTypes(d as unknown as GraphDocument, nodeRegistry);
    errors.push(...edgeTypeErrors);
  }

  return { valid: errors.length === 0, errors };
}

/**
 * Validate that each edge connects type-compatible ports.
 * Looks up the static `inputs`/`outputs` on node classes from the registry.
 */
export function validateEdgeTypes(
  doc: GraphDocument,
  nodeRegistry: NodeRegistry,
): ValidationError[] {
  const errors: ValidationError[] = [];

  for (let i = 0; i < doc.edges.length; i++) {
    const edge = doc.edges[i]!;
    let from, to;
    try {
      from = parseEdgeEndpoint(edge.from);
      to = parseEdgeEndpoint(edge.to);
    } catch {
      continue; // Malformed edges are caught by structural validation
    }

    const sourceNode = doc.nodes[from.nodeId];
    const targetNode = doc.nodes[to.nodeId];
    if (!sourceNode || !targetNode) continue;

    const SourceClass = nodeRegistry[sourceNode.type] as
      | (Function & { outputs?: Record<string, unknown> })
      | undefined;
    const TargetClass = nodeRegistry[targetNode.type] as
      | (Function & { inputs?: Record<string, unknown> })
      | undefined;
    if (!SourceClass || !TargetClass) continue;

    const outputTypeStr = SourceClass.outputs?.[from.portName];
    const inputTypeStr = TargetClass.inputs?.[to.portName];
    if (outputTypeStr == null || inputTypeStr == null) continue;

    if (!areTypesCompatible(String(outputTypeStr), String(inputTypeStr))) {
      errors.push({
        path: `edges[${i}]`,
        message: `Type mismatch: output "${from.portName}" (${outputTypeStr}) → input "${to.portName}" (${inputTypeStr})`,
      });
    }
  }

  return errors;
}

/**
 * Check for cycles in the graph using DFS.
 */
export function hasCycles(doc: GraphDocument): boolean {
  const adj = new Map<string, string[]>();

  for (const id of Object.keys(doc.nodes)) {
    adj.set(id, []);
  }

  for (const edge of doc.edges) {
    try {
      const from = parseEdgeEndpoint(edge.from);
      const to = parseEdgeEndpoint(edge.to);
      if (adj.has(from.nodeId)) {
        adj.get(from.nodeId)!.push(to.nodeId);
      }
    } catch {
      // skip malformed edges
    }
  }

  const visited = new Set<string>();
  const inStack = new Set<string>();

  function dfs(node: string): boolean {
    visited.add(node);
    inStack.add(node);

    for (const neighbor of adj.get(node) ?? []) {
      if (inStack.has(neighbor)) return true;
      if (!visited.has(neighbor) && dfs(neighbor)) return true;
    }

    inStack.delete(node);
    return false;
  }

  for (const node of adj.keys()) {
    if (!visited.has(node) && dfs(node)) return true;
  }

  return false;
}
