// src/nodes/base/base-node.ts
// Rete-native base node class

import { ClassicPreset } from 'rete';

import {
  DefaultParams,
  NodeCategory,
  NodeExecutionError,
  NodeInputs,
  NodeOutputs,
  NodeUIConfig,
  NodeValidationError,
  ParamMeta,
  ProgressCallback,
  ProgressEvent,
  ProgressState,
  type CredentialProvider,
  CREDENTIAL_PROVIDER_KEY,
} from '../../types';

import { parsePortType, validatePortValue } from '../../utils/type-utils';
import { getOrCreateSocket } from '../../sockets/socket-registry';

/**
 * Abstract base class for all nodes.
 * Extends ClassicPreset.Node so it can be used directly with Rete's NodeEditor and DataflowEngine.
 */
export abstract class Base extends ClassicPreset.Node {
  // Class-level defaults (override in subclasses)
  static inputs: NodeInputs = {};
  static outputs: NodeOutputs = {};

  static paramsMeta: ParamMeta[] = [];
  static defaultParams: DefaultParams = {};

  static required_keys: string[] = [];
  static CATEGORY: NodeCategory = NodeCategory.BASE;

  /**
   * UI configuration for the node (ComfyUI-style).
   */
  static uiConfig: NodeUIConfig = {
    size: [200, 100],
    displayResults: false,
    resizable: false,
  };

  // Instance properties
  readonly figNodeId: string;
  params: Record<string, unknown>;
  nodeInputs: NodeInputs;
  nodeOutputs: NodeOutputs;
  graphContext: Record<string, unknown>;

  protected _progressCallback: ProgressCallback | null = null;
  protected _isStopped = false;

  constructor(
    figNodeId: string,
    params: Record<string, unknown>,
    graphContext: Record<string, unknown> = {}
  ) {
    // Pass class name as label to Rete
    super((new.target as typeof Base).name);

    this.figNodeId = figNodeId;

    // Merge default params with provided params
    const defaults = (this.constructor as typeof Base).defaultParams;
    this.params = { ...defaults, ...(params ?? {}) };

    // Copy class-level inputs/outputs to instance
    this.nodeInputs = { ...(this.constructor as typeof Base).inputs };
    this.nodeOutputs = { ...(this.constructor as typeof Base).outputs };

    this.graphContext = graphContext;

    // Register Rete inputs from static inputs
    for (const [name, typeStr] of Object.entries(this.nodeInputs)) {
      const socket = getOrCreateSocket(String(typeStr));
      this.addInput(name, new ClassicPreset.Input(socket, name));
    }

    // Register Rete outputs from static outputs
    for (const [name, typeStr] of Object.entries(this.nodeOutputs)) {
      const socket = getOrCreateSocket(String(typeStr));
      this.addOutput(name, new ClassicPreset.Output(socket, name));
    }
  }

  /**
   * Rete DataflowEngine entry point.
   * Called by the engine to compute this node's outputs from its inputs.
   */
  async data(inputs: Record<string, unknown[]>): Promise<Record<string, unknown>> {
    // Flatten: Rete passes arrays (one per connection), take first value
    const flat: Record<string, unknown> = {};
    for (const [key, values] of Object.entries(inputs)) {
      flat[key] = Array.isArray(values) && values.length > 0 ? values[0] : values;
    }
    // Merge params as defaults for unconnected inputs
    const merged = { ...this.params };
    for (const [k, v] of Object.entries(flat)) {
      merged[k] = v;
    }
    return this.execute(merged);
  }

  /**
   * Get the node category.
   */
  get category(): NodeCategory {
    return (this.constructor as typeof Base).CATEGORY;
  }

  /**
   * Get the credential provider injected via graphContext.
   */
  get credentials(): CredentialProvider {
    const provider = this.graphContext[CREDENTIAL_PROVIDER_KEY] as CredentialProvider | undefined;
    if (!provider) {
      throw new Error(
        `No CredentialProvider available. Ensure GraphDocumentExecutor was constructed with a credentials parameter.`
      );
    }
    return provider;
  }

  /**
   * Check whether a credential provider is available.
   */
  get hasCredentialProvider(): boolean {
    return CREDENTIAL_PROVIDER_KEY in this.graphContext;
  }

  /**
   * Check if a type allows null values.
   */
  protected typeAllowsNull(tp: unknown): boolean {
    if (tp === null || tp === undefined) {
      return true;
    }
    if (typeof tp === 'string') {
      const lower = tp.toLowerCase();
      return lower === 'any' || lower.includes('null') || lower.includes('undefined') || lower.includes('optional');
    }
    return false;
  }

  /**
   * Validate that required inputs are present and type-check values against
   * declared port types.
   */
  validateInputs(inputs: Record<string, unknown>): void {
    for (const key of Object.keys(this.nodeInputs)) {
      const typeStr = this.nodeInputs[key];
      const parsed = typeof typeStr === 'string' ? parsePortType(typeStr) : null;

      if (!(key in inputs)) {
        if (!this.typeAllowsNull(typeStr)) {
          throw new NodeValidationError(this.figNodeId, `Missing required input: ${key}`);
        }
        continue;
      }

      if (typeof typeStr === 'string' && parsed) {
        const result = validatePortValue(inputs[key], typeStr);
        if (result !== true) {
          console.warn(
            `[Node ${this.figNodeId}] Input "${key}" type mismatch: ${result}`,
          );
        }
      }
    }
  }

  /**
   * Set a callback function to report progress during execution.
   */
  setProgressCallback(callback: ProgressCallback): void {
    this._progressCallback = callback;
  }

  /**
   * Clamp progress value to 0-100 range.
   */
  protected clampProgress(value: number): number {
    if (value < 0.0) return 0.0;
    if (value > 100.0) return 100.0;
    return value;
  }

  /**
   * Emit a progress event using figNodeId (the graph document ID).
   */
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
      node_id: this.figNodeId,
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

  /**
   * Convenience helper for subclasses to report an UPDATE event.
   */
  reportProgress(progress: number, text = ''): void {
    this.emitProgress(ProgressState.UPDATE, progress, text);
  }

  /**
   * Immediately terminate node execution and clean up resources. Idempotent.
   */
  forceStop(): void {
    console.debug(
      `BaseNode: force_stop called for node ${this.figNodeId}, already stopped: ${this._isStopped}`
    );
    if (this._isStopped) {
      return;
    }
    this._isStopped = true;
    this.emitProgress(ProgressState.STOPPED, 100.0, 'stopped');
  }

  /**
   * Check if execution has been stopped.
   */
  get isStopped(): boolean {
    return this._isStopped;
  }

  /**
   * Template method for execution with uniform error handling and progress lifecycle.
   */
  async execute(inputs: Record<string, unknown>): Promise<Record<string, unknown>> {
    this.validateInputs(inputs);
    this.emitProgress(ProgressState.START, 0.0, '');

    try {
      const result = await this.executeImpl(inputs);
      this.emitProgress(ProgressState.DONE, 100.0, '');
      return result;
    } catch (e) {
      const error = e instanceof Error ? e : new Error(String(e));
      this.emitProgress(
        ProgressState.ERROR,
        100.0,
        `error: ${error.name}: ${error.message}`
      );
      throw new NodeExecutionError(this.figNodeId, 'Execution failed', error);
    }
  }

  /**
   * Core execution logic - implement in subclasses.
   */
  protected abstract executeImpl(inputs: Record<string, unknown>): Promise<Record<string, unknown>>;
}
