// backend/core/graph-executor.ts
// Translated from: core/graph_executor.py

import {
  NodeCategory,
  NodeExecutionError,
  NodeRegistry,
  ProgressCallback,
  ResultCallback,
  SerialisableGraph,
  SerialisedLink,
} from './types';
// import { getVault } from './api-key-vault'; // TODO: Re-enable when API key injection is implemented
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
 * Simple directed graph implementation with topological generation support.
 * Replaces RustWorkX PyDiGraph for this use case.
 */
class DiGraph {
  private adjacency: Map<NodeIndex, Set<NodeIndex>> = new Map();
  private reverseAdj: Map<NodeIndex, Set<NodeIndex>> = new Map();
  private nodeData: Map<NodeIndex, NodeId> = new Map();
  private nextIndex = 0;

  /**
   * Add a node to the graph.
   * @returns The index assigned to the node.
   */
  addNode(data: NodeId): NodeIndex {
    const idx = this.nextIndex++;
    this.nodeData.set(idx, data);
    this.adjacency.set(idx, new Set());
    this.reverseAdj.set(idx, new Set());
    return idx;
  }

  /**
   * Add a directed edge from one node to another.
   */
  addEdge(from: NodeIndex, to: NodeIndex): void {
    this.adjacency.get(from)?.add(to);
    this.reverseAdj.get(to)?.add(from);
  }

  /**
   * Get the number of incoming edges to a node.
   */
  inDegree(idx: NodeIndex): number {
    return this.reverseAdj.get(idx)?.size ?? 0;
  }

  /**
   * Get the number of outgoing edges from a node.
   */
  outDegree(idx: NodeIndex): number {
    return this.adjacency.get(idx)?.size ?? 0;
  }

  /**
   * Check if the graph is a DAG (no cycles).
   */
  isDAG(): boolean {
    const inDegree = new Map<NodeIndex, number>();
    for (const idx of this.nodeData.keys()) {
      inDegree.set(idx, this.inDegree(idx));
    }

    const queue: NodeIndex[] = [];
    for (const [idx, deg] of inDegree) {
      if (deg === 0) queue.push(idx);
    }

    let processed = 0;
    while (queue.length > 0) {
      const node = queue.shift()!;
      processed++;
      for (const neighbor of this.adjacency.get(node) ?? []) {
        const newDeg = inDegree.get(neighbor)! - 1;
        inDegree.set(neighbor, newDeg);
        if (newDeg === 0) queue.push(neighbor);
      }
    }

    return processed === this.nodeData.size;
  }

  /**
   * Get topological generations (levels) for parallel execution.
   * Nodes in the same level have no dependencies on each other.
   */
  topologicalGenerations(): NodeIndex[][] {
    const inDegree = new Map<NodeIndex, number>();
    for (const idx of this.nodeData.keys()) {
      inDegree.set(idx, this.inDegree(idx));
    }

    const levels: NodeIndex[][] = [];
    let currentLevel: NodeIndex[] = [];

    // Start with all nodes that have no dependencies
    for (const [idx, deg] of inDegree) {
      if (deg === 0) currentLevel.push(idx);
    }

    while (currentLevel.length > 0) {
      levels.push(currentLevel);
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

    return levels;
  }

  /**
   * Get the data (NodeId) associated with an index.
   */
  getData(idx: NodeIndex): NodeId | undefined {
    return this.nodeData.get(idx);
  }
}

// ============ Graph Executor ============

export class GraphExecutor {
  private graph: SerialisableGraph;
  private nodeRegistry: NodeRegistry;
  private nodes: Map<NodeId, Base> = new Map();
  private inputNames: Map<NodeId, string[]> = new Map();
  private outputNames: Map<NodeId, string[]> = new Map();
  private dag: DiGraph = new DiGraph();
  private idToIdx: Map<NodeId, NodeIndex> = new Map();
  private idxToId: Map<NodeIndex, NodeId> = new Map();
  private _state: GraphExecutionState = GraphExecutionState.IDLE;
  private _cancellationReason: string | null = null;
  private _resultCallback: ResultCallback | null = null;
  private _activeTasks: Array<Promise<[NodeId, Record<string, unknown>]>> = [];

  constructor(graph: SerialisableGraph, nodeRegistry: NodeRegistry) {
    this.graph = graph;
    this.nodeRegistry = nodeRegistry;
    this.buildGraph();
  }

  /**
   * Build graph context for a node.
   */
  private buildGraphContext(nodeId: NodeId): Record<string, unknown> {
    return {
      graph_id: this.graph.id,
      nodes: this.graph.nodes ?? [],
      links: this.graph.links ?? [],
      current_node_id: nodeId,
    };
  }

  /**
   * Build the internal graph representation from the serialized graph.
   */
  private buildGraph(): void {
    const nodes = this.graph.nodes ?? [];

    for (const nodeData of nodes) {
      const nodeId = nodeData.id;
      const nodeType = nodeData.type;

      if (!(nodeType in this.nodeRegistry)) {
        throw new Error(`Unknown node type: ${nodeType}`);
      }

      const properties = nodeData.properties ?? {};
      const graphContext = this.buildGraphContext(nodeId);

      const NodeClass = this.nodeRegistry[nodeType] as new (
        id: number,
        params: Record<string, unknown>,
        graphContext?: Record<string, unknown>
      ) => Base;

      this.nodes.set(nodeId, new NodeClass(nodeId, properties, graphContext));

      const inputList = (nodeData.inputs ?? []).map((inp) => inp.name ?? '');
      if (inputList.length > 0) {
        this.inputNames.set(nodeId, inputList);
      }

      const outputList = (nodeData.outputs ?? []).map((out) => out.name ?? '');
      if (outputList.length > 0) {
        this.outputNames.set(nodeId, outputList);
      }

      const idx = this.dag.addNode(nodeId);
      this.idToIdx.set(nodeId, idx);
      this.idxToId.set(idx, nodeId);
    }

    const links = this.graph.links ?? [];
    for (const link of links) {
      const sLink = link as SerialisedLink;
      const fromId = sLink.origin_id;
      const toId = sLink.target_id;

      if (!this.idToIdx.has(fromId)) {
        console.warn(
          `Link ${sLink.id ?? 'unknown'} references non-existent origin node ${fromId}, skipping`
        );
        continue;
      }
      if (!this.idToIdx.has(toId)) {
        console.warn(
          `Link ${sLink.id ?? 'unknown'} references non-existent target node ${toId}, skipping`
        );
        continue;
      }

      this.dag.addEdge(this.idToIdx.get(fromId)!, this.idToIdx.get(toId)!);
    }

    if (!this.dag.isDAG()) {
      throw new Error('Graph contains cycles');
    }
  }

  // ============ Execution Flow ============

  /**
   * Execute the graph and return results.
   */
  async execute(): Promise<ExecutionResults> {
    const results: ExecutionResults = {};
    const levels = this.dag.topologicalGenerations();
    this._activeTasks = [];
    this._state = GraphExecutionState.RUNNING;

    try {
      await this.executeLevels(levels, results);
    } catch (e) {
      console.error(`Execution failed: ${e}`);
    } finally {
      await this.cleanupExecution();
    }

    return results;
  }

  /**
   * Execute all levels of the graph.
   */
  private async executeLevels(
    levels: NodeIndex[][],
    results: ExecutionResults
  ): Promise<void> {
    for (const level of levels) {
      if (this.shouldStop()) {
        break;
      }

      const tasks: Array<Promise<[NodeId, Record<string, unknown>]>> = [];

      for (const nodeIdx of level) {
        const nodeId = this.idxToId.get(nodeIdx)!;

        // Skip isolated nodes (no connections)
        if (this.dag.inDegree(nodeIdx) === 0 && this.dag.outDegree(nodeIdx) === 0) {
          continue;
        }

        // Check if any predecessor has failed - propagate error instead of running
        const predError = this.getPredecessorError(nodeId, results);
        if (predError) {
          console.log(`Skipping node ${nodeId} due to predecessor failure: ${predError}`);
          results[nodeId] = { error: predError };
          continue;
        }

        const node = this.nodes.get(nodeId)!;
        const inputs = this.getNodeInputs(nodeId, results);

        // Merge params with inputs (params as defaults for unfilled inputs)
        const mergedInputs: Record<string, unknown> = {};
        for (const [k, v] of Object.entries(node.params)) {
          if (k in node.inputs && !(k in inputs) && v !== null) {
            mergedInputs[k] = v;
          }
        }
        Object.assign(mergedInputs, inputs);

        const task = this.executeNodeWithErrorHandling(nodeId, node, mergedInputs);
        tasks.push(task);
        this._activeTasks.push(task);
      }

      if (tasks.length > 0) {
        if (this.shouldStop()) {
          break;
        }

        // Execute all tasks in parallel and process results as they complete
        const settledResults = await Promise.allSettled(tasks);

        for (const settledResult of settledResults) {
          if (this.shouldStop()) {
            break;
          }

          if (settledResult.status === 'fulfilled') {
            this.processLevelResult(settledResult.value, results);
          } else {
            console.error(`Task failed with exception: ${settledResult.reason}`);
          }
        }
      }
    }
  }

  /**
   * Process a single level result.
   */
  private processLevelResult(
    levelResult: [NodeId, Record<string, unknown>],
    results: ExecutionResults
  ): void {
    const [nodeId, output] = levelResult;
    const node = this.nodes.get(nodeId);

    if (!node) return;

    console.log(
      `RESULT_TRACE: Processing result for node ${nodeId}, type=${node.constructor.name}, category=${node.category}`
    );

    // Emit immediately for IO category nodes
    const shouldEmit = this.shouldEmitImmediately(node);
    const hasCallback = this._resultCallback !== null;

    console.log(
      `RESULT_TRACE: Node ${nodeId} - shouldEmit=${shouldEmit}, hasCallback=${hasCallback}`
    );

    if (shouldEmit && this._resultCallback) {
      console.log(`RESULT_TRACE: Emitting immediate result for node ${nodeId}`);
      this._resultCallback(nodeId, output);
    }

    results[nodeId] = output;
  }

  /**
   * Clean up execution state and cancel remaining tasks.
   */
  private async cleanupExecution(): Promise<void> {
    // In JavaScript, we can't forcibly cancel promises, but we can set the stop flag
    if (this.shouldStop()) {
      this._state = GraphExecutionState.STOPPED;
    }
  }

  /**
   * Execute a node with error handling.
   */
  private async executeNodeWithErrorHandling(
    nodeId: NodeId,
    node: Base,
    mergedInputs: Record<string, unknown>
  ): Promise<[NodeId, Record<string, unknown>]> {
    try {
      const outputs = await node.execute(mergedInputs);
      return [nodeId, outputs];
    } catch (e) {
      if (e instanceof NodeExecutionError) {
        if (e.originalError) {
          console.log(
            `ERROR_TRACE: Original exception: ${e.originalError.name}: ${e.originalError.message}`
          );
        }
        console.error(`Node ${nodeId} failed: ${e.message}`);
        return [nodeId, { error: e.message }];
      }
      const error = e instanceof Error ? e : new Error(String(e));
      console.log(
        `ERROR_TRACE: Unexpected exception in node ${nodeId}: ${error.name}: ${error.message}`
      );
      console.error(`Unexpected error in node ${nodeId}: ${error.message}`);
      return [nodeId, { error: `Unexpected error: ${error.message}` }];
    }
  }

  /**
   * Check if any predecessor of a node has failed.
   * Returns the error message if a predecessor failed, null otherwise.
   */
  private getPredecessorError(nodeId: NodeId, results: ExecutionResults): string | null {
    const links = this.graph.links ?? [];
    for (const link of links) {
      const sLink = link as SerialisedLink;
      if (sLink.target_id !== nodeId) {
        continue;
      }

      const predId = sLink.origin_id;
      const predResult = results[predId];
      if (predResult && 'error' in predResult && typeof predResult.error === 'string') {
        return `Predecessor node ${predId} failed: ${predResult.error}`;
      }
    }
    return null;
  }

  /**
   * Get inputs for a node from predecessor outputs.
   */
  private getNodeInputs(
    nodeId: NodeId,
    results: ExecutionResults
  ): Record<string, unknown> {
    const inputs: Record<string, unknown> = {};

    // Derive inputs from the link table
    const links = this.graph.links ?? [];
    for (const link of links) {
      const sLink = link as SerialisedLink;

      if (sLink.target_id !== nodeId) {
        continue;
      }

      const predId = sLink.origin_id;
      const outputSlot = sLink.origin_slot;
      const inputSlot = sLink.target_slot;

      const predNode = this.nodes.get(predId);
      if (!predNode) {
        continue;
      }

      const predOutputs =
        this.outputNames.get(predId) ?? Object.keys(predNode.outputs);
      if (outputSlot >= predOutputs.length) {
        continue;
      }

      const outputKey = predOutputs[outputSlot];
      if (!outputKey) {
        continue;
      }

      const predResult = results[predId];
      if (!predResult || !(outputKey in predResult)) {
        continue;
      }

      const value = predResult[outputKey];
      const nodeInputs =
        this.inputNames.get(nodeId) ?? Object.keys(this.nodes.get(nodeId)!.inputs);

      if (inputSlot < nodeInputs.length) {
        const inputKey = nodeInputs[inputSlot];
        if (inputKey) {
          inputs[inputKey] = value;
        }
      }
    }

    return inputs;
  }

  /**
   * Force stop execution immediately.
   */
  forceStop(reason = 'user'): void {
    if (
      this._state === GraphExecutionState.STOPPING ||
      this._state === GraphExecutionState.STOPPED
    ) {
      return;
    }

    this._state = GraphExecutionState.STOPPING;
    this._cancellationReason = reason;

    // Force stop all nodes
    console.log(`STOP_TRACE: Stopping ${this.nodes.size} nodes`);
    for (const [nodeId, node] of this.nodes) {
      console.log(`STOP_TRACE: Calling force_stop on node ${nodeId} (${node.constructor.name})`);
      node.forceStop();
    }

    console.log('STOP_TRACE: Force stop completed in GraphExecutor');
    this._state = GraphExecutionState.STOPPED;
  }

  /**
   * Stop execution (async wrapper for forceStop).
   */
  async stop(reason = 'user'): Promise<void> {
    console.log('STOP_TRACE: GraphExecutor.stop called');
    this.forceStop(reason);
  }

  // ============ State Management ============

  get state(): GraphExecutionState {
    return this._state;
  }

  get isRunning(): boolean {
    return this._state === GraphExecutionState.RUNNING;
  }

  get isStopping(): boolean {
    return this._state === GraphExecutionState.STOPPING;
  }

  get isStopped(): boolean {
    return this._state === GraphExecutionState.STOPPED;
  }

  get cancellationReason(): string | null {
    return this._cancellationReason;
  }

  private shouldStop(): boolean {
    return this._state === GraphExecutionState.STOPPING;
  }

  // ============ Configuration ============

  setProgressCallback(callback: ProgressCallback): void {
    for (const node of this.nodes.values()) {
      node.setProgressCallback(callback);
    }
  }

  setResultCallback(callback: ResultCallback): void {
    this._resultCallback = callback;
  }

  private shouldEmitImmediately(node: Base): boolean {
    const result = node.category === NodeCategory.IO;
    console.log(
      `RESULT_TRACE: _should_emit_immediately(node=${node.constructor.name}, category=${node.category}) -> ${result}`
    );
    return result;
  }
}
