// src/utils/type-utils.ts
// Runtime type detection and inference

import {
  AssetSymbol,
  IndicatorValue,
  IndicatorResult,
} from '../types';

/**
 * Detect the type of a value and return a canonical type name.
 */
export function detectType(value: unknown): string {
  if (value === null || value === undefined) {
    return 'None';
  }

  // AssetSymbol instance
  if (value instanceof AssetSymbol) {
    return 'AssetSymbol';
  }

  // Check for IndicatorValue shape
  if (isIndicatorValue(value)) {
    return 'IndicatorValue';
  }

  // Check for IndicatorResult shape
  if (isIndicatorResult(value)) {
    return 'IndicatorResult';
  }

  // LLMChatMessage - has role and content
  if (isRecord(value) && 'role' in value && 'content' in value) {
    return 'LLMChatMessage';
  }

  // LLMToolSpec - type="function" and has function field
  if (isRecord(value) && value.type === 'function' && 'function' in value) {
    return 'LLMToolSpec';
  }

  // LLMChatMetrics - has metric keys
  if (isRecord(value)) {
    const metricKeys = [
      'total_duration',
      'load_duration',
      'prompt_eval_count',
      'prompt_eval_duration',
      'eval_count',
      'eval_duration',
      'error',
    ];
    if (metricKeys.some((key) => key in value)) {
      return 'LLMChatMetrics';
    }
  }

  // LLMToolHistoryItem - has call and result
  if (isRecord(value) && 'call' in value && 'result' in value) {
    return 'LLMToolHistoryItem';
  }

  // LLMThinkingHistoryItem - has thinking and iteration
  if (isRecord(value) && 'thinking' in value && 'iteration' in value) {
    return 'LLMThinkingHistoryItem';
  }

  // Built-in types
  if (typeof value === 'boolean') {
    return 'bool';
  }
  if (typeof value === 'number') {
    return Number.isInteger(value) ? 'int' : 'float';
  }
  if (typeof value === 'string') {
    return 'str';
  }
  if (Array.isArray(value)) {
    return 'list';
  }
  if (typeof value === 'object') {
    return 'dict';
  }

  return typeof value;
}

/**
 * Infer a high-level data type name for metadata purposes.
 */
export function inferDataType(data: unknown): string {
  if (data === null || data === undefined) {
    return 'None';
  }

  if (data instanceof AssetSymbol) {
    return 'AssetSymbol';
  }

  if (isIndicatorValue(data)) {
    return 'IndicatorValue';
  }

  if (isIndicatorResult(data)) {
    return 'IndicatorResult';
  }

  if (Array.isArray(data)) {
    if (data.length === 0) {
      return 'EmptyList';
    }

    const itemType = detectType(data[0]);

    if (itemType === 'AssetSymbol') {
      return 'AssetSymbolList';
    }
    if (itemType === 'LLMChatMessage') {
      return 'LLMChatMessageList';
    }
    if (itemType === 'IndicatorResult') {
      return 'IndicatorResultList';
    }

    return `List[${itemType}]`;
  }

  if (!isRecord(data)) {
    return detectType(data);
  }

  const keys = Object.keys(data);
  if (keys.length === 0) {
    return 'EmptyDict';
  }

  const firstKey = keys[0]!;
  const firstValue = data[firstKey];

  // Check for OHLCVBundle pattern: dict[string, OHLCVBar[]]
  if (Array.isArray(firstValue) && firstValue.length > 0) {
    const bar = firstValue[0];
    if (isRecord(bar)) {
      const barKeys = ['timestamp', 'open', 'high', 'low', 'close', 'volume'];
      if (barKeys.every((key) => key in bar)) {
        return 'OHLCVBundle';
      }
    }
  }

  return `Dict[${detectType(firstKey)}, ${detectType(firstValue)}]`;
}

// ============ Type Guards ============

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
}

function isIndicatorValue(value: unknown): value is IndicatorValue {
  if (!isRecord(value)) return false;
  return (
    'single' in value &&
    typeof value.single === 'number' &&
    'lines' in value &&
    isRecord(value.lines) &&
    'series' in value &&
    Array.isArray(value.series)
  );
}

function isIndicatorResult(value: unknown): value is IndicatorResult {
  if (!isRecord(value)) return false;
  return (
    'indicatorType' in value &&
    'values' in value &&
    isIndicatorValue(value.values)
  );
}

/**
 * Parse a TypeScript type representation into a structured format.
 */
export function parseTypeString(typeStr: string): Record<string, unknown> {
  const genericMatch = typeStr.match(/^(\w+)\[(.+)\]$/);

  if (!genericMatch) {
    return { base: typeStr };
  }

  const base = genericMatch[1]!;
  const inner = genericMatch[2]!;

  if (base.toLowerCase() === 'dict') {
    const parts = splitGenericArgs(inner);
    return {
      base: 'dict',
      key_type: parseTypeString(parts[0] ?? 'unknown'),
      value_type: parseTypeString(parts[1] ?? 'unknown'),
    };
  }

  if (['list', 'array', 'set'].includes(base.toLowerCase())) {
    return {
      base: base.toLowerCase(),
      subtypes: [parseTypeString(inner)],
    };
  }

  // Union types
  if (inner.includes('|')) {
    const unionTypes = inner.split('|').map((t) => t.trim());
    const subtypes = unionTypes
      .filter((t) => t !== 'null' && t !== 'undefined')
      .map(parseTypeString);

    if (subtypes.length === 1 && subtypes[0]) {
      return subtypes[0];
    }

    return { base: 'union', subtypes };
  }

  return { base, subtypes: [parseTypeString(inner)] };
}

// ============ Port Type Parsing & Compatibility ============

export interface ParsedPortType {
  types: string[];
  optional: boolean;
}

/**
 * Normalize a type name alias to its canonical form.
 * Maps Python-style names (returned by detectType) and common aliases to
 * canonical TS-style names used in port type declarations.
 */
const TYPE_ALIASES: Record<string, string> = {
  str: 'string',
  int: 'number',
  float: 'number',
  bool: 'boolean',
  list: 'array',
  dict: 'object',
};

/**
 * Domain-specific subtypes that are compatible with their base types.
 */
const SUBTYPE_MAP: Record<string, string> = {
  Score: 'number',
  Exchange: 'string',
  AssetSymbolList: 'array',
  LLMChatMessageList: 'array',
  LLMToolSpecList: 'array',
  LLMToolHistory: 'array',
  LLMThinkingHistory: 'array',
  IndicatorResultList: 'array',
  OHLCVBundle: 'object',
  IndicatorValue: 'object',
  IndicatorResult: 'object',
  LLMChatMessage: 'object',
  LLMToolSpec: 'object',
  LLMChatMetrics: 'object',
  LLMToolHistoryItem: 'object',
  LLMThinkingHistoryItem: 'object',
};

function normalizeTypeName(t: string): string {
  const trimmed = t.trim();
  return TYPE_ALIASES[trimmed] ?? trimmed;
}

/**
 * Parse a comma-separated port type string.
 * E.g. `"string,LLMChatMessage,optional"` → `{ types: ['string', 'LLMChatMessage'], optional: true }`
 */
export function parsePortType(typeStr: string): ParsedPortType {
  const parts = typeStr.split(',').map((s) => s.trim()).filter(Boolean);
  const optional = parts.includes('optional');
  const types = parts.filter((p) => p !== 'optional');
  return { types, optional };
}

/**
 * Check whether a single output type is compatible with a single input type.
 * After normalization, checks for exact match, then subtype relationships.
 */
function isSingleTypeCompatible(outputType: string, inputType: string): boolean {
  const normOut = normalizeTypeName(outputType);
  const normIn = normalizeTypeName(inputType);

  // Exact match after normalization
  if (normOut === normIn) return true;

  // Output is a subtype of the input's base type
  const outBase = SUBTYPE_MAP[outputType];
  if (outBase && normalizeTypeName(outBase) === normIn) return true;

  // Input is a subtype — allow if normalized bases match
  const inBase = SUBTYPE_MAP[inputType];
  if (inBase && normalizeTypeName(inBase) === normOut) return true;

  // Both are subtypes of the same base
  if (outBase && inBase && normalizeTypeName(outBase) === normalizeTypeName(inBase)) return true;

  return false;
}

/**
 * Check whether an output port type is compatible with an input port type.
 * Both are comma-separated strings (e.g. `"string"`, `"string,LLMChatMessage,optional"`).
 *
 * Rules:
 * - `"any"` on either side → always compatible
 * - Each output type must match at least one input union member
 * - `"optional"` is ignored (it's a presence-only concern)
 */
export function areTypesCompatible(outputTypeStr: string, inputTypeStr: string): boolean {
  const output = parsePortType(outputTypeStr);
  const input = parsePortType(inputTypeStr);

  // "any" on either side → always compatible
  if (output.types.some((t) => normalizeTypeName(t) === 'any')) return true;
  if (input.types.some((t) => normalizeTypeName(t) === 'any')) return true;

  // Every output type must match at least one input type
  for (const outType of output.types) {
    let matched = false;
    for (const inType of input.types) {
      if (isSingleTypeCompatible(outType, inType)) {
        matched = true;
        break;
      }
    }
    if (!matched) return false;
  }

  return true;
}

/**
 * Validate a runtime value against a port type string.
 * Returns `true` if valid, or a descriptive error string.
 */
export function validatePortValue(value: unknown, portTypeStr: string): true | string {
  const parsed = parsePortType(portTypeStr);

  // Optional port with null/undefined → valid
  if (parsed.optional && (value === null || value === undefined)) {
    return true;
  }

  // "any" type → always valid
  if (parsed.types.some((t) => normalizeTypeName(t) === 'any')) {
    return true;
  }

  const detectedType = detectType(value);

  // Check if the detected type is compatible with any declared type
  for (const declaredType of parsed.types) {
    if (isSingleTypeCompatible(detectedType, declaredType)) {
      return true;
    }
  }

  return `Expected ${parsed.types.join(' | ')}, got ${detectedType}`;
}

/**
 * Split generic arguments handling nested generics.
 */
function splitGenericArgs(args: string): string[] {
  const result: string[] = [];
  let current = '';
  let depth = 0;

  for (const char of args) {
    if (char === '[' || char === '<') {
      depth++;
      current += char;
    } else if (char === ']' || char === '>') {
      depth--;
      current += char;
    } else if (char === ',' && depth === 0) {
      result.push(current.trim());
      current = '';
    } else {
      current += char;
    }
  }

  if (current.trim()) {
    result.push(current.trim());
  }

  return result;
}
