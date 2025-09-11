import { describe, expect, test } from 'vitest';
import { constructTypeString, getTypeColor, registerType, TYPE_COLORS } from '../types';

describe('types.ts', () => {
    test('getTypeColor returns correct color for AssetSymbol', () => {
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

    test('getTypeColor falls back to default for unknown types', () => {
        expect(getTypeColor({ base: 'UnknownType' })).toBe('#FFFFFF');
    });

    test('registerType adds and overwrites colors', () => {
        const key = 'CustomType';
        registerType(key, '#ABCDEF');
        expect(TYPE_COLORS[key]).toBe('#ABCDEF');
        registerType(key, '#123456');
        expect(TYPE_COLORS[key]).toBe('#123456');
    });
});
