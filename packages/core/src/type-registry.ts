// src/type-registry.ts
import type { PortSpec } from './ports.js';

// ============ Type Registry ============

const _registry = new Set<string>([
  'any', 'string', 'number', 'boolean', 'object', 'array', 'exec',
  // Generic aliases (no domain deps)
  'Exchange', 'Timestamp', 'Score',
]);

/** Register a new port type name. Called by domain packages at module load time. */
export function registerType(name: string): void {
  _registry.add(name);
}

/** Check if a type name is registered. */
export function isRegisteredType(name: string): boolean {
  const resolved = TYPE_ALIASES[name] ?? name;
  return _registry.has(resolved);
}

/** All currently registered type names. */
export function getRegisteredTypes(): ReadonlySet<string> {
  return _registry;
}

// ============ Type Aliases ============

export const TYPE_ALIASES: Record<string, string> = {
  str: 'string',
  int: 'number',
  float: 'number',
  bool: 'boolean',
  list: 'array',
  dict: 'object',
};

// ============ Port Factory ============

/** Convenience factory: `port('OHLCVBundle', { multi: true })` -> PortSpec */
export function port(type: string, opts?: { multi?: boolean; optional?: boolean }): PortSpec {
  const spec: PortSpec = { type };
  if (opts?.multi) spec.multi = true;
  if (opts?.optional) spec.optional = true;
  return spec;
}

/** Shorthand factory for exec (control-flow) ports. */
export function execPort(): PortSpec {
  return { type: 'exec' };
}
