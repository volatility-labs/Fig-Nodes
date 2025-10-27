
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
            const result = `${type}<${sub}>`;
            return result;
        } else if (typeInfoObj.subtypes && Array.isArray(typeInfoObj.subtypes) && typeInfoObj.subtypes.length > 0) {
            const subs = (typeInfoObj.subtypes as unknown[]).map((st) => this.parseType(st)).join(', ');
            const result = `${type}<${subs}>`;
            return result;
        } else if (typeInfoObj.key_type && typeInfoObj.value_type) {
            const key = this.parseType(typeInfoObj.key_type);
            const val = this.parseType(typeInfoObj.value_type);
            const result = `dict<${key}, ${val}>`;
            console.log(`[NodeTypeSystem] parseType: dict -> "${result}"`);
            return result;
        }
        console.log(`[NodeTypeSystem] parseType: simple type -> "${type}"`);
        return type;
    }

    static validateConnection(inputType: string | number, outputType: string | number): boolean {
        console.log(`[NodeTypeSystem] validateConnection: input="${inputType}", output="${outputType}"`);
        
        // Handle exact match first (includes same union types)
        if (inputType === outputType) {
            console.log(`[NodeTypeSystem] Exact match: true`);
            return true;
        }
        
        if (typeof inputType === 'string' && inputType.includes(' | ')) {
            if (outputType === 0) {
                console.log(`[NodeTypeSystem] Any output to union input: true`);
                return true; // Any can connect to union
            }
            const allowed = inputType.split(' | ').map(t => t.trim());
            console.log(`[NodeTypeSystem] Union input, allowed types:`, allowed);
            if (typeof outputType === 'string' && allowed.includes(outputType)) {
                console.log(`[NodeTypeSystem] Output matches union subtype: true`);
                return true;
            }
            console.log(`[NodeTypeSystem] Output does not match union subtype: false`);
            return false;
        }
        
        // Handle case where output is union but input is not
        if (typeof outputType === 'string' && outputType.includes(' | ')) {
            if (inputType === 0) {
                console.log(`[NodeTypeSystem] Any input to union output: true`);
                return true; // Any can connect to union
            }
            const allowed = outputType.split(' | ').map(t => t.trim());
            console.log(`[NodeTypeSystem] Union output, allowed types:`, allowed);
            if (typeof inputType === 'string' && allowed.includes(inputType)) {
                console.log(`[NodeTypeSystem] Input matches union subtype: true`);
                return true;
            }
            console.log(`[NodeTypeSystem] Input does not match union subtype: false`);
            return false;
        }
        
        // Default: allow if types match or any (0)
        const result = inputType === 0 || outputType === 0 || inputType === outputType;
        console.log(`[NodeTypeSystem] Default check: ${result}`);
        return result;
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
