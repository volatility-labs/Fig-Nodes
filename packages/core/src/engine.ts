// src/engine.ts
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
} from './types.js';
import { type Graph, parseEdgeEndpoint } from './graph.js';
import { Node, type NodeDefinition } from './node.js';
import { getSocketKey, areSocketKeysCompatible } from './sockets.js';

// ============ Rete Scheme Types ============

type Connection = ClassicPreset.Connection<ClassicPreset.Node, ClassicPreset.Node>;
type Schemes = {
  Node: Node;
  Connection: Connection;
};

// ============ Types ============

type StringExecutionResults = Record<string, Record<string, unknown>>;

// ============ Graph Executor ============

/**
 * Executor that uses Rete's NodeEditor (headless) + DataflowEngine.
 */
export class GraphExecutor {
  private editor: NodeEditor<Schemes>;
  private engine: DataflowEngine<Schemes>;
  private nodes: Map<string, Node> = new Map();
  private _resultCallback: ResultCallback | null = null;
  private _stopped = false;

  constructor(doc: Graph, nodeRegistry: NodeRegistry, credentials?: CredentialProvider) {
    this.editor = new NodeEditor<Schemes>();
    this.engine = new DataflowEngine<Schemes>();
    this.editor.use(this.engine);

    this.buildFromDocument(doc, nodeRegistry, credentials);
    this.validateCredentials(credentials);
  }

  private buildFromDocument(
    doc: Graph,
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
        nodeId: string,
        params: Record<string, unknown>,
        graphContext?: Record<string, unknown>,
      ) => Node;

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

      const sourceOutput = sourceNode.outputs[from.portName];
      const targetInput = targetNode.inputs[to.portName];
      if (!sourceOutput) {
        console.warn(`Edge references unknown source output "${from.portName}" on node "${from.nodeId}", skipping`);
        continue;
      }
      if (!targetInput) {
        console.warn(`Edge references unknown target input "${to.portName}" on node "${to.nodeId}", skipping`);
        continue;
      }

      const sourceKey = getSocketKey((sourceOutput.socket?.name ?? 'any'));
      const targetKey = getSocketKey((targetInput.socket?.name ?? 'any'));
      if (!areSocketKeysCompatible(sourceKey, targetKey)) {
        console.warn(
          `Edge socket mismatch "${from.nodeId}.${from.portName}" (${sourceKey}) -> "${to.nodeId}.${to.portName}" (${targetKey}), skipping`,
        );
        continue;
      }

      const conn = new ClassicPreset.Connection(sourceNode, from.portName, targetNode, to.portName) as Connection;
      this.editor.addConnection(conn);
    }
  }

  // ============ Credential Validation ============

  /**
   * Validate that all required credentials are available before execution.
   * Throws if any node's requiredCredentials are missing from the provider.
   */
  private validateCredentials(credentials?: CredentialProvider): void {
    if (!credentials) return;

    const missing: string[] = [];
    for (const node of this.nodes.values()) {
      const def = (node.constructor as typeof Node).definition as NodeDefinition;
      const required = def.requiredCredentials;
      if (!required) continue;

      for (const key of required) {
        if (!credentials.has(key) && !missing.includes(key)) {
          missing.push(key);
        }
      }
    }

    if (missing.length > 0) {
      throw new NodeExecutionError(
        'credential-check',
        `Missing required credentials: ${missing.join(', ')}`,
      );
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

    const sinkNodes: Node[] = [];
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

      const docId = node.nodeId;
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

    this.engine.reset();
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
