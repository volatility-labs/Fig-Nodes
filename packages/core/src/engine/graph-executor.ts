// src/engine/graph-executor.ts
// Rete-based graph execution engine using NodeEditor + DataflowEngine

import { NodeEditor, ClassicPreset } from 'rete';
import { DataflowEngine } from 'rete-engine';

import {
  NodeCategory,
  NodeExecutionError,
  type NodeRegistry,
  type ProgressCallback,
  type ResultCallback,
  type CredentialProvider,
  CREDENTIAL_PROVIDER_KEY,
} from '../types';
import { type GraphDocument, parseEdgeEndpoint } from '../types/graph-document';
import { Base } from '../nodes/base/base-node';

// ============ Rete Scheme Types ============

// Use ClassicPreset.Node for the connection generic to satisfy DataflowEngineScheme,
// while using Base as the Node type in the scheme.
type Connection = ClassicPreset.Connection<ClassicPreset.Node, ClassicPreset.Node>;
type Schemes = {
  Node: Base;
  Connection: Connection;
};

// ============ Types ============

type StringExecutionResults = Record<string, Record<string, unknown>>;

// ============ GraphDocument Executor ============

/**
 * Executor that uses Rete's NodeEditor (headless) + DataflowEngine.
 */
export class GraphDocumentExecutor {
  private editor: NodeEditor<Schemes>;
  private engine: DataflowEngine<Schemes>;
  private nodes: Map<string, Base> = new Map(); // docId → node instance
  private _resultCallback: ResultCallback | null = null;
  private _stopped = false;

  constructor(doc: GraphDocument, nodeRegistry: NodeRegistry, credentials?: CredentialProvider) {
    this.editor = new NodeEditor<Schemes>();
    this.engine = new DataflowEngine<Schemes>();
    this.editor.use(this.engine);

    this.buildFromDocument(doc, nodeRegistry, credentials);
  }

  private buildFromDocument(
    doc: GraphDocument,
    nodeRegistry: NodeRegistry,
    credentials?: CredentialProvider,
  ): void {
    const graphContext = (nodeId: string): Record<string, unknown> => {
      const ctx: Record<string, unknown> = {
        graph_id: doc.id,
        document: doc,
        current_node_id: nodeId,
      };
      if (credentials) {
        ctx[CREDENTIAL_PROVIDER_KEY] = credentials;
      }
      return ctx;
    };

    // Create nodes
    for (const [nodeId, nodeData] of Object.entries(doc.nodes)) {
      const nodeType = nodeData.type;

      if (!(nodeType in nodeRegistry)) {
        throw new Error(`Unknown node type: ${nodeType}`);
      }

      const NodeClass = nodeRegistry[nodeType] as new (
        figNodeId: string,
        params: Record<string, unknown>,
        graphContext?: Record<string, unknown>,
      ) => Base;

      const node = new NodeClass(nodeId, nodeData.params ?? {}, graphContext(nodeId));
      this.editor.addNode(node);
      this.nodes.set(nodeId, node);
    }

    // Create connections
    for (const edge of doc.edges) {
      const from = parseEdgeEndpoint(edge.from);
      const to = parseEdgeEndpoint(edge.to);

      const sourceNode = this.nodes.get(from.nodeId);
      const targetNode = this.nodes.get(to.nodeId);

      if (!sourceNode) {
        console.warn(`Edge references non-existent source node "${from.nodeId}", skipping`);
        continue;
      }
      if (!targetNode) {
        console.warn(`Edge references non-existent target node "${to.nodeId}", skipping`);
        continue;
      }

      const conn = new ClassicPreset.Connection(sourceNode, from.portName, targetNode, to.portName) as Connection;
      this.editor.addConnection(conn);
    }
  }

  // ============ Execution ============

  async execute(): Promise<StringExecutionResults> {
    const results: StringExecutionResults = {};
    this._stopped = false;

    // Find sink nodes (no outgoing connections)
    const connections = this.editor.getConnections();
    const nodesWithOutgoing = new Set<string>();
    for (const conn of connections) {
      nodesWithOutgoing.add(conn.source);
    }

    const sinkNodes: Base[] = [];
    for (const [, node] of this.nodes) {
      if (!nodesWithOutgoing.has(node.id)) {
        sinkNodes.push(node);
      }
    }

    // If no sinks found (disconnected graph), fetch all nodes
    const targets = sinkNodes.length > 0 ? sinkNodes : [...this.nodes.values()];

    // Fetch each sink — the engine recursively resolves upstream dependencies
    for (const node of targets) {
      if (this._stopped) break;

      const docId = node.figNodeId;
      try {
        const output = await this.engine.fetch(node.id);
        results[docId] = output;

        // Fire result callback for IO-category nodes
        if (node.category === NodeCategory.IO && this._resultCallback) {
          this._resultCallback(docId, output);
        }
      } catch (e) {
        if (e instanceof NodeExecutionError) {
          console.error(`Node ${docId} failed: ${e.message}`);
          results[docId] = { error: e.message };
        } else {
          const error = e instanceof Error ? e : new Error(String(e));
          console.error(`Unexpected error in node ${docId}: ${error.message}`);
          results[docId] = { error: `Unexpected error: ${error.message}` };
        }
      }
    }

    // Collect results from non-sink nodes that were executed as dependencies
    for (const [docId, node] of this.nodes) {
      if (!(docId in results)) {
        try {
          const cached = await this.engine.fetch(node.id);
          results[docId] = cached;

          if (node.category === NodeCategory.IO && this._resultCallback) {
            this._resultCallback(docId, cached);
          }
        } catch {
          // Node may not have been reached — skip
        }
      }
    }

    return results;
  }

  // ============ Cancellation ============

  forceStop(_reason = 'user'): void {
    this._stopped = true;

    for (const node of this.nodes.values()) {
      node.forceStop();
    }
  }

  // ============ Callbacks ============

  setProgressCallback(callback: ProgressCallback): void {
    for (const node of this.nodes.values()) {
      node.setProgressCallback(callback);
    }
  }

  setResultCallback(callback: ResultCallback): void {
    this._resultCallback = callback;
  }
}
