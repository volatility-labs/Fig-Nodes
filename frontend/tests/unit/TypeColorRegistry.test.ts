import { describe, expect, test } from 'vitest';
import { TypeColorRegistry, TypeInfo } from '../../services/TypeColorRegistry';

describe('TypeColorRegistry', () => {
    let registry: TypeColorRegistry;

    beforeEach(() => {
        registry = new TypeColorRegistry();
    });

    test('getTypeColor returns deterministic color for AssetSymbol (override present)', () => {
        expect(registry.getTypeColor({ base: 'AssetSymbol' })).toBe('#FF6D00');
    });

    test('constructTypeString handles dict, list, nested, and stream', () => {
        expect(registry.constructTypeString({ base: 'str' })).toBe('str');
        expect(registry.constructTypeString({ base: 'list', subtype: { base: 'str' } })).toBe('list<str>');
        expect(registry.constructTypeString({ base: 'dict', key_type: { base: 'str' }, value_type: { base: 'float' } }))
            .toBe('dict<str, float>');
        expect(registry.constructTypeString({ base: 'list', subtype: { base: 'dict', key_type: { base: 'str' }, value_type: { base: 'any' } } }))
            .toBe('list<dict<str, any>>');
        expect(registry.constructTypeString({ base: 'OHLCVBundle', isStream: true })).toBe('stream<OHLCVBundle>');
        expect(registry.constructTypeString({ base: 'multi', subtypes: [{ base: 'str' }, { base: 'int' }] }))
            .toBe('multi<str, int>');
    });

    test('constructTypeString handles union types with pipe separator', () => {
        expect(registry.constructTypeString({ base: 'union', subtypes: [{ base: 'str' }, { base: 'int' }] }))
            .toBe('str | int');
    });

    test('getTypeColor generates an hsl color for unknown types', () => {
        const color = registry.getTypeColor({ base: 'UnknownType' });
        expect(color.startsWith('hsl(')).toBe(true);
    });

    test('registerOverride adds and overwrites overrides', () => {
        const key = 'CustomType';
        registry.registerOverride(key, '#ABCDEF');
        expect(registry.getOverrides()[key]).toBe('#ABCDEF');
        registry.registerOverride(key, '#123456');
        expect(registry.getOverrides()[key]).toBe('#123456');
    });

    test('getOverrides returns all registered overrides', () => {
        registry.registerOverride('Type1', '#111111');
        registry.registerOverride('Type2', '#222222');
        const overrides = registry.getOverrides();
        expect(overrides.Type1).toBe('#111111');
        expect(overrides.Type2).toBe('#222222');
        expect(overrides.AssetSymbol).toBe('#FF6D00'); // Default override
    });
});

