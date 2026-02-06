// backend/nodes/base/base-node.ts
// Translated from: nodes/base/base_node.py
import { NodeCategory, NodeExecutionError, NodeValidationError, ProgressState, CREDENTIAL_PROVIDER_KEY, } from '../../types';
/**
 * Abstract base class for all nodes.
 */
export class Base {
    // Class-level defaults (override in subclasses)
    static inputs = {};
    static outputs = {};
    static paramsMeta = [];
    static defaultParams = {};
    static required_keys = [];
    static CATEGORY = NodeCategory.BASE;
    /**
     * UI configuration for the node (ComfyUI-style).
     *
     * IMPORTANT: All subclasses MUST override this with their own uiConfig.
     * This ensures consistent UI behavior and serves as implicit documentation.
     * The NodeRegistry will warn if a node doesn't define its own uiConfig.
     *
     * @example
     * static uiConfig: NodeUIConfig = {
     *   size: [240, 120],
     *   displayResults: false,
     *   resizable: true,
     * };
     */
    static uiConfig = {
        size: [200, 100],
        displayResults: false,
        resizable: false,
    };
    // Instance properties
    id;
    params;
    inputs;
    outputs;
    graphContext;
    _progressCallback = null;
    _isStopped = false;
    constructor(id, params, graphContext = {}) {
        this.id = id;
        // Merge default params with provided params
        const defaults = this.constructor.defaultParams;
        this.params = { ...defaults, ...(params ?? {}) };
        // Copy class-level inputs/outputs to instance
        this.inputs = { ...this.constructor.inputs };
        this.outputs = { ...this.constructor.outputs };
        this.graphContext = graphContext;
    }
    /**
     * Get the node category.
     */
    get category() {
        return this.constructor.CATEGORY;
    }
    /**
     * Get the credential provider injected via graphContext.
     * Throws if no provider was injected.
     */
    get credentials() {
        const provider = this.graphContext[CREDENTIAL_PROVIDER_KEY];
        if (!provider) {
            throw new Error(`No CredentialProvider available. Ensure GraphExecutor was constructed with a credentials parameter.`);
        }
        return provider;
    }
    /**
     * Check whether a credential provider is available (safe for optional keys).
     */
    get hasCredentialProvider() {
        return CREDENTIAL_PROVIDER_KEY in this.graphContext;
    }
    /**
     * Check if a type allows null values.
     */
    typeAllowsNull(tp) {
        if (tp === null || tp === undefined) {
            return true;
        }
        if (typeof tp === 'string') {
            const lower = tp.toLowerCase();
            // 'any' type accepts all values including null/undefined
            return lower === 'any' || lower.includes('null') || lower.includes('undefined') || lower.includes('optional');
        }
        return false;
    }
    /**
     * Validate that required inputs are present.
     */
    validateInputs(inputs) {
        for (const key of Object.keys(this.inputs)) {
            if (!(key in inputs) && !this.typeAllowsNull(this.inputs[key])) {
                throw new NodeValidationError(this.id, `Missing required input: ${key}`);
            }
        }
    }
    /**
     * Set a callback function to report progress during execution.
     */
    setProgressCallback(callback) {
        this._progressCallback = callback;
    }
    /**
     * Clamp progress value to 0-100 range.
     */
    clampProgress(value) {
        if (value < 0.0)
            return 0.0;
        if (value > 100.0)
            return 100.0;
        return value;
    }
    /**
     * Emit a progress event.
     */
    emitProgress(state, progress, text = '', meta) {
        if (!this._progressCallback) {
            return;
        }
        const event = {
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
    reportProgress(progress, text = '') {
        this.emitProgress(ProgressState.UPDATE, progress, text);
    }
    /**
     * Immediately terminate node execution and clean up resources. Idempotent.
     */
    forceStop() {
        console.debug(`BaseNode: force_stop called for node ${this.id}, already stopped: ${this._isStopped}`);
        if (this._isStopped) {
            return; // Idempotent
        }
        this._isStopped = true;
        this.emitProgress(ProgressState.STOPPED, 100.0, 'stopped');
    }
    /**
     * Check if execution has been stopped.
     */
    get isStopped() {
        return this._isStopped;
    }
    /**
     * Template method for execution with uniform error handling and progress lifecycle.
     */
    async execute(inputs) {
        this.validateInputs(inputs);
        this.emitProgress(ProgressState.START, 0.0, '');
        try {
            const result = await this.executeImpl(inputs);
            this.emitProgress(ProgressState.DONE, 100.0, '');
            return result;
        }
        catch (e) {
            const error = e instanceof Error ? e : new Error(String(e));
            this.emitProgress(ProgressState.ERROR, 100.0, `error: ${error.name}: ${error.message}`);
            throw new NodeExecutionError(this.id, 'Execution failed', error);
        }
    }
}
