import { describe, expect, test } from 'vitest';
import { constructTypeString, getTypeColor, registerTypeColorOverride, getTypeColorOverrides } from '../../types';

describe('types.ts', () => {
    test('getTypeColor returns deterministic color for AssetSymbol (override present)', () => {
        expect(getTypeColor({ base: 'AssetSymbol' })).toBe('#FF6D00');
    });

    test('constructTypeString handles dict, list, nested, and stream', () => {
        expect(constructTypeString({ base: 'str' })).toBe('str');
        expect(constructTypeString({ base: 'list', subtype: { base: 'str' } })).toBe('list<str>');
        expect(constructTypeString({ base: 'dict', key_type: { base: 'str' }, value_type: { base: 'float' } }))
            .toBe('dict<str, float>');
        expect(constructTypeString({ base: 'list', subtype: { base: 'dict', key_type: { base: 'str' }, value_type: { base: 'any' } } }))
            .toBe('list<dict<str, any>>');
        expect(constructTypeString({ base: 'OHLCVBundle', isStream: true })).toBe('stream<OHLCVBundle>');
        expect(constructTypeString({ base: 'multi', subtypes: [{ base: 'str' }, { base: 'int' }] }))
            .toBe('multi<str, int>');
    });

    test('getTypeColor generates an hsl color for unknown types', () => {
        const color = getTypeColor({ base: 'UnknownType' });
        expect(color.startsWith('hsl(')).toBe(true);
    });

    test('registerTypeColorOverride adds and overwrites overrides', () => {
        const key = 'CustomType';
        registerTypeColorOverride(key, '#ABCDEF');
        expect(getTypeColorOverrides()[key]).toBe('#ABCDEF');
        registerTypeColorOverride(key, '#123456');
        expect(getTypeColorOverrides()[key]).toBe('#123456');
    });
});
