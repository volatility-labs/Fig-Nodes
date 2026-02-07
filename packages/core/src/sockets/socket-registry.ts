// src/sockets/socket-registry.ts
// Socket registry mapping type strings to ClassicPreset.Socket instances

import { ClassicPreset } from 'rete';

const socketCache = new Map<string, ClassicPreset.Socket>();
const anySocket = new ClassicPreset.Socket('any');

/**
 * Get or create a ClassicPreset.Socket for a given type string.
 * Parses the primary type from composite strings (e.g. "string,optional" → "string").
 * Returns the shared `anySocket` for "any" types.
 */
export function getOrCreateSocket(typeStr: string): ClassicPreset.Socket {
  // Parse primary type (first token before comma)
  const primary = typeStr.split(',')[0]!.trim().toLowerCase();

  if (primary === 'any') return anySocket;

  if (socketCache.has(primary)) return socketCache.get(primary)!;

  const socket = new ClassicPreset.Socket(primary);
  socketCache.set(primary, socket);
  return socket;
}

export { anySocket };
