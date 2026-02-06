// stores/flow-adapter.ts
// Converts between GraphDocument and React Flow node/edge format

import type { Node, Edge } from '@xyflow/react';
import type { GraphDocument } from '@fig-node/core';
import { parseEdgeEndpoint } from '@fig-node/core';
import type { NodeUIConfig, ParamMeta } from '@fig-node/core';

// ============ Types ============

/** Metadata about a node type, fetched from /api/v1/nodes */
export interface NodeTypeMetadata {
  inputs: Record<string, unknown>;
  outputs: Record<string, unknown>;
  params: ParamMeta[];
  defaultParams: Record<string, unknown>;
  category: string;
  requiredKeys: string[];
  description: string;
  uiConfig: NodeUIConfig;
}

export type NodeMetadataMap = Record<string, NodeTypeMetadata>;

/** Data shape passed to FigNode component via React Flow's `data` prop.
 *  Contains only structural/static metadata. Dynamic state (params, display
 *  results, execution status) is read by FigNode directly from the store. */
export interface FigNodeData {
  type: string;
  title?: string;
  inputs: Array<{ name: string; type: string }>;
  outputs: Array<{ name: string; type: string }>;
  uiConfig: NodeUIConfig;
  paramsMeta: ParamMeta[];
  [key: string]: unknown;
}

// ============ GraphDocument -> React Flow ============

export function toFlowNodes(
  doc: GraphDocument,
  metadata: NodeMetadataMap,
): Node<FigNodeData>[] {
  return Object.entries(doc.nodes).map(([id, node]) => {
    const meta = metadata[node.type];
    return {
      id,
      type: 'figNode',
      position: { x: node.position?.[0] ?? 0, y: node.position?.[1] ?? 0 },
      data: {
        type: node.type,
        title: node.title,
        inputs: meta
          ? Object.entries(meta.inputs).map(([name, type]) => ({
            name,
            type: String(type),
          }))
          : [],
        outputs: meta
          ? Object.entries(meta.outputs).map(([name, type]) => ({
            name,
            type: String(type),
          }))
          : [],
        uiConfig: meta?.uiConfig ?? {},
        paramsMeta: meta?.params ?? [],
      },
    };
  });
}

export function toFlowEdges(doc: GraphDocument): Edge[] {
  return doc.edges.map((e, i) => {
    const src = parseEdgeEndpoint(e.from);
    const tgt = parseEdgeEndpoint(e.to);
    return {
      id: `e-${i}-${src.nodeId}-${tgt.nodeId}`,
      source: src.nodeId,
      sourceHandle: src.portName,
      target: tgt.nodeId,
      targetHandle: tgt.portName,
      animated: false,
    };
  });
}

// ============ React Flow -> GraphDocument updates ============

/**
 * Convert a React Flow connection event to a GraphEdge
 */
export function connectionToEdge(connection: {
  source: string | null;
  target: string | null;
  sourceHandle: string | null;
  targetHandle: string | null;
}): { from: string; to: string } | null {
  if (!connection.source || !connection.target || !connection.sourceHandle || !connection.targetHandle) {
    return null;
  }
  return {
    from: `${connection.source}.${connection.sourceHandle}`,
    to: `${connection.target}.${connection.targetHandle}`,
  };
}
