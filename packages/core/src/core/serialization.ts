// backend/core/serialization.ts
// Translated from: core/serialization.py

import { AssetSymbol } from './types';

// Type definitions for serialized values
export type SerializedScalar = string;

// Using interface to avoid circular type reference
export interface SerializedObject {
  [key: string]: SerializedScalar | SerializedObject | SerializedArray;
}

export interface SerializedArray extends Array<SerializedScalar | SerializedObject | SerializedArray> {}

export type SerializedValue = SerializedScalar | SerializedObject | SerializedArray;

// Type aliases for input/output
export type ExecutionResults = Record<number, Record<string, unknown>>;
export type SerializedResults = Record<string, Record<string, SerializedValue>>;

/**
 * Serialize a value to a JSON-safe format.
 *
 * Handles:
 * - Primitives (string, number, boolean) -> string
 * - Arrays -> recursive serialization
 * - Objects -> recursive serialization with string keys
 * - AssetSymbol -> object representation
 * - Enum -> name/value
 */
export function serializeValue(v: unknown): SerializedValue {
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
      const dict = v.toDict() as Record<string, unknown>;
      return Object.fromEntries(
        Object.entries(dict).map(([k, val]) => [String(k), serializeValue(val)])
      );
    } catch {
      return String(v);
    }
  }

  // Handle plain objects
  if (typeof v === 'object' && v !== null) {
    return Object.fromEntries(
      Object.entries(v as Record<string, unknown>).map(([k, val]) => [
        String(k),
        serializeValue(val),
      ])
    );
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
 *
 * Converts node IDs from numbers to strings and recursively serializes
 * all output values to ensure they can be JSON-encoded.
 */
export function serializeResults(results: ExecutionResults): SerializedResults {
  const serializedResults: SerializedResults = {};

  for (const [nodeId, nodeRes] of Object.entries(results)) {
    // Node ID is already a string key from Object.entries
    const nodeIdStr = String(nodeId);

    // Serialize each output from this node
    const serializedOutputs: Record<string, SerializedValue> = {};
    for (const [outputName, outputValue] of Object.entries(nodeRes)) {
      serializedOutputs[outputName] = serializeValue(outputValue);
    }

    serializedResults[nodeIdStr] = serializedOutputs;
  }

  return serializedResults;
}

/**
 * Check if a value is a Map (equivalent to Python DataFrame check).
 * Since we're using Map<string, OHLCVBar[]> for OHLCVBundle,
 * this handles the bundle serialization case.
 */
export function isOHLCVBundle(v: unknown): v is Map<string, unknown[]> {
  return v instanceof Map;
}

/**
 * Serialize an OHLCV bundle (Map) to a plain object.
 */
export function serializeOHLCVBundle(bundle: Map<string, unknown[]>): Record<string, unknown[]> {
  const result: Record<string, unknown[]> = {};
  for (const [key, value] of bundle) {
    result[key] = value;
  }
  return result;
}
