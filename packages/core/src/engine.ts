// src/engine.ts
// Rete-based graph execution engine using NodeEditor + DataflowEngine + ControlFlowEngine

import { NodeEditor, ClassicPreset } from 'rete';
import { DataflowEngine, ControlFlowEngine } from 'rete-engine';

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
import { isExecPort } from './ports.js';

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
 * Executor that uses Rete's NodeEditor (headless) + DataflowEngine + ControlFlowEngine.
 * Pure-dataflow graphs (no exec connections) execute via the existing sink-node logic.
 * Hybrid graphs (exec connections present) use ControlFlowEngine for sequencing,
 * with DataflowEngine for data resolution.
 */
export class GraphExecutor {
  private editor: NodeEditor<Schemes>;
  private dataflowEngine: DataflowEngine<Schemes>;
  private controlFlowEngine: ControlFlowEngine<Schemes>;
  private nodes: Map<string, Node> = new Map();
  private _resultCallback: ResultCallback | null = null;
  private _stopped = false;
  private _hasExecConnections = false;

  constructor(doc: Graph, nodeRegistry: NodeRegistry, credentials?: CredentialProvider) {
    this.editor = new NodeEditor<Schemes>();

    // DataflowEngine: filter out exec ports so they don't participate in data routing
    this.dataflowEngine = new DataflowEngine<Schemes>((node) => {
      const def = (node.constructor as typeof Node).definition as NodeDefinition;
      const inputs = Object.entries(def.inputs ?? {})
        .filter(([, spec]) => !isExecPort(spec))
        .map(([name]) => name);
      const outputs = Object.entries(def.outputs ?? {})
        .filter(([, spec]) => !isExecPort(spec))
        .map(([name]) => name);
      return { inputs: () => inputs, outputs: () => outputs };
    });

    // ControlFlowEngine: only consider exec ports
    this.controlFlowEngine = new ControlFlowEngine<Schemes>((node) => {
      const def = (node.constructor as typeof Node).definition as NodeDefinition;
      const inputs = Object.entries(def.inputs ?? {})
        .filter(([, spec]) => isExecPort(spec))
        .map(([name]) => name);
      const outputs = Object.entries(def.outputs ?? {})
        .filter(([, spec]) => isExecPort(spec))
        .map(([name]) => name);
      return { inputs: () => inputs, outputs: () => outputs };
    });

    this.editor.use(this.dataflowEngine);
    this.editor.use(this.controlFlowEngine);

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
        __dataflowEngine__: this.dataflowEngine,
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

      // Track whether the graph has any exec connections
      if (sourceKey === 'exec') {
        this._hasExecConnections = true;
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

    if (this._hasExecConnections) {
      return this.executeHybrid(results);
    }

    return this.executeDataflow(results);
  }

  /**
   * Pure dataflow execution — existing sink-node logic, unchanged behavior.
   */
  private async executeDataflow(results: StringExecutionResults): Promise<StringExecutionResults> {
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
        const output = await this.dataflowEngine.fetch(node.id);
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
          const cached = await this.dataflowEngine.fetch(node.id);
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

  /**
   * Hybrid execution — find start nodes (exec outputs, no incoming exec),
   * kick off ControlFlowEngine, then collect DataflowEngine results.
   */
  private async executeHybrid(results: StringExecutionResults): Promise<StringExecutionResults> {
    const connections = this.editor.getConnections();

    // Nodes that receive incoming exec connections
    const nodesWithIncomingExec = new Set<string>();
    for (const conn of connections) {
      const sourceNode = this.nodes.get(conn.source);
      if (sourceNode) {
        const def = (sourceNode.constructor as typeof Node).definition as NodeDefinition;
        const outputSpec = def.outputs?.[conn.sourceOutput as string];
        if (outputSpec && isExecPort(outputSpec)) {
          nodesWithIncomingExec.add(conn.target);
        }
      }
    }

    // Start nodes: have exec outputs but no incoming exec connections
    const startNodes: Node[] = [];
    for (const node of this.nodes.values()) {
      const def = (node.constructor as typeof Node).definition as NodeDefinition;
      const hasExecOutput = Object.values(def.outputs ?? {}).some(isExecPort);
      if (hasExecOutput && !nodesWithIncomingExec.has(node.id)) {
        startNodes.push(node);
      }
    }

    // Execute control flow from each start node
    for (const node of startNodes) {
      if (this._stopped) break;
      this.controlFlowEngine.execute(node.id);
    }

    // Collect dataflow results from all nodes
    for (const [docId, node] of this.nodes) {
      if (this._stopped) break;
      try {
        const output = await this.dataflowEngine.fetch(node.id);
        results[docId] = output;

        if (node.category === NodeCategory.IO && this._resultCallback) {
          this._resultCallback(docId, output);
        }
      } catch {
        // Node may not have been reached — skip
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

    this.dataflowEngine.reset();
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
