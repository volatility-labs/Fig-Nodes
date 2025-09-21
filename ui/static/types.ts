// types.ts - Extensible type registry for frontend

// Update TypeInfo interface
export interface TypeInfo {
    base: string;
    subtype?: TypeInfo;
    key_type?: TypeInfo;
    value_type?: TypeInfo;
    subtypes?: TypeInfo[];
    isStream?: boolean;
}

// Add function to construct type string
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

// Update getTypeColor to use constructTypeString
export function getTypeColor(typeInfo: TypeInfo): string {
    const typeString = constructTypeString(typeInfo);
    return TYPE_COLORS[typeString] || '#FFFFFF';
}

// Update TYPE_COLORS with constructed strings and add more from backend registry
export const TYPE_COLORS: { [type: string]: string } = {
    'AssetSymbol': '#FF6D00',
    'list<AssetSymbol>': '#22A7F0',
    'str': '#E74C3C',
    'int': '#2ECC71',
    'float': '#2ECC71',
    'dict<str, float>': '#9B59B6',  // For IndicatorDict
    'list<any>': '#3498DB',         // For AnyList
    'dict<str, any>': '#9B59B6',    // For ConfigDict
    'list<dict<str, any>>': '#BDC3C7',         // For OHLCV
    'dict<AssetSymbol, list<dict<str, any>>>': '#BDC3C7',  // For OHLCVBundle
    'any': '#FFFFFF',
    'list<str>': '#E74C3C',
};

// Update registerType to use constructed strings if needed
export function registerType(typeString: string, color: string) {
    if (typeString in TYPE_COLORS) {
        console.warn(`Overwriting color for type ${typeString}`);
    }
    TYPE_COLORS[typeString] = color;
}

// Example registrations
registerType('AssetSymbol', TYPE_COLORS['AssetSymbol']);
registerType('list<AssetSymbol>', TYPE_COLORS['list<AssetSymbol>']);
registerType('stream<OHLCVBundle>', '#FF00FF'); // Example for OHLCVStream
// Add registrations for other types if necessary

