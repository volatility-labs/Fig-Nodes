import { LGraphCanvas } from '@fig-node/litegraph';

export interface TypeInfo {
    base: string;
    subtype?: TypeInfo;
    key_type?: TypeInfo;
    value_type?: TypeInfo;
    subtypes?: TypeInfo[];
    isStream?: boolean;
}

export class TypeColorRegistry {
    private canvas: LGraphCanvas | null = null;
    private typeColorOverrides: Map<string, string> = new Map();
    private registeredTypes = new Set<string>();

    constructor() {
        // Initialize with default overrides
        this.typeColorOverrides.set('AssetSymbol', '#FF6D00');
    }

    /**
     * Initialize type colors from node metadata
     * Should be called after UIModuleLoader.registerNodes()
     */
    initialize(nodeMetadata: Record<string, any>, canvas: LGraphCanvas): void {
        this.canvas = canvas;
        const allTypes = this.extractAllTypes(nodeMetadata);
        this.registerTypeColors(allTypes);
    }

    /**
     * Extract all unique type strings from node metadata
     */
    private extractAllTypes(nodeMetadata: Record<string, any>): Set<string> {
        const types = new Set<string>();

        for (const nodeName in nodeMetadata) {
            const nodeData = nodeMetadata[nodeName];
            
            // Extract from inputs
            if (nodeData.inputs) {
                for (const inputName in nodeData.inputs) {
                    const typeInfo = nodeData.inputs[inputName];
                    const typeString = this.constructTypeString(typeInfo as TypeInfo);
                    if (typeString) {
                        types.add(typeString);
                    }
                }
            }

            // Extract from outputs
            if (nodeData.outputs) {
                for (const outputName in nodeData.outputs) {
                    const typeInfo = nodeData.outputs[outputName];
                    const typeString = this.constructTypeString(typeInfo as TypeInfo);
                    if (typeString) {
                        types.add(typeString);
                    }
                }
            }
        }

        return types;
    }

    /**
     * Register colors for all types in LGraphCanvas.link_type_colors
     */
    private registerTypeColors(types: Set<string>): void {
        if (!this.canvas) return;

        for (const typeString of types) {
            if (!this.registeredTypes.has(typeString)) {
                // Parse the type string back to TypeInfo for color computation
                const typeInfo = this.parseTypeStringToTypeInfo(typeString);
                const color = this.getTypeColor(typeInfo);
                LGraphCanvas.link_type_colors[typeString] = color;
                this.registeredTypes.add(typeString);
            }
        }
    }

    /**
     * Parse a type string back to TypeInfo (simplified parser)
     * This is used when we only have the string representation
     */
    private parseTypeStringToTypeInfo(typeString: string): TypeInfo {
        // Handle union types
        if (typeString.includes(' | ')) {
            const subtypes = typeString.split(' | ').map(sub => ({ base: sub.trim() }));
            return { base: 'union', subtypes };
        }

        // Handle stream types
        if (typeString.startsWith('stream<')) {
            const inner = typeString.slice(7, -1);
            return { base: inner, isStream: true };
        }

        // Handle dict types
        if (typeString.startsWith('dict<')) {
            const inner = typeString.slice(5, -1);
            const [keyPart, ...valueParts] = inner.split(',');
            const valuePart = valueParts.join(',').trim();
            if (keyPart) {
                return {
                    base: 'dict',
                    key_type: { base: keyPart.trim() },
                    value_type: { base: valuePart }
                };
            }
        }

        // Handle list types
        if (typeString.includes('<')) {
            const match = typeString.match(/^(\w+)<(.+)>$/);
            if (match && match[1] && match[2]) {
                const [, base, inner] = match;
                return {
                    base: base!,
                    subtype: { base: inner! }
                };
            }
        }

        // Simple type
        return { base: typeString };
    }

    /**
     * Construct type string from TypeInfo (public API)
     */
    constructTypeString(typeInfo: TypeInfo): string {
        let typeStr = typeInfo.base;
        
        if (typeInfo.isStream) {
            typeStr = `stream<${typeStr}>`;
        }

        // Handle union types (use pipe separator)
        if (typeInfo.base === 'union' && typeInfo.subtypes) {
            return typeInfo.subtypes.map(st => this.constructTypeString(st)).join(' | ');
        }

        if (typeInfo.key_type && typeInfo.value_type) {
            return `dict<${this.constructTypeString(typeInfo.key_type)}, ${this.constructTypeString(typeInfo.value_type)}>`;
        } else if (typeInfo.subtype) {
            return `${typeStr}<${this.constructTypeString(typeInfo.subtype)}>`;
        } else if (typeInfo.subtypes && typeInfo.subtypes.length > 0) {
            // For non-union types with subtypes, use comma separator
            return `${typeStr}<${typeInfo.subtypes.map(st => this.constructTypeString(st)).join(', ')}>`;
        }
        
        return typeStr;
    }

    /**
     * Get color for a type (public API for BaseCustomNode)
     */
    getTypeColor(typeInfo: TypeInfo): string {
        const typeString = this.constructTypeString(typeInfo);
        
        // Check overrides first
        if (this.typeColorOverrides.has(typeString)) {
            return this.typeColorOverrides.get(typeString)!;
        }

        // Generate deterministic color
        return this.hslFromHash(this.hashString(typeString.toLowerCase()));
    }

    /**
     * Register a type color override
     */
    registerOverride(typeString: string, color: string): void {
        this.typeColorOverrides.set(typeString, color);
        if (this.canvas && this.registeredTypes.has(typeString)) {
            LGraphCanvas.link_type_colors[typeString] = color;
        }
    }

    /**
     * Get all type color overrides
     */
    getOverrides(): Record<string, string> {
        const result: Record<string, string> = {};
        this.typeColorOverrides.forEach((color, type) => {
            result[type] = color;
        });
        return result;
    }

    /**
     * Refresh type colors (useful when theme changes)
     */
    refresh(): void {
        if (!this.canvas) return;

        // Re-register all known types
        const types = Array.from(this.registeredTypes);
        for (const typeString of types) {
            const typeInfo = this.parseTypeStringToTypeInfo(typeString);
            const color = this.getTypeColor(typeInfo);
            LGraphCanvas.link_type_colors[typeString] = color;
        }
    }

    /**
     * Hash string for deterministic color generation
     */
    private hashString(str: string): number {
        let h = 0x811c9dc5;
        for (let i = 0; i < str.length; i++) {
            h ^= str.charCodeAt(i);
            h = Math.imul(h, 0x01000193);
        }
        return h >>> 0;
    }

    /**
     * Generate HSL color from hash
     */
    private hslFromHash(hash: number): string {
        const hue = hash % 360;
        const sat = 55 + (hash >> 3) % 20; // 55-74
        const light = 52 + (hash >> 5) % 16; // 52-67
        return `hsl(${hue}, ${sat}%, ${light}%)`;
    }
}

