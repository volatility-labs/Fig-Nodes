// components/editor/rete-adapter.ts
// Rete is the single runtime source of truth for graph structure.
// The adapter manages node/edge CRUD and serializes on demand.

import { NodeEditor, ClassicPreset } from 'rete';
import { AreaPlugin } from 'rete-area-plugin';
import type { MinimapExtra } from 'rete-minimap-plugin';
import type { Graph, GraphEdge, GraphNode } from '@sosa/core';
import { parseEdgeEndpoint, getOrCreateSocket } from '@sosa/core';
import type { NodeSchemaMap } from '../../types/nodes';

// ============ Lightweight wrapper for frontend-only nodes ============

/**
 * FigReteNode is a lightweight ClassicPreset.Node used in the frontend editor.
 * It does NOT extend Node (which requires full run()). Instead, it's a
 * simple node with sockets for visual editing only.
 *
 * The node's `id` IS the document ID (no dual-ID mapping needed).
 */
export class FigReteNode extends ClassicPreset.Node {
  nodeType: string;
  params: Record<string, unknown>;
  declare width: number;
  declare height: number;

  constructor(id: string, nodeType: string, label: string, params: Record<string, unknown> = {}) {
    super(label);
    this.id = id;          // Override Rete's auto-UUID with the document ID
    this.nodeType = nodeType;
    this.params = params;
    this.width = 180;
    this.height = 100;
  }
}

// ============ Rete Scheme Types ============

// Use ClassicPreset.Node for Connection generic to satisfy Rete's type constraints
type Conn = ClassicPreset.Connection<ClassicPreset.Node, ClassicPreset.Node>;
export type FrontendSchemes = {
  Node: FigReteNode;
  Connection: Conn;
};

export type AreaExtra = MinimapExtra;

// ============ ReteAdapter ============

export class ReteAdapter {
  editor: NodeEditor<FrontendSchemes>;
  area: AreaPlugin<FrontendSchemes, AreaExtra> | null = null;
  nodeMetadata: NodeSchemaMap;

  /** True while loadDocument is running — pipe callbacks should ignore events. */
  loading = false;

  constructor(editor: NodeEditor<FrontendSchemes>, nodeMetadata: NodeSchemaMap) {
    this.editor = editor;
    this.nodeMetadata = nodeMetadata;
  }

  setArea(area: AreaPlugin<FrontendSchemes, AreaExtra>): void {
    this.area = area;
  }

  /**
   * Load a full Graph into the Rete editor.
   */
  async loadDocument(doc: Graph): Promise<void> {
    this.loading = true;
    try {
      // Clear existing state
      for (const conn of this.editor.getConnections()) {
        await this.editor.removeConnection(conn.id);
      }
      for (const node of this.editor.getNodes()) {
        await this.editor.removeNode(node.id);
      }

      // Create nodes
      for (const [docId, graphNode] of Object.entries(doc.nodes)) {
        const meta = this.nodeMetadata[graphNode.type];
        const node = new FigReteNode(
          docId,
          graphNode.type,
          graphNode.title ?? graphNode.type,
          graphNode.params ?? {},
        );

        // Add inputs from metadata
        if (meta) {
          for (const p of meta.inputs) {
            const socket = getOrCreateSocket(p);
            node.addInput(p.name, new ClassicPreset.Input(socket, p.name, p.multi ?? false));
          }
          for (const p of meta.outputs) {
            const socket = getOrCreateSocket(p);
            node.addOutput(p.name, new ClassicPreset.Output(socket, p.name));
          }
        }

        await this.editor.addNode(node);

        // Position via area plugin
        if (this.area && graphNode.position) {
          await this.area.translate(node.id, { x: graphNode.position[0], y: graphNode.position[1] });
        }
      }

      // Create connections
      for (const edge of doc.edges) {
        try {
          const from = parseEdgeEndpoint(edge.from);
          const to = parseEdgeEndpoint(edge.to);

          const sourceNode = this.editor.getNode(from.nodeId);
          const targetNode = this.editor.getNode(to.nodeId);
          if (!sourceNode || !targetNode) continue;

          const conn = new ClassicPreset.Connection(sourceNode, from.portName, targetNode, to.portName) as Conn;
          await this.editor.addConnection(conn);
        } catch (e) {
          console.warn(`Failed to create connection for edge ${edge.from} -> ${edge.to}:`, e);
        }
      }
    } finally {
      this.loading = false;
    }
  }

  /**
   * Add a single node to the Rete editor.
   */
  async addNode(docId: string, graphNode: { type: string; params?: Record<string, unknown>; title?: string; position?: [number, number] }): Promise<void> {
    const meta = this.nodeMetadata[graphNode.type];
    const node = new FigReteNode(
      docId,
      graphNode.type,
      graphNode.title ?? graphNode.type,
      graphNode.params ?? {},
    );

    if (meta) {
      for (const p of meta.inputs) {
        const socket = getOrCreateSocket(p);
        node.addInput(p.name, new ClassicPreset.Input(socket, p.name, p.multi ?? false));
      }
      for (const p of meta.outputs) {
        const socket = getOrCreateSocket(p);
        node.addOutput(p.name, new ClassicPreset.Output(socket, p.name));
      }
    }

    await this.editor.addNode(node);

    if (this.area && graphNode.position) {
      await this.area.translate(node.id, { x: graphNode.position[0], y: graphNode.position[1] });
    }
  }

  /**
   * Remove a node from the Rete editor.
   */
  async removeNode(nodeId: string): Promise<void> {
    const node = this.editor.getNode(nodeId);
    if (!node) return;

    // Remove all connections to/from this node first
    const connections = this.editor.getConnections();
    for (const conn of connections) {
      if (conn.source === nodeId || conn.target === nodeId) {
        await this.editor.removeConnection(conn.id);
      }
    }

    await this.editor.removeNode(nodeId);
  }

  /**
   * Add an edge to the Rete editor.
   */
  async addEdge(edge: GraphEdge): Promise<void> {
    const from = parseEdgeEndpoint(edge.from);
    const to = parseEdgeEndpoint(edge.to);

    const sourceNode = this.editor.getNode(from.nodeId);
    const targetNode = this.editor.getNode(to.nodeId);
    if (!sourceNode || !targetNode) return;

    const conn = new ClassicPreset.Connection(sourceNode, from.portName, targetNode, to.portName) as Conn;
    await this.editor.addConnection(conn);
  }

  /**
   * Remove an edge from the Rete editor.
   */
  async removeEdge(fromEndpoint: string, toEndpoint: string): Promise<void> {
    const from = parseEdgeEndpoint(fromEndpoint);
    const to = parseEdgeEndpoint(toEndpoint);

    const connections = this.editor.getConnections();
    for (const conn of connections) {
      if (
        conn.source === from.nodeId &&
        conn.sourceOutput === from.portName &&
        conn.target === to.nodeId &&
        conn.targetInput === to.portName
      ) {
        await this.editor.removeConnection(conn.id);
        break;
      }
    }
  }

  /**
   * Update a node's position in the area.
   */
  async updateNodePosition(nodeId: string, position: [number, number]): Promise<void> {
    if (!this.area) return;
    await this.area.translate(nodeId, { x: position[0], y: position[1] });
  }

  /**
   * Serialize the current Rete state into a Graph.
   */
  serializeGraph(docName: string, docId: string): Graph {
    const nodes: Record<string, GraphNode> = {};
    for (const node of this.editor.getNodes()) {
      const view = this.area?.nodeViews.get(node.id);
      nodes[node.id] = {
        type: node.nodeType,
        params: { ...node.params },
        title: node.label !== node.nodeType ? node.label : undefined,
        position: view ? [view.position.x, view.position.y] : undefined,
      };
    }

    const edges: GraphEdge[] = this.editor.getConnections().map((conn) => ({
      from: `${conn.source}.${conn.sourceOutput}`,
      to: `${conn.target}.${conn.targetInput}`,
    }));

    return { id: docId, name: docName, version: 2, nodes, edges };
  }
}
