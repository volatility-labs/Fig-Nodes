// types.ts - Extensible type registry for frontend

// Map of base type names to colors (hex or LiteGraph color names)
export const TYPE_COLORS: { [type: string]: string } = {
    'AssetSymbol': '#FF6D00',      // Orange for single symbols
    'AssetSymbolList': '#22A7F0',  // Blue for lists
    'str': '#E74C3C',             // Red for strings
    'int': '#2ECC71',             // Green for numbers
    'float': '#2ECC71',
    'dict': '#9B59B6',            // Purple for dicts
    'list': '#3498DB',            // Blue for generic lists
    'data': '#BDC3C7',            // Gray for generic data
    // Add more as needed
};

// Function to register a new type and color
export function registerType(typeName: string, color: string) {
    if (typeName in TYPE_COLORS) {
        console.warn(`Overwriting color for type ${typeName}`);
    }
    TYPE_COLORS[typeName] = color;
}

// Example registrations from backend types
registerType('AssetSymbol', TYPE_COLORS['AssetSymbol']);
registerType('AssetSymbolList', TYPE_COLORS['AssetSymbolList']);
// ... existing code ...

// Interface for backend-parsed type info (from server.py _parse_type)
export interface TypeInfo {
    base: string;
    subtype?: TypeInfo | null;
}

// Update getTypeColor to use TypeInfo
export function getTypeColor(typeInfo: TypeInfo): string {
    let baseType = typeInfo.base;
    let current = typeInfo;
    while (current.subtype) {
        baseType = `${baseType}<${current.subtype.base}>`;
        current = current.subtype;
    }
    return TYPE_COLORS[baseType] || '#FFFFFF';
}

