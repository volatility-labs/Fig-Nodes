
export class NodeTypeSystem {
    static parseType(typeInfo: unknown): string | number {
        if (!typeInfo) {
            return 0; // LiteGraph wildcard for "accept any"
        }
        const typeInfoObj = typeInfo as Record<string, unknown>;
        const baseName = typeof typeInfoObj.base === 'string' ? typeInfoObj.base : String(typeInfoObj.base);
        if (baseName === 'Any' || baseName === 'typing.Any' || baseName.toLowerCase() === 'any') {
            return 0; // LiteGraph wildcard
        }
        if (baseName === 'union' && typeInfoObj.subtypes) {
            const subs = (typeInfoObj.subtypes as unknown[]).map((st) => this.parseType(st)).join(' | ');
            return subs;
        }
        const type = baseName;
        if (typeInfoObj.subtype) {
            const sub = this.parseType(typeInfoObj.subtype);
            return `${type}<${sub}>`;
        } else if (typeInfoObj.subtypes && Array.isArray(typeInfoObj.subtypes) && typeInfoObj.subtypes.length > 0) {
            const subs = (typeInfoObj.subtypes as unknown[]).map((st) => this.parseType(st)).join(', ');
            return `${type}<${subs}>`;
        } else if (typeInfoObj.key_type && typeInfoObj.value_type) {
            const key = this.parseType(typeInfoObj.key_type);
            const val = this.parseType(typeInfoObj.value_type);
            return `dict<${key}, ${val}>`;
        }
        return type;
    }

    static validateConnection(inputType: string | number, outputType: string | number): boolean {
        if (typeof inputType === 'string' && inputType.includes(' | ')) {
            if (outputType === 0) return true; // Any can connect to union
            const allowed = inputType.split(' | ').map(t => t.trim());
            if (typeof outputType === 'string' && allowed.includes(outputType)) {
                return true;
            }
            return false;
        }
        // Default: allow if types match or any (0)
        return inputType === 0 || outputType === 0 || inputType === outputType;
    }

    static getDefaultValue(param: string): unknown {
        const lowerParam = param.toLowerCase();
        if (lowerParam.includes('days') || lowerParam.includes('period')) return 14;
        if (lowerParam.includes('bool')) return true;
        return '';
    }

    static determineParamType(name: string): string {
        const lower = name.toLowerCase();
        if (lower.includes('period') || lower.includes('days')) return 'number';
        return 'text';
    }
}
