import { DefaultParams, NodeCategory, NodeInputs, NodeOutputs, NodeUIConfig, ParamMeta, ProgressCallback, ProgressState, type CredentialProvider } from '../../types';
/**
 * Abstract base class for all nodes.
 */
export declare abstract class Base {
    static inputs: NodeInputs;
    static outputs: NodeOutputs;
    static paramsMeta: ParamMeta[];
    static defaultParams: DefaultParams;
    static required_keys: string[];
    static CATEGORY: NodeCategory;
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
    static uiConfig: NodeUIConfig;
    readonly id: number;
    params: Record<string, unknown>;
    inputs: NodeInputs;
    outputs: NodeOutputs;
    graphContext: Record<string, unknown>;
    protected _progressCallback: ProgressCallback | null;
    protected _isStopped: boolean;
    constructor(id: number, params: Record<string, unknown>, graphContext?: Record<string, unknown>);
    /**
     * Get the node category.
     */
    get category(): NodeCategory;
    /**
     * Get the credential provider injected via graphContext.
     * Throws if no provider was injected.
     */
    get credentials(): CredentialProvider;
    /**
     * Check whether a credential provider is available (safe for optional keys).
     */
    get hasCredentialProvider(): boolean;
    /**
     * Check if a type allows null values.
     */
    protected typeAllowsNull(tp: unknown): boolean;
    /**
     * Validate that required inputs are present.
     */
    validateInputs(inputs: Record<string, unknown>): void;
    /**
     * Set a callback function to report progress during execution.
     */
    setProgressCallback(callback: ProgressCallback): void;
    /**
     * Clamp progress value to 0-100 range.
     */
    protected clampProgress(value: number): number;
    /**
     * Emit a progress event.
     */
    protected emitProgress(state: ProgressState, progress?: number, text?: string, meta?: Record<string, unknown>): void;
    /**
     * Convenience helper for subclasses to report an UPDATE event.
     */
    reportProgress(progress: number, text?: string): void;
    /**
     * Immediately terminate node execution and clean up resources. Idempotent.
     */
    forceStop(): void;
    /**
     * Check if execution has been stopped.
     */
    get isStopped(): boolean;
    /**
     * Template method for execution with uniform error handling and progress lifecycle.
     */
    execute(inputs: Record<string, unknown>): Promise<Record<string, unknown>>;
    /**
     * Core execution logic - implement in subclasses.
     * Do not add try/catch here; let base handle errors.
     */
    protected abstract executeImpl(inputs: Record<string, unknown>): Promise<Record<string, unknown>>;
}
