// Type definitions for graph execution results
// These match the serialized types from Python's core/serialization.py

export type SerializedScalar = string;

export type SerializedValue =
    | SerializedScalar
    | { [key: string]: SerializedValue }
    | SerializedValue[]
    | Array<{ [key: string]: SerializedValue }>;

export type ExecutionResults = {
    [nodeId: string]: { [outputName: string]: SerializedValue };
};

