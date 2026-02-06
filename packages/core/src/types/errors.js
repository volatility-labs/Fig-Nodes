// src/types/errors.ts
// Node error classes
export class NodeError extends Error {
    constructor(message) {
        super(message);
        this.name = 'NodeError';
    }
}
export class NodeValidationError extends NodeError {
    constructor(nodeId, message) {
        super(`Node ${nodeId}: ${message}`);
        this.name = 'NodeValidationError';
    }
}
export class NodeExecutionError extends NodeError {
    originalError;
    constructor(nodeId, message, originalError) {
        super(`Node ${nodeId}: ${message}`);
        this.name = 'NodeExecutionError';
        this.originalError = originalError;
    }
}
