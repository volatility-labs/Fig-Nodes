// src/utils/serialization.ts
// Graph execution result serialization
import { AssetSymbol } from '../types';
/**
 * Serialize a value to a JSON-safe format.
 */
export function serializeValue(v) {
    // Handle null/undefined
    if (v === null || v === undefined) {
        return 'None';
    }
    // Handle arrays
    if (Array.isArray(v)) {
        return v.map((item) => serializeValue(item));
    }
    // Handle AssetSymbol
    if (v instanceof AssetSymbol) {
        return serializeValue(v.toDict());
    }
    // Handle objects with toDict method
    if (typeof v === 'object' && v !== null && 'toDict' in v && typeof v.toDict === 'function') {
        try {
            const dict = v.toDict();
            return Object.fromEntries(Object.entries(dict).map(([k, val]) => [String(k), serializeValue(val)]));
        }
        catch {
            return String(v);
        }
    }
    // Handle plain objects
    if (typeof v === 'object' && v !== null) {
        return Object.fromEntries(Object.entries(v).map(([k, val]) => [
            String(k),
            serializeValue(val),
        ]));
    }
    // Handle primitives
    if (typeof v === 'string' || typeof v === 'number' || typeof v === 'boolean') {
        return String(v);
    }
    // Fallback for unhandled types
    console.warn(`Fallback to String() for unhandled type: ${typeof v}`);
    return String(v);
}
/**
 * Serialize graph execution results for WebSocket transmission.
 */
export function serializeResults(results) {
    const serializedResults = {};
    for (const [nodeId, nodeRes] of Object.entries(results)) {
        const nodeIdStr = String(nodeId);
        const serializedOutputs = {};
        for (const [outputName, outputValue] of Object.entries(nodeRes)) {
            serializedOutputs[outputName] = serializeValue(outputValue);
        }
        serializedResults[nodeIdStr] = serializedOutputs;
    }
    return serializedResults;
}
/**
 * Check if a value is a Map (OHLCVBundle).
 */
export function isOHLCVBundle(v) {
    return v instanceof Map;
}
/**
 * Serialize an OHLCV bundle (Map) to a plain object.
 */
export function serializeOHLCVBundle(bundle) {
    const result = {};
    for (const [key, value] of bundle) {
        result[key] = value;
    }
    return result;
}
