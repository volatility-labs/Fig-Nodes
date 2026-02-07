// rete/rete-adapter.ts
// Bidirectional sync between GraphDocument (Zustand store) and Rete editor

import { NodeEditor, ClassicPreset } from 'rete';
import { AreaPlugin } from 'rete-area-plugin';
import type { GraphDocument, GraphEdge } from '@fig-node/core';
import { parseEdgeEndpoint } from '@fig-node/core';
import type { NodeMetadataMap } from '../types/node-metadata';

// ============ Lightweight wrapper for frontend-only nodes ============

/**
 * FigReteNode is a lightweight ClassicPreset.Node used in the frontend editor.
 * It does NOT extend Base (which requires full executeImpl). Instead, it's a
 * simple node with sockets for visual editing only.
 */
export class FigReteNode extends ClassicPreset.Node {
  figNodeId: string;
  nodeType: string;
  width = 200;
  height = 150;

  constructor(figNodeId: string, nodeType: string, label: string) {
    super(label);
    this.figNodeId = figNodeId;
    this.nodeType = nodeType;
  }
}

// ============ Rete Scheme Types ============

// Use ClassicPreset.Node for Connection generic to satisfy Rete's type constraints
type Conn = ClassicPreset.Connection<ClassicPreset.Node, ClassicPreset.Node>;
export type FrontendSchemes = {
  Node: FigReteNode;
  Connection: Conn;
};

export type AreaExtra = never;

// ============ Socket cache (shared across adapter) ============

const socketCache = new Map<string, ClassicPreset.Socket>();
const anySocket = new ClassicPreset.Socket('any');

function getOrCreateSocket(typeStr: string): ClassicPreset.Socket {
  const primary = typeStr.split(',')[0]!.trim().toLowerCase();
  if (primary === 'any') return anySocket;
  if (socketCache.has(primary)) return socketCache.get(primary)!;
  const socket = new ClassicPreset.Socket(primary);
  socketCache.set(primary, socket);
  return socket;
}

// ============ ReteAdapter ============

export class ReteAdapter {
  editor: NodeEditor<FrontendSchemes>;
  area: AreaPlugin<FrontendSchemes, AreaExtra> | null = null;
  nodeMetadata: NodeMetadataMap;

  // Bidirectional ID mapping
  docToRete = new Map<string, string>();  // graphDocId → rete node id
  reteToDoc = new Map<string, string>();  // rete node id → graphDocId

  // Prevent feedback loops during store → Rete sync
  syncing = false;

  constructor(editor: NodeEditor<FrontendSchemes>, nodeMetadata: NodeMetadataMap) {
    this.editor = editor;
    this.nodeMetadata = nodeMetadata;
  }

  setArea(area: AreaPlugin<FrontendSchemes, AreaExtra>): void {
    this.area = area;
  }

  /**
   * Load a full GraphDocument into the Rete editor.
   */
  async loadDocument(doc: GraphDocument): Promise<void> {
    this.syncing = true;

    try {
      // Clear existing state
      for (const conn of this.editor.getConnections()) {
        await this.editor.removeConnection(conn.id);
      }
      for (const node of this.editor.getNodes()) {
        await this.editor.removeNode(node.id);
      }
      this.docToRete.clear();
      this.reteToDoc.clear();

      // Create nodes
      for (const [docId, graphNode] of Object.entries(doc.nodes)) {
        const meta = this.nodeMetadata[graphNode.type];
        const node = new FigReteNode(docId, graphNode.type, graphNode.title ?? graphNode.type);

        // Add inputs from metadata
        if (meta) {
          for (const [name, typeStr] of Object.entries(meta.inputs)) {
            const socket = getOrCreateSocket(String(typeStr));
            node.addInput(name, new ClassicPreset.Input(socket, name));
          }
          for (const [name, typeStr] of Object.entries(meta.outputs)) {
            const socket = getOrCreateSocket(String(typeStr));
            node.addOutput(name, new ClassicPreset.Output(socket, name));
          }
        }

        await this.editor.addNode(node);
        this.docToRete.set(docId, node.id);
        this.reteToDoc.set(node.id, docId);

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

          const sourceReteId = this.docToRete.get(from.nodeId);
          const targetReteId = this.docToRete.get(to.nodeId);
          if (!sourceReteId || !targetReteId) continue;

          const sourceNode = this.editor.getNode(sourceReteId);
          const targetNode = this.editor.getNode(targetReteId);
          if (!sourceNode || !targetNode) continue;

          const conn = new ClassicPreset.Connection(sourceNode, from.portName, targetNode, to.portName) as Conn;
          await this.editor.addConnection(conn);
        } catch (e) {
          console.warn(`Failed to create connection for edge ${edge.from} -> ${edge.to}:`, e);
        }
      }
    } finally {
      this.syncing = false;
    }
  }

  /**
   * Add a single node to the Rete editor.
   */
  async addNode(docId: string, graphNode: { type: string; params?: Record<string, unknown>; title?: string; position?: [number, number] }): Promise<void> {
    this.syncing = true;
    try {
      const meta = this.nodeMetadata[graphNode.type];
      const node = new FigReteNode(docId, graphNode.type, graphNode.title ?? graphNode.type);

      if (meta) {
        for (const [name, typeStr] of Object.entries(meta.inputs)) {
          const socket = getOrCreateSocket(String(typeStr));
          node.addInput(name, new ClassicPreset.Input(socket, name));
        }
        for (const [name, typeStr] of Object.entries(meta.outputs)) {
          const socket = getOrCreateSocket(String(typeStr));
          node.addOutput(name, new ClassicPreset.Output(socket, name));
        }
      }

      await this.editor.addNode(node);
      this.docToRete.set(docId, node.id);
      this.reteToDoc.set(node.id, docId);

      if (this.area && graphNode.position) {
        await this.area.translate(node.id, { x: graphNode.position[0], y: graphNode.position[1] });
      }
    } finally {
      this.syncing = false;
    }
  }

  /**
   * Remove a node from the Rete editor.
   */
  async removeNode(docId: string): Promise<void> {
    this.syncing = true;
    try {
      const reteId = this.docToRete.get(docId);
      if (!reteId) return;

      // Remove all connections to/from this node first
      const connections = this.editor.getConnections();
      for (const conn of connections) {
        if (conn.source === reteId || conn.target === reteId) {
          await this.editor.removeConnection(conn.id);
        }
      }

      await this.editor.removeNode(reteId);
      this.docToRete.delete(docId);
      this.reteToDoc.delete(reteId);
    } finally {
      this.syncing = false;
    }
  }

  /**
   * Add an edge to the Rete editor.
   */
  async addEdge(edge: GraphEdge): Promise<void> {
    this.syncing = true;
    try {
      const from = parseEdgeEndpoint(edge.from);
      const to = parseEdgeEndpoint(edge.to);

      const sourceReteId = this.docToRete.get(from.nodeId);
      const targetReteId = this.docToRete.get(to.nodeId);
      if (!sourceReteId || !targetReteId) return;

      const sourceNode = this.editor.getNode(sourceReteId);
      const targetNode = this.editor.getNode(targetReteId);
      if (!sourceNode || !targetNode) return;

      const conn = new ClassicPreset.Connection(sourceNode, from.portName, targetNode, to.portName) as Conn;
      await this.editor.addConnection(conn);
    } finally {
      this.syncing = false;
    }
  }

  /**
   * Remove an edge from the Rete editor.
   */
  async removeEdge(fromEndpoint: string, toEndpoint: string): Promise<void> {
    this.syncing = true;
    try {
      const from = parseEdgeEndpoint(fromEndpoint);
      const to = parseEdgeEndpoint(toEndpoint);

      const sourceReteId = this.docToRete.get(from.nodeId);
      const targetReteId = this.docToRete.get(to.nodeId);
      if (!sourceReteId || !targetReteId) return;

      const connections = this.editor.getConnections();
      for (const conn of connections) {
        if (
          conn.source === sourceReteId &&
          conn.sourceOutput === from.portName &&
          conn.target === targetReteId &&
          conn.targetInput === to.portName
        ) {
          await this.editor.removeConnection(conn.id);
          break;
        }
      }
    } finally {
      this.syncing = false;
    }
  }

  /**
   * Update a node's position in the area.
   */
  async updateNodePosition(docId: string, position: [number, number]): Promise<void> {
    if (!this.area) return;
    this.syncing = true;
    try {
      const reteId = this.docToRete.get(docId);
      if (!reteId) return;
      await this.area.translate(reteId, { x: position[0], y: position[1] });
    } finally {
      this.syncing = false;
    }
  }

  /**
   * Get the graph document ID for a rete node ID.
   */
  getDocId(reteNodeId: string): string | undefined {
    return this.reteToDoc.get(reteNodeId);
  }

  /**
   * Get the rete node ID for a graph document ID.
   */
  getReteId(docId: string): string | undefined {
    return this.docToRete.get(docId);
  }
}
