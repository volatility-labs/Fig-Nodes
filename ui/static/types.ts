// types.ts - Frontend type helpers: string construction + color mapping

export interface TypeInfo {
    base: string;
    subtype?: TypeInfo;
    key_type?: TypeInfo;
    value_type?: TypeInfo;
    subtypes?: TypeInfo[];
    isStream?: boolean;
}

export function constructTypeString(typeInfo: TypeInfo): string {
    let typeStr = typeInfo.base;
    if (typeInfo.isStream) {
        typeStr = `stream<${typeStr}>`;
    }
    if (typeInfo.key_type && typeInfo.value_type) {
        return `dict<${constructTypeString(typeInfo.key_type)}, ${constructTypeString(typeInfo.value_type)}>`;
    } else if (typeInfo.subtype) {
        return `${typeStr}<${constructTypeString(typeInfo.subtype)}>`;
    } else if (typeInfo.subtypes && typeInfo.subtypes.length > 0) {
        return `${typeStr}<${typeInfo.subtypes.map(constructTypeString).join(', ')}>`;
    }
    return typeStr;
}

// Deterministic color from type string with optional overrides.
// This avoids manual syncing with backend type registry.
const TYPE_COLOR_OVERRIDES: { [type: string]: string } = {
    // Example curated overrides for core types (optional)
    'AssetSymbol': '#FF6D00',
};

function hashString(str: string): number {
    // Small, fast 32-bit hash (FNV-1a variant)
    let h = 0x811c9dc5;
    for (let i = 0; i < str.length; i++) {
        h ^= str.charCodeAt(i);
        h = Math.imul(h, 0x01000193);
    }
    return h >>> 0;
}

function hslFromHash(hash: number): string {
    const hue = hash % 360;
    const sat = 55 + (hash >> 3) % 20; // 55-74
    const light = 52 + (hash >> 5) % 16; // 52-67
    return `hsl(${hue}, ${sat}%, ${light}%)`;
}

export function getTypeColor(typeInfo: TypeInfo): string {
    const typeString = constructTypeString(typeInfo);
    if (TYPE_COLOR_OVERRIDES[typeString]) return TYPE_COLOR_OVERRIDES[typeString];
    return hslFromHash(hashString(typeString.toLowerCase()));
}

export function registerTypeColorOverride(typeString: string, color: string) {
    TYPE_COLOR_OVERRIDES[typeString] = color;
}

export function getTypeColorOverrides(): { [type: string]: string } {
    return { ...TYPE_COLOR_OVERRIDES };
}
