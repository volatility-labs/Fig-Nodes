export declare class NodeError extends Error {
    constructor(message: string);
}
export declare class NodeValidationError extends NodeError {
    constructor(nodeId: number, message: string);
}
export declare class NodeExecutionError extends NodeError {
    originalError?: Error;
    constructor(nodeId: number, message: string, originalError?: Error);
}
