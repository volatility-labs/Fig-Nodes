import { expect, test } from 'vitest';
import { getTypeColor } from '../types';

test('getTypeColor returns correct color for AssetSymbol', () => {
    expect(getTypeColor({ base: 'AssetSymbol' })).toBe('#FF6D00');
});
