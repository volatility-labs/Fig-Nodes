// src/sockets.ts
// Socket registry and socket key helpers

import { ClassicPreset } from 'rete';
import { TYPE_ALIASES } from './type-registry.js';
import type { PortSpec } from './ports.js';

// ============ Socket Key Helpers ============

/**
 * Convert a declared port type (PortSpec or string) to a canonical socket key.
 */
export function getSocketKey(portOrStr: PortSpec | string): string {
  const typeName = typeof portOrStr === 'object' && portOrStr !== null
    ? portOrStr.type
    : portOrStr;

  const trimmed = typeName?.trim();
  if (!trimmed) return 'any';

  const alias = TYPE_ALIASES[trimmed];
  const canonical = alias ?? trimmed;
  return String(canonical).toLowerCase();
}

/**
 * Socket-level compatibility rule.
 */
export function areSocketKeysCompatible(sourceKey: string, targetKey: string): boolean {
  if (sourceKey === 'exec' || targetKey === 'exec') return sourceKey === targetKey;
  return sourceKey === 'any' || targetKey === 'any' || sourceKey === targetKey;
}

/**
 * Convenience wrapper for raw type strings.
 */
export function areSocketTypesCompatible(sourceTypeStr: string, targetTypeStr: string): boolean {
  return areSocketKeysCompatible(getSocketKey(sourceTypeStr), getSocketKey(targetTypeStr));
}

// ============ Socket Registry ============

const socketCache = new Map<string, ClassicPreset.Socket>();
const anySocket = new ClassicPreset.Socket('any');

/**
 * Get or create a ClassicPreset.Socket for a given PortSpec or type string.
 */
export function getOrCreateSocket(portOrStr: PortSpec | string): ClassicPreset.Socket {
  const primary = getSocketKey(portOrStr);

  if (primary === 'any') return anySocket;

  if (socketCache.has(primary)) return socketCache.get(primary)!;

  const socket = new ClassicPreset.Socket(primary);
  socketCache.set(primary, socket);
  return socket;
}

export { anySocket };
