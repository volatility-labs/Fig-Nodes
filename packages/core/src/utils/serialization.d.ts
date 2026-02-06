export type SerializedScalar = string;
export interface SerializedObject {
    [key: string]: SerializedScalar | SerializedObject | SerializedArray;
}
export interface SerializedArray extends Array<SerializedScalar | SerializedObject | SerializedArray> {
}
export type SerializedValue = SerializedScalar | SerializedObject | SerializedArray;
export type ExecutionResults = Record<number, Record<string, unknown>>;
export type SerializedResults = Record<string, Record<string, SerializedValue>>;
/**
 * Serialize a value to a JSON-safe format.
 */
export declare function serializeValue(v: unknown): SerializedValue;
/**
 * Serialize graph execution results for WebSocket transmission.
 */
export declare function serializeResults(results: ExecutionResults): SerializedResults;
/**
 * Check if a value is a Map (OHLCVBundle).
 */
export declare function isOHLCVBundle(v: unknown): v is Map<string, unknown[]>;
/**
 * Serialize an OHLCV bundle (Map) to a plain object.
 */
export declare function serializeOHLCVBundle(bundle: Map<string, unknown[]>): Record<string, unknown[]>;
