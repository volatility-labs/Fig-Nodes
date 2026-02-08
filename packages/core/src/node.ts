// src/node.ts
// Core Node base class with NodeDefinition pattern

import { ClassicPreset } from 'rete';

import {
  NodeCategory,
  NodeExecutionError,
  type NodeInputs,
  type NodeOutputs,
  type NodeUIConfig,
  NodeValidationError,
  type ParamMeta,
  type ProgressCallback,
  type ProgressEvent,
  ProgressState,
  type CredentialProvider,
  CREDENTIAL_PROVIDER_KEY,
} from './types.js';

import { getOrCreateSocket } from './sockets.js';

// ============ NodeDefinition ============

export interface NodeDefinition {
  inputs?: NodeInputs;
  outputs?: NodeOutputs;
  params?: ParamMeta[];
  category?: NodeCategory;
  requiredCredentials?: string[];
  ui?: NodeUIConfig;
}

/**
 * Abstract base class for all nodes.
 * Extends ClassicPreset.Node so it can be used directly with Rete's NodeEditor and DataflowEngine.
 */
export abstract class Node extends ClassicPreset.Node {
  static definition: NodeDefinition = {};

  readonly nodeId: string;
  params: Record<string, unknown>;
  nodeInputs: NodeInputs;
  nodeOutputs: NodeOutputs;
  graphContext: Record<string, unknown>;

  protected _progressCallback: ProgressCallback | null = null;
  protected _isStopped = false;

  constructor(
    nodeId: string,
    params: Record<string, unknown>,
    graphContext: Record<string, unknown> = {}
  ) {
    super((new.target as typeof Node).name);

    this.nodeId = nodeId;

    // Read definition from the concrete class
    const def = (this.constructor as typeof Node).definition;

    // Derive defaults from params[].default (single source of truth)
    const defaults: Record<string, unknown> = {};
    for (const p of def.params ?? []) {
      if (p.default !== undefined) defaults[p.name] = p.default;
    }
    this.params = { ...defaults, ...(params ?? {}) };

    // Copy definition inputs/outputs to instance
    this.nodeInputs = { ...(def.inputs ?? {}) };
    this.nodeOutputs = { ...(def.outputs ?? {}) };

    this.graphContext = graphContext;

    // Register Rete inputs
    for (const [name, spec] of Object.entries(this.nodeInputs)) {
      const socket = getOrCreateSocket(spec);
      this.addInput(name, new ClassicPreset.Input(socket, name, spec.multi ?? false));
    }

    // Register Rete outputs
    for (const [name, spec] of Object.entries(this.nodeOutputs)) {
      const socket = getOrCreateSocket(spec);
      this.addOutput(name, new ClassicPreset.Output(socket, name));
    }
  }

  /**
   * Rete DataflowEngine entry point.
   */
  async data(inputs: Record<string, unknown[]>): Promise<Record<string, unknown>> {
    const flat: Record<string, unknown> = {};
    for (const [key, values] of Object.entries(inputs)) {
      const spec = this.nodeInputs[key];
      const isMulti = spec?.multi ?? false;
      flat[key] = isMulti
        ? (Array.isArray(values) ? values : [values])
        : (Array.isArray(values) && values.length > 0 ? values[0] : values);
    }
    const merged = { ...this.params };
    for (const [k, v] of Object.entries(flat)) {
      merged[k] = v;
    }
    return this.execute(merged);
  }

  get category(): NodeCategory {
    return (this.constructor as typeof Node).definition.category ?? NodeCategory.BASE;
  }

  get credentials(): CredentialProvider {
    const provider = this.graphContext[CREDENTIAL_PROVIDER_KEY] as CredentialProvider | undefined;
    if (!provider) {
      throw new Error(
        `No CredentialProvider available. Ensure GraphExecutor was constructed with a credentials parameter.`
      );
    }
    return provider;
  }

  get hasCredentialProvider(): boolean {
    return CREDENTIAL_PROVIDER_KEY in this.graphContext;
  }

  protected typeAllowsNull(tp: unknown): boolean {
    if (tp === null || tp === undefined) {
      return true;
    }
    if (typeof tp === 'object' && tp !== null && 'type' in tp) {
      const spec = tp as { type: string; optional?: boolean };
      return spec.type === 'any' || spec.optional === true;
    }
    return false;
  }

  validateInputs(inputs: Record<string, unknown>): void {
    for (const key of Object.keys(this.nodeInputs)) {
      const spec = this.nodeInputs[key];
      const isOptionalInput = spec?.optional === true || this.typeAllowsNull(spec);

      if (!(key in inputs)) {
        if (!isOptionalInput) {
          throw new NodeValidationError(this.nodeId, `Missing required input: ${key}`);
        }
      }
    }
  }

  setProgressCallback(callback: ProgressCallback): void {
    this._progressCallback = callback;
  }

  protected clampProgress(value: number): number {
    if (value < 0.0) return 0.0;
    if (value > 100.0) return 100.0;
    return value;
  }

  protected emitProgress(
    state: ProgressState,
    progress?: number,
    text = '',
    meta?: Record<string, unknown>
  ): void {
    if (!this._progressCallback) {
      return;
    }

    const event: ProgressEvent = {
      node_id: this.nodeId,
      state,
    };

    if (progress !== undefined) {
      event.progress = this.clampProgress(progress);
    }
    if (text) {
      event.text = text;
    }
    if (meta) {
      event.meta = meta;
    }

    this._progressCallback(event);
  }

  protected progress(percent: number, message = ''): void {
    this.emitProgress(ProgressState.UPDATE, percent, message);
  }

  forceStop(): void {
    console.debug(
      `Node: force_stop called for node ${this.nodeId}, already stopped: ${this._isStopped}`
    );
    if (this._isStopped) {
      return;
    }
    this._isStopped = true;
    this.emitProgress(ProgressState.STOPPED, 100.0, 'stopped');
  }

  protected get cancelled(): boolean {
    return this._isStopped;
  }

  async execute(inputs: Record<string, unknown>): Promise<Record<string, unknown>> {
    this.validateInputs(inputs);
    this.emitProgress(ProgressState.START, 0.0, '');

    try {
      const result = await this.run(inputs);
      this.emitProgress(ProgressState.DONE, 100.0, '');
      return result;
    } catch (e) {
      const error = e instanceof Error ? e : new Error(String(e));
      this.emitProgress(
        ProgressState.ERROR,
        100.0,
        `error: ${error.name}: ${error.message}`
      );
      throw new NodeExecutionError(this.nodeId, 'Execution failed', error);
    }
  }

  protected abstract run(inputs: Record<string, unknown>): Promise<Record<string, unknown>>;
}
