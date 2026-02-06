// src/types/errors.ts
// Node error classes

export class NodeError extends Error {
  constructor(message: string) {
    super(message);
    this.name = 'NodeError';
  }
}

export class NodeValidationError extends NodeError {
  constructor(nodeId: number, message: string) {
    super(`Node ${nodeId}: ${message}`);
    this.name = 'NodeValidationError';
  }
}

export class NodeExecutionError extends NodeError {
  originalError?: Error;

  constructor(nodeId: number, message: string, originalError?: Error) {
    super(`Node ${nodeId}: ${message}`);
    this.name = 'NodeExecutionError';
    this.originalError = originalError;
  }
}
