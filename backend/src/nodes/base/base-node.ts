// backend/nodes/base/base-node.ts
// Translated from: nodes/base/base_node.py

import { z, ZodSchema, ZodObject, ZodTypeAny } from 'zod';
import {
  DefaultParams,
  NodeCategory,
  NodeExecutionError,
  NodeInputs,
  NodeOutputs,
  NodeValidationError,
  ParamMeta,
  ProgressCallback,
  ProgressEvent,
  ProgressState,
} from '../../core/types';

/**
 * Abstract base class for all nodes.
 */
export abstract class Base {
  // Class-level defaults (override in subclasses)
  static inputs: NodeInputs = {};
  static outputs: NodeOutputs = {};
  static params_meta: ParamMeta[] = [];
  static default_params: DefaultParams = {};
  static required_keys: string[] = [];
  static CATEGORY: NodeCategory = NodeCategory.BASE;

  // Instance properties
  readonly id: number;
  params: Record<string, unknown>;
  inputs: NodeInputs;
  outputs: NodeOutputs;
  graphContext: Record<string, unknown>;

  protected _progressCallback: ProgressCallback | null = null;
  protected _isStopped = false;

  constructor(
    id: number,
    params: Record<string, unknown>,
    graphContext: Record<string, unknown> = {}
  ) {
    this.id = id;

    // Merge default params with provided params
    const defaultParams = (this.constructor as typeof Base).default_params;
    this.params = { ...defaultParams, ...(params ?? {}) };

    // Copy class-level inputs/outputs to instance
    this.inputs = { ...(this.constructor as typeof Base).inputs };
    this.outputs = { ...(this.constructor as typeof Base).outputs };

    this.graphContext = graphContext;
  }

  /**
   * Get the node category.
   */
  get category(): NodeCategory {
    return (this.constructor as typeof Base).CATEGORY;
  }

  /**
   * Normalize a value to a list.
   */
  protected static normalizeToList(value: unknown): unknown[] {
    if (value === null || value === undefined) {
      return [];
    }
    if (Array.isArray(value)) {
      return value;
    }
    return [value];
  }

  /**
   * Deduplicate items while preserving order.
   */
  protected static dedupePreserveOrder<T>(items: T[]): T[] {
    if (!items.length) {
      return [];
    }

    const result: T[] = [];
    const seen = new Set<unknown>();

    for (const item of items) {
      // For primitive values, use direct comparison
      // For objects, use JSON stringification as a simple hash
      const key = typeof item === 'object' ? JSON.stringify(item) : item;

      if (!seen.has(key)) {
        seen.add(key);
        result.push(item);
      }
    }

    return result;
  }

  /**
   * Check if a type is declared as a list/array.
   */
  protected static isDeclaredList(expectedType: unknown): boolean {
    // In TypeScript, we check if the type annotation indicates an array
    // This is a simplified check - actual implementation may use Zod schemas
    if (expectedType === null || expectedType === undefined) {
      return false;
    }
    if (Array.isArray(expectedType)) {
      return true;
    }
    if (typeof expectedType === 'string') {
      return expectedType.includes('[]') || expectedType.toLowerCase().includes('list');
    }
    return false;
  }

  /**
   * Collect multiple inputs with the same base key (e.g., input_0, input_1, ...).
   */
  collectMultiInput(key: string, inputs: Record<string, unknown>): unknown[] {
    const expectedType = this.inputs[key];

    // If not declared as List, just normalize the primary value to a list
    if (!Base.isDeclaredList(expectedType)) {
      return Base.normalizeToList(inputs[key]);
    }

    // Declared as List - collect primary and suffixed values into a single list
    const collected: unknown[] = [];
    collected.push(...Base.normalizeToList(inputs[key]));

    let i = 0;
    while (true) {
      const multiKey = `${key}_${i}`;
      if (!(multiKey in inputs)) {
        break;
      }
      collected.push(...Base.normalizeToList(inputs[multiKey]));
      i++;
    }

    return Base.dedupePreserveOrder(collected);
  }

  /**
   * Validate inputs against declared input types.
   * Uses Zod for runtime validation if schemas are defined.
   */
  validateInputs(inputs: Record<string, unknown>): void {
    const normalized: Record<string, unknown> = { ...inputs };

    // Collect multi-inputs
    for (const [key, expectedType] of Object.entries(this.inputs)) {
      if (key in normalized) {
        continue;
      }

      if (Base.isDeclaredList(expectedType)) {
        const collected = this.collectMultiInput(key, inputs);
        if (collected.length > 0) {
          normalized[key] = collected;
        }
      }
    }

    // Set undefined optional inputs to null
    for (const [key, expectedType] of Object.entries(this.inputs)) {
      if (!(key in normalized) && this.typeAllowsNull(expectedType)) {
        normalized[key] = null;
      }
    }

    // Perform validation
    // If subclass provides a Zod schema, use it; otherwise do basic presence check
    const schema = this.getInputSchema();
    if (schema) {
      const result = schema.safeParse(normalized);
      if (!result.success) {
        throw new NodeValidationError(
          this.id,
          `Input validation failed: ${result.error.message}`
        );
      }
    } else {
      // Basic validation: check required inputs are present
      for (const key of Object.keys(this.inputs)) {
        if (!(key in normalized) && !this.typeAllowsNull(this.inputs[key])) {
          throw new NodeValidationError(this.id, `Missing required input: ${key}`);
        }
      }
    }
  }

  /**
   * Get Zod schema for input validation.
   * Override in subclasses to provide specific validation.
   */
  protected getInputSchema(): ZodSchema | null {
    return null;
  }

  /**
   * Check if a type allows null values.
   */
  protected typeAllowsNull(tp: unknown): boolean {
    // Check if type annotation includes null/undefined/optional
    if (tp === null || tp === undefined) {
      return true;
    }
    if (typeof tp === 'string') {
      const lower = tp.toLowerCase();
      return lower.includes('null') || lower.includes('undefined') || lower.includes('optional');
    }
    return false;
  }

  /**
   * Validate outputs against declared output types.
   */
  protected validateOutputs(outputs: Record<string, unknown>): void {
    if (!this.outputs || Object.keys(this.outputs).length === 0) {
      return;
    }

    // Best-effort validation - only validate present outputs
    const schema = this.getOutputSchema();
    if (schema && outputs) {
      const presentFields = Object.keys(outputs).filter((k) => k in this.outputs);
      if (presentFields.length > 0) {
        const partialSchema = schema.partial();
        const result = partialSchema.safeParse(outputs);
        if (!result.success) {
          throw new TypeError(
            `Output validation failed for node ${this.id}: ${result.error.message}`
          );
        }
      }
    }
  }

  /**
   * Get Zod schema for output validation.
   * Override in subclasses to provide specific validation.
   */
  protected getOutputSchema(): ZodObject<Record<string, ZodTypeAny>> | null {
    return null;
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
   * Emit a progress event.
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
      node_id: this.id,
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
      `BaseNode: force_stop called for node ${this.id}, already stopped: ${this._isStopped}`
    );
    if (this._isStopped) {
      return; // Idempotent
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
      this.validateOutputs(result);
      this.emitProgress(ProgressState.DONE, 100.0, '');
      return result;
    } catch (e) {
      const error = e instanceof Error ? e : new Error(String(e));
      this.emitProgress(
        ProgressState.ERROR,
        100.0,
        `error: ${error.name}: ${error.message}`
      );
      throw new NodeExecutionError(this.id, 'Execution failed', error);
    }
  }

  /**
   * Core execution logic - implement in subclasses.
   * Do not add try/catch here; let base handle errors.
   */
  protected abstract executeImpl(inputs: Record<string, unknown>): Promise<Record<string, unknown>>;
}
