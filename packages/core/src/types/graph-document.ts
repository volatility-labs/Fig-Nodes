// src/types/graph-document.ts
// Clean, LLM-friendly graph document schema
// This is the single source of truth for graph state in the new Svelte Flow editor.

// ============ Core Types ============

export interface GraphNode {
  type: string;
  params: Record<string, unknown>;
  title?: string;
  position?: [number, number];
  size?: [number, number];
}

export interface GraphEdge {
  from: string; // "nodeId.outputName"
  to: string;   // "nodeId.inputName"
}

export interface GraphGroup {
  id: string;
  title: string;
  color?: string;
  bounds: { x: number; y: number; width: number; height: number };
  children?: string[]; // node IDs
}

export interface GraphLayout {
  zoom?: number;
  offset?: [number, number];
}

export interface GraphDocument {
  id: string;
  name: string;
  version: 2;
  nodes: Record<string, GraphNode>;       // "chat_1" -> { type, params }
  edges: GraphEdge[];                      // [{ from: "node.output", to: "node.input" }]
  groups?: GraphGroup[];
  layout?: GraphLayout;
}

// ============ Factory ============

export function createEmptyDocument(name = 'untitled'): GraphDocument {
  return {
    id: crypto.randomUUID(),
    name,
    version: 2,
    nodes: {},
    edges: [],
  };
}

// ============ Edge Helpers ============

export function parseEdgeEndpoint(endpoint: string): { nodeId: string; portName: string } {
  const dotIndex = endpoint.indexOf('.');
  if (dotIndex === -1) {
    throw new Error(`Invalid edge endpoint: "${endpoint}" (expected "nodeId.portName")`);
  }
  return {
    nodeId: endpoint.substring(0, dotIndex),
    portName: endpoint.substring(dotIndex + 1),
  };
}

export function makeEdgeEndpoint(nodeId: string, portName: string): string {
  return `${nodeId}.${portName}`;
}
