import { LGraphCanvas } from '@fig-node/litegraph';

export interface TypeInfo {
    base: string;
    subtype?: TypeInfo;
    key_type?: TypeInfo;
    value_type?: TypeInfo;
    subtypes?: TypeInfo[];
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
                    const typeString = this.parseType(typeInfo);
                    if (typeString && typeof typeString === 'string') {
                        types.add(typeString);
                    }
                }
            }

            // Extract from outputs
            if (nodeData.outputs) {
                for (const outputName in nodeData.outputs) {
                    const typeInfo = nodeData.outputs[outputName];
                    const typeString = this.parseType(typeInfo);
                    if (typeString && typeof typeString === 'string') {
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
                const color = this.getTypeColor(typeString);
                LGraphCanvas.link_type_colors[typeString] = color;
                this.registeredTypes.add(typeString);
            }
        }
    }

    /**
     * Parse type info into a canonical type string.
     * Returns 0 for wildcard types (Any).
     * This is the single source of truth for type string format.
     */
    parseType(typeInfo: unknown): string | number {
        if (!typeInfo) {
            return 0; // LiteGraph wildcard for "accept any"
        }

        // Handle plain string types
        if (typeof typeInfo === 'string') {
            const lower = typeInfo.toLowerCase();
            if (lower === 'any' || lower === 'typing.any') {
                return 0;
            }
            return typeInfo;
        }

        const typeInfoObj = typeInfo as TypeInfo;
        const baseName = typeof typeInfoObj.base === 'string' ? typeInfoObj.base : String(typeInfoObj.base ?? 'any');

        if (baseName === 'Any' || baseName === 'typing.Any' || baseName.toLowerCase() === 'any') {
            return 0;
        }

        // Handle union types - use comma separator for LiteGraph compatibility
        if (baseName === 'union' && typeInfoObj.subtypes) {
            const subs = typeInfoObj.subtypes.map((st) => this.parseType(st)).join(',');
            return subs;
        }

        // Handle dict types
        if (typeInfoObj.key_type && typeInfoObj.value_type) {
            const key = this.parseType(typeInfoObj.key_type);
            const val = this.parseType(typeInfoObj.value_type);
            return `dict<${key}, ${val}>`;
        }

        // Handle list/generic types with single subtype
        if (typeInfoObj.subtype) {
            const sub = this.parseType(typeInfoObj.subtype);
            return `${baseName}<${sub}>`;
        }

        // Handle types with multiple subtypes (non-union)
        if (typeInfoObj.subtypes && Array.isArray(typeInfoObj.subtypes) && typeInfoObj.subtypes.length > 0) {
            const subs = typeInfoObj.subtypes.map((st) => this.parseType(st)).join(', ');
            return `${baseName}<${subs}>`;
        }

        return baseName;
    }

    /**
     * Get color for a type (public API for BaseCustomNode)
     */
    getTypeColor(typeInfo: TypeInfo | string): string {
        // Parse to canonical type string
        const typeString = this.parseType(typeInfo);

        // Wildcard types get default color
        if (typeString === 0) {
            return this.hslFromHash(this.hashString('any'));
        }

        const typeStr = typeString as string;

        // Check overrides first
        if (this.typeColorOverrides.has(typeStr)) {
            return this.typeColorOverrides.get(typeStr)!;
        }

        // Generate deterministic color
        return this.hslFromHash(this.hashString(typeStr.toLowerCase()));
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
        for (const typeString of this.registeredTypes) {
            const color = this.getTypeColor(typeString);
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

