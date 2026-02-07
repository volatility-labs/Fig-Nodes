// stores/type-colors.ts
// Deterministic type → color mapping for handles and edges.
// Ported from the deleted TypeColorRegistry service.

const overrides: Record<string, string> = {
  AssetSymbol: '#FF6D00',
};

function hashString(str: string): number {
  let h = 0x811c9dc5;
  for (let i = 0; i < str.length; i++) {
    h ^= str.charCodeAt(i);
    h = Math.imul(h, 0x01000193);
  }
  return h >>> 0;
}

function hslFromHash(hash: number): string {
  const hue = hash % 360;
  const sat = 55 + (hash >> 3) % 20;   // 55-74
  const light = 52 + (hash >> 5) % 16;  // 52-67
  return `hsl(${hue}, ${sat}%, ${light}%)`;
}

/** Return a deterministic color for a port/edge data type. */
export function typeColor(typeStr: string | undefined): string {
  if (!typeStr || typeStr.toLowerCase() === 'any') {
    return hslFromHash(hashString('any'));
  }
  if (overrides[typeStr]) return overrides[typeStr];
  return hslFromHash(hashString(typeStr.toLowerCase()));
}
