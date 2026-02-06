// src/engine/graph-executor.ts
// DAG-based graph execution engine using GraphDocument (string IDs, named ports)

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

// ============ Types ============

type NodeIndex = number;

// GraphDocument execution uses string IDs
type StringExecutionResults = Record<string, Record<string, unknown>>;

interface NamedPortLink {
  fromNodeId: string;
  outputPort: string;
  inputPort: string;
}

enum GraphExecutionState {
  IDLE = 'idle',
  RUNNING = 'running',
  STOPPING = 'stopping',
  STOPPED = 'stopped',
}

// ============ DiGraph Implementation ============

/**
 * Simple directed graph with topological generation support.
 */
class DiGraph {
  private adjacency: Map<NodeIndex, Set<NodeIndex>> = new Map();
  private reverseAdj: Map<NodeIndex, Set<NodeIndex>> = new Map();
  private nodeCount = 0;
  private nextIndex = 0;

  addNode(): NodeIndex {
    const idx = this.nextIndex++;
    this.adjacency.set(idx, new Set());
    this.reverseAdj.set(idx, new Set());
    this.nodeCount++;
    return idx;
  }

  addEdge(from: NodeIndex, to: NodeIndex): void {
    this.adjacency.get(from)?.add(to);
    this.reverseAdj.get(to)?.add(from);
  }

  inDegree(idx: NodeIndex): number {
    return this.reverseAdj.get(idx)?.size ?? 0;
  }

  outDegree(idx: NodeIndex): number {
    return this.adjacency.get(idx)?.size ?? 0;
  }

  /**
   * Compute topological generations (levels) for parallel execution.
   * Nodes in the same level have no dependencies on each other.
   * Throws if the graph contains cycles.
   */
  topologicalGenerations(): NodeIndex[][] {
    const inDegree = new Map<NodeIndex, number>();
    for (const idx of this.adjacency.keys()) {
      inDegree.set(idx, this.inDegree(idx));
    }

    const levels: NodeIndex[][] = [];
    let currentLevel: NodeIndex[] = [];
    let visited = 0;

    for (const [idx, deg] of inDegree) {
      if (deg === 0) currentLevel.push(idx);
    }

    while (currentLevel.length > 0) {
      levels.push(currentLevel);
      visited += currentLevel.length;
      const nextLevel: NodeIndex[] = [];

      for (const node of currentLevel) {
        for (const neighbor of this.adjacency.get(node) ?? []) {
          const newDeg = inDegree.get(neighbor)! - 1;
          inDegree.set(neighbor, newDeg);
          if (newDeg === 0) nextLevel.push(neighbor);
        }
      }

      currentLevel = nextLevel;
    }

    if (visited !== this.nodeCount) {
      throw new Error('Graph contains cycles');
    }

    return levels;
  }
}

// ============ GraphDocument Executor ============

/**
 * Executor that works directly with GraphDocument (string IDs, named ports).
 */
export class GraphDocumentExecutor {
  private doc: GraphDocument;
  private nodeRegistry: NodeRegistry;
  private credentials?: CredentialProvider;
  private nodes: Map<string, Base> = new Map();
  private dag: DiGraph = new DiGraph();
  private strIdToIdx: Map<string, NodeIndex> = new Map();
  private idxToStrId: Map<NodeIndex, string> = new Map();
  private incomingLinks: Map<string, NamedPortLink[]> = new Map();
  private _state: GraphExecutionState = GraphExecutionState.IDLE;
  private _resultCallback: ResultCallback | null = null;
  // Maps string node ID -> numeric ID assigned for Base constructor
  private strIdToNumId: Map<string, number> = new Map();

  constructor(doc: GraphDocument, nodeRegistry: NodeRegistry, credentials?: CredentialProvider) {
    this.doc = doc;
    this.nodeRegistry = nodeRegistry;
    this.credentials = credentials;
    this.buildFromDocument();
  }

  private buildGraphContext(nodeId: string): Record<string, unknown> {
    const ctx: Record<string, unknown> = {
      graph_id: this.doc.id,
      document: this.doc,
      current_node_id: nodeId,
    };

    if (this.credentials) {
      ctx[CREDENTIAL_PROVIDER_KEY] = this.credentials;
    }

    return ctx;
  }

  private buildFromDocument(): void {
    let numericId = 1;

    // Build nodes
    for (const [nodeId, nodeData] of Object.entries(this.doc.nodes)) {
      const nodeType = nodeData.type;

      if (!(nodeType in this.nodeRegistry)) {
        throw new Error(`Unknown node type: ${nodeType}`);
      }

      const NodeClass = this.nodeRegistry[nodeType] as new (
        id: number,
        params: Record<string, unknown>,
        graphContext?: Record<string, unknown>,
      ) => Base;

      const nid = numericId++;
      this.strIdToNumId.set(nodeId, nid);
      this.nodes.set(nodeId, new NodeClass(nid, nodeData.params ?? {}, this.buildGraphContext(nodeId)));

      const idx = this.dag.addNode();
      this.strIdToIdx.set(nodeId, idx);
      this.idxToStrId.set(idx, nodeId);
    }

    // Build edges from named ports
    for (const edge of this.doc.edges) {
      const from = parseEdgeEndpoint(edge.from);
      const to = parseEdgeEndpoint(edge.to);

      if (!this.strIdToIdx.has(from.nodeId)) {
        console.warn(`Edge references non-existent source node "${from.nodeId}", skipping`);
        continue;
      }
      if (!this.strIdToIdx.has(to.nodeId)) {
        console.warn(`Edge references non-existent target node "${to.nodeId}", skipping`);
        continue;
      }

      this.dag.addEdge(this.strIdToIdx.get(from.nodeId)!, this.strIdToIdx.get(to.nodeId)!);

      if (!this.incomingLinks.has(to.nodeId)) {
        this.incomingLinks.set(to.nodeId, []);
      }
      this.incomingLinks.get(to.nodeId)!.push({
        fromNodeId: from.nodeId,
        outputPort: from.portName,
        inputPort: to.portName,
      });
    }

    // Validate DAG (throws on cycles)
    this.dag.topologicalGenerations();
  }

  // ============ Execution ============

  async execute(): Promise<StringExecutionResults> {
    const results: StringExecutionResults = {};
    const levels = this.dag.topologicalGenerations();
    this._state = GraphExecutionState.RUNNING;

    try {
      for (const level of levels) {
        if (this.shouldStop()) break;

        const tasks: Array<Promise<[string, Record<string, unknown>]>> = [];

        for (const nodeIdx of level) {
          const nodeId = this.idxToStrId.get(nodeIdx)!;

          // Skip isolated nodes (no connections)
          if (this.dag.inDegree(nodeIdx) === 0 && this.dag.outDegree(nodeIdx) === 0) {
            continue;
          }

          const predError = this.getPredecessorError(nodeId, results);
          if (predError) {
            results[nodeId] = { error: predError };
            continue;
          }

          const node = this.nodes.get(nodeId)!;
          const inputs = this.getNodeInputs(nodeId, results);

          // Merge params as defaults for unfilled inputs
          const mergedInputs: Record<string, unknown> = {};
          for (const [k, v] of Object.entries(node.params)) {
            if (k in node.inputs && !(k in inputs) && v !== null) {
              mergedInputs[k] = v;
            }
          }
          Object.assign(mergedInputs, inputs);

          tasks.push(this.executeNode(nodeId, node, mergedInputs));
        }

        if (tasks.length > 0 && !this.shouldStop()) {
          const settledResults = await Promise.allSettled(tasks);

          for (const settled of settledResults) {
            if (this.shouldStop()) break;

            if (settled.status === 'fulfilled') {
              const [nodeId, output] = settled.value;
              const node = this.nodes.get(nodeId);

              if (node?.category === NodeCategory.IO && this._resultCallback) {
                const numId = this.strIdToNumId.get(nodeId)!;
                this._resultCallback(numId, output);
              }

              results[nodeId] = output;
            } else {
              console.error(`Task failed: ${settled.reason}`);
            }
          }
        }
      }
    } catch (e) {
      console.error(`Execution failed: ${e}`);
    }

    return results;
  }

  private async executeNode(
    nodeId: string,
    node: Base,
    mergedInputs: Record<string, unknown>,
  ): Promise<[string, Record<string, unknown>]> {
    try {
      const outputs = await node.execute(mergedInputs);
      return [nodeId, outputs];
    } catch (e) {
      if (e instanceof NodeExecutionError) {
        console.error(`Node ${nodeId} failed: ${e.message}`);
        return [nodeId, { error: e.message }];
      }
      const error = e instanceof Error ? e : new Error(String(e));
      console.error(`Unexpected error in node ${nodeId}: ${error.message}`);
      return [nodeId, { error: `Unexpected error: ${error.message}` }];
    }
  }

  private getPredecessorError(nodeId: string, results: StringExecutionResults): string | null {
    for (const link of this.incomingLinks.get(nodeId) ?? []) {
      const predResult = results[link.fromNodeId];
      if (predResult && typeof predResult.error === 'string') {
        return `Predecessor node ${link.fromNodeId} failed: ${predResult.error}`;
      }
    }
    return null;
  }

  /**
   * Resolve inputs by named ports -- no slot index translation needed.
   */
  private getNodeInputs(nodeId: string, results: StringExecutionResults): Record<string, unknown> {
    const inputs: Record<string, unknown> = {};

    for (const link of this.incomingLinks.get(nodeId) ?? []) {
      const predResult = results[link.fromNodeId];
      if (!predResult || !(link.outputPort in predResult)) continue;

      inputs[link.inputPort] = predResult[link.outputPort];
    }

    return inputs;
  }

  // ============ Cancellation ============

  forceStop(_reason = 'user'): void {
    if (
      this._state === GraphExecutionState.STOPPING ||
      this._state === GraphExecutionState.STOPPED
    ) {
      return;
    }

    this._state = GraphExecutionState.STOPPING;

    for (const node of this.nodes.values()) {
      node.forceStop();
    }

    this._state = GraphExecutionState.STOPPED;
  }

  private shouldStop(): boolean {
    return this._state !== GraphExecutionState.RUNNING;
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
