// src/engine/graph-executor.ts
// DAG-based graph execution engine

import {
  NodeCategory,
  NodeExecutionError,
  NodeRegistry,
  ProgressCallback,
  ResultCallback,
  SerialisableGraph,
  SerialisedLink,
  type CredentialProvider,
  CREDENTIAL_PROVIDER_KEY,
} from '../types';
import { Base } from '../nodes/base/base-node';

// ============ Types ============

type NodeId = number;
type NodeIndex = number;
type ExecutionResults = Record<NodeId, Record<string, unknown>>;

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

// ============ Graph Executor ============

export class GraphExecutor {
  private graph: SerialisableGraph;
  private nodeRegistry: NodeRegistry;
  private credentials?: CredentialProvider;
  private nodes: Map<NodeId, Base> = new Map();
  private inputNames: Map<NodeId, string[]> = new Map();
  private outputNames: Map<NodeId, string[]> = new Map();
  private dag: DiGraph = new DiGraph();
  private idToIdx: Map<NodeId, NodeIndex> = new Map();
  private idxToId: Map<NodeIndex, NodeId> = new Map();
  private incomingLinks: Map<NodeId, SerialisedLink[]> = new Map();
  private _state: GraphExecutionState = GraphExecutionState.IDLE;
  private _resultCallback: ResultCallback | null = null;

  constructor(graph: SerialisableGraph, nodeRegistry: NodeRegistry, credentials?: CredentialProvider) {
    this.graph = graph;
    this.nodeRegistry = nodeRegistry;
    this.credentials = credentials;
    this.buildGraph();
  }

  private buildGraphContext(nodeId: NodeId): Record<string, unknown> {
    const ctx: Record<string, unknown> = {
      graph_id: this.graph.id,
      nodes: this.graph.nodes ?? [],
      links: this.graph.links ?? [],
      current_node_id: nodeId,
    };

    if (this.credentials) {
      ctx[CREDENTIAL_PROVIDER_KEY] = this.credentials;
    }

    return ctx;
  }

  private buildGraph(): void {
    const nodes = this.graph.nodes ?? [];

    for (const nodeData of nodes) {
      const nodeId = nodeData.id;
      const nodeType = nodeData.type;

      if (!(nodeType in this.nodeRegistry)) {
        throw new Error(`Unknown node type: ${nodeType}`);
      }

      const NodeClass = this.nodeRegistry[nodeType] as new (
        id: number,
        params: Record<string, unknown>,
        graphContext?: Record<string, unknown>
      ) => Base;

      this.nodes.set(
        nodeId,
        new NodeClass(nodeId, nodeData.properties ?? {}, this.buildGraphContext(nodeId))
      );

      const inputList = (nodeData.inputs ?? []).map((inp) => inp.name ?? '');
      if (inputList.length > 0) {
        this.inputNames.set(nodeId, inputList);
      }

      const outputList = (nodeData.outputs ?? []).map((out) => out.name ?? '');
      if (outputList.length > 0) {
        this.outputNames.set(nodeId, outputList);
      }

      const idx = this.dag.addNode();
      this.idToIdx.set(nodeId, idx);
      this.idxToId.set(idx, nodeId);
    }

    const links = this.graph.links ?? [];
    for (const link of links) {
      const fromId = link.origin_id;
      const toId = link.target_id;

      if (!this.idToIdx.has(fromId)) {
        console.warn(
          `Link ${link.id ?? 'unknown'} references non-existent origin node ${fromId}, skipping`
        );
        continue;
      }
      if (!this.idToIdx.has(toId)) {
        console.warn(
          `Link ${link.id ?? 'unknown'} references non-existent target node ${toId}, skipping`
        );
        continue;
      }

      this.dag.addEdge(this.idToIdx.get(fromId)!, this.idToIdx.get(toId)!);

      if (!this.incomingLinks.has(toId)) {
        this.incomingLinks.set(toId, []);
      }
      this.incomingLinks.get(toId)!.push(link);
    }

    // Validates the graph is a DAG (throws on cycles)
    this.dag.topologicalGenerations();
  }

  // ============ Execution ============

  async execute(): Promise<ExecutionResults> {
    const results: ExecutionResults = {};
    const levels = this.dag.topologicalGenerations();
    this._state = GraphExecutionState.RUNNING;

    try {
      for (const level of levels) {
        if (this.shouldStop()) break;

        const tasks: Array<Promise<[NodeId, Record<string, unknown>]>> = [];

        for (const nodeIdx of level) {
          const nodeId = this.idxToId.get(nodeIdx)!;

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
                this._resultCallback(nodeId, output);
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
    nodeId: NodeId,
    node: Base,
    mergedInputs: Record<string, unknown>
  ): Promise<[NodeId, Record<string, unknown>]> {
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

  private getPredecessorError(nodeId: NodeId, results: ExecutionResults): string | null {
    for (const link of this.incomingLinks.get(nodeId) ?? []) {
      const predResult = results[link.origin_id];
      if (predResult && typeof predResult.error === 'string') {
        return `Predecessor node ${link.origin_id} failed: ${predResult.error}`;
      }
    }
    return null;
  }

  private getNodeInputs(nodeId: NodeId, results: ExecutionResults): Record<string, unknown> {
    const inputs: Record<string, unknown> = {};

    for (const link of this.incomingLinks.get(nodeId) ?? []) {
      const predNode = this.nodes.get(link.origin_id);
      if (!predNode) continue;

      const predOutputs = this.outputNames.get(link.origin_id) ?? Object.keys(predNode.outputs);
      if (link.origin_slot >= predOutputs.length) continue;

      const outputKey = predOutputs[link.origin_slot];
      if (!outputKey) continue;

      const predResult = results[link.origin_id];
      if (!predResult || !(outputKey in predResult)) continue;

      const nodeInputs =
        this.inputNames.get(nodeId) ?? Object.keys(this.nodes.get(nodeId)!.inputs);
      if (link.target_slot < nodeInputs.length) {
        const inputKey = nodeInputs[link.target_slot];
        if (inputKey) {
          inputs[inputKey] = predResult[outputKey];
        }
      }
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
