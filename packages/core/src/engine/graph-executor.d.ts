import { NodeRegistry, ProgressCallback, ResultCallback, SerialisableGraph, type CredentialProvider } from '../types';
type NodeId = number;
type ExecutionResults = Record<NodeId, Record<string, unknown>>;
export declare class GraphExecutor {
    private graph;
    private nodeRegistry;
    private credentials?;
    private nodes;
    private inputNames;
    private outputNames;
    private dag;
    private idToIdx;
    private idxToId;
    private incomingLinks;
    private _state;
    private _resultCallback;
    constructor(graph: SerialisableGraph, nodeRegistry: NodeRegistry, credentials?: CredentialProvider);
    private buildGraphContext;
    private buildGraph;
    execute(): Promise<ExecutionResults>;
    private executeNode;
    private getPredecessorError;
    private getNodeInputs;
    forceStop(_reason?: string): void;
    private shouldStop;
    setProgressCallback(callback: ProgressCallback): void;
    setResultCallback(callback: ResultCallback): void;
}
export {};
