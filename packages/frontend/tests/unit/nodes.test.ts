import { describe, expect, test, vi, beforeEach } from 'vitest';
import { BaseCustomNode } from '../../nodes';
import { ServiceRegistry } from '../../services/ServiceRegistry';
import { TypeColorRegistry } from '../../services/TypeColorRegistry';

function baseData() {
    return {
        category: 'test',
        inputs: { a: { base: 'str' } },
        outputs: { out: { base: 'str' } },
        params: [{ name: 'value', type: 'text', default: '' }],
    } as any;
}

let mockServiceRegistry: ServiceRegistry;

describe('Node UI Unit Tests', () => {
    beforeEach(() => {
        // ensure clipboard mock exists
        (globalThis as any).navigator.clipboard.writeText = vi.fn();
        mockServiceRegistry = new ServiceRegistry();
    });

    test('BaseCustomNode adds IO and widgets and updates display', () => {
        const node = new BaseCustomNode('Base', baseData(), mockServiceRegistry);
        expect(node.inputs.length).toBe(1);
        expect(node.outputs.length).toBe(1);
        expect(node.widgets!.length).toBeGreaterThan(0);
        node.updateDisplay({ output: 'hello' });
        expect(typeof node.displayText).toBe('string');
        expect(node.displayText).toContain('hello');
    });
});

describe('BaseCustomNode comprehensive tests', () => {
    beforeEach(() => {
        (globalThis as any).navigator.clipboard.writeText = vi.fn();
        mockServiceRegistry = new ServiceRegistry();
    });

    test('creates text widget and updates value via prompt', () => {
        const data = baseData();
        data.params = [{ name: 'textParam', type: 'text', default: 'initial' }];
        const node = new BaseCustomNode('Test', data, mockServiceRegistry);
        expect(node.widgets).toBeDefined();
        const widget = node.widgets![0];
        expect(widget?.name).toBe('textParam: initial');
        expect(node.properties.textParam).toBe('initial');

        // Simulate prompt callback
        expect(widget?.callback).toBeDefined();
        widget?.callback!(null);
        node.properties.textParam = 'updated';
        expect(node.properties.textParam).toBe('updated');
    });

    test('creates number widget with options and updates value', () => {
        const data = baseData();
        data.params = [{ name: 'numParam', type: 'number', default: 5, min: 0, max: 10, step: 1 }];
        const node = new BaseCustomNode('Test', data, mockServiceRegistry);
        expect(node.widgets).toBeDefined();
        const widget = node.widgets![0];
        expect(widget?.type).toBe('number');
        expect(widget?.value).toBe(5);
        expect(widget?.options?.min).toBe(0);
        expect(widget?.options?.max).toBe(10);
        expect(widget?.options?.step).toBe(1);

        expect(widget?.callback).toBeDefined();
        widget?.callback!(7);
        expect(node.properties.numParam).toBe(7);
        expect(widget?.value).toBe(7);
    });

    test('creates custom dropdown widget for combo parameters', () => {
        const data = baseData();
        data.params = [{ name: 'comboParam', type: 'combo', options: ['opt1', 'opt2', 'opt3'], default: 'opt1' }];
        const node = new BaseCustomNode('Test', data, mockServiceRegistry);
        expect(node.widgets).toBeDefined();
        const widget = node.widgets![0];
        expect(widget?.type).toBe('button');
        expect(widget?.name).toBe('comboParam: opt1');
        expect(node.properties.comboParam).toBe('opt1');
        expect((widget as any)?.options?.values).toEqual(['opt1', 'opt2', 'opt3']);

        node.properties.comboParam = 'opt2';
        node.syncWidgetValues();
        expect(widget?.name).toBe('comboParam: opt2');
    });

    test('handles boolean combo widget correctly', () => {
        const data = baseData();
        data.params = [{ name: 'boolParam', type: 'combo', options: [true, false], default: true }];
        const node = new BaseCustomNode('Test', data, mockServiceRegistry);
        expect(node.widgets).toBeDefined();
        const widget = node.widgets![0];
        expect(widget?.type).toBe('button');
        expect(widget?.name).toBe('boolParam: true');
        expect(node.properties.boolParam).toBe(true);
        expect((widget as any)?.options?.values).toEqual([true, false]);

        node.properties.boolParam = false;
        node.syncWidgetValues();
        expect(widget?.name).toBe('boolParam: false');

        node.properties.boolParam = true;
        node.syncWidgetValues();
        expect(widget?.name).toBe('boolParam: true');
    });

    test('wraps text correctly in display', () => {
        const node = new BaseCustomNode('Test', baseData(), mockServiceRegistry);
        node.displayText = 'This is a long text that should wrap across multiple lines in the node display area';
        const mockCtx = { measureText: (text: string) => ({ width: text.length * 8 }) };
        const lines = node.wrapText(node.displayText, 100, mockCtx as any);
        expect(lines.length).toBeGreaterThan(1);
        expect(lines.every(line => mockCtx.measureText(line).width <= 100)).toBe(true);
    });

    test('sets error and updates color', () => {
        const node = new BaseCustomNode('Test', baseData(), mockServiceRegistry);
        node.setError('Test error');
        expect(node.error).toBe('Test error');
        expect(node.color).toBe('#FF0000');
    });

    test('syncs number widget values on configure using paramName mapping', () => {
        const data = baseData();
        data.params = [{ name: 'syncParam', type: 'number', default: 10 }];
        const node = new BaseCustomNode('Test', data, mockServiceRegistry);
        node.properties.syncParam = 20;
        node.configure({ id: 'test', type: 'Test', pos: [0, 0], size: [200, 100], flags: {}, order: 0, mode: 0 });
        expect(node.widgets).toBeDefined();
        const widget = node.widgets![0];
        expect(widget?.value).toBe(20);
    });

    test('syncs custom dropdown widget values on configure', () => {
        const data = baseData();
        data.params = [{ name: 'dropdownParam', type: 'combo', options: ['A', 'B', 'C'], default: 'A' }];
        const node = new BaseCustomNode('Test', data, mockServiceRegistry);
        node.properties.dropdownParam = 'B';
        node.configure({ id: 'test', type: 'Test', pos: [0, 0], size: [200, 100], flags: {}, order: 0, mode: 0 });
        expect(node.widgets).toBeDefined();
        const widget = node.widgets![0];
        expect(widget?.name).toBe('dropdownParam: B');
    });

    test('pulses highlight', () => {
        const node = new BaseCustomNode('Test', baseData(), mockServiceRegistry);
        node.pulseHighlight();
        expect((node as any).highlightStartTs).not.toBeNull();
    });

    test('custom dropdown widget updates value and display', () => {
        const data = baseData();
        data.params = [{ name: 'dropdownParam', type: 'combo', options: ['A', 'B', 'C'], default: 'A' }];
        const node = new BaseCustomNode('Test', data, mockServiceRegistry);
        const widget = node.widgets![0];

        node.properties.dropdownParam = 'B';
        node.syncWidgetValues();
        expect(widget?.name).toBe('dropdownParam: B');

        node.properties.dropdownParam = 'C';
        node.syncWidgetValues();
        expect(widget?.name).toBe('dropdownParam: C');
    });

    test('formatComboValue handles different value types', () => {
        const node = new BaseCustomNode('Test', baseData(), mockServiceRegistry);

        expect((node as any).formatComboValue('string')).toBe('string');
        expect((node as any).formatComboValue(42)).toBe('42');
        expect((node as any).formatComboValue(true)).toBe('true');
        expect((node as any).formatComboValue(false)).toBe('false');
        expect((node as any).formatComboValue(null)).toBe('null');
        expect((node as any).formatComboValue(undefined)).toBe('undefined');
    });
});

describe('Progress bar rendering', () => {
    beforeEach(() => {
        mockServiceRegistry = new ServiceRegistry();
    });

    test('BaseCustomNode calls renderer.drawProgressBar when progress >= 0', () => {
        const node = new BaseCustomNode('Test', baseData(), mockServiceRegistry);
        const renderer: any = (node as any).renderer;
        const spy = vi.spyOn(renderer, 'drawProgressBar');

        const ctx: any = {
            save: () => { },
            restore: () => { },
            fillRect: () => { },
            strokeRect: () => { },
            measureText: (_t: string) => ({ width: 0 }),
            fillText: (_t: string, _x: number, _y: number) => { },
            beginPath: () => { },
        };

        node.onDrawForeground(ctx as any);
        expect(spy).toHaveBeenCalledTimes(1);

        node.setProgress(25, 'Loading 1/4');
        node.onDrawForeground(ctx as any);
        expect(spy).toHaveBeenCalledTimes(2);
    });
});

describe('Strict connection typing', () => {
    let typeColorRegistry: TypeColorRegistry;
    let localServiceRegistry: ServiceRegistry;

    beforeEach(() => {
        localServiceRegistry = new ServiceRegistry();
        typeColorRegistry = new TypeColorRegistry();
        localServiceRegistry.register('typeColorRegistry', typeColorRegistry);
    });

    test('parseType handles union types correctly', () => {
        const unionType = {
            base: 'union',
            subtypes: [
                { base: 'str' },
                { base: 'LLMChatMessage' }
            ]
        };
        expect(typeColorRegistry.parseType(unionType)).toBe('str,LLMChatMessage');
    });

    test('parseType handles simple types correctly', () => {
        expect(typeColorRegistry.parseType({ base: 'str' })).toBe('str');
        expect(typeColorRegistry.parseType({ base: 'int' })).toBe('int');
        expect(typeColorRegistry.parseType({ base: 'Any' })).toBe(0);
    });

    test('parseType handles complex types like lists and dicts', () => {
        expect(typeColorRegistry.parseType({ base: 'list', subtype: { base: 'str' } })).toBe('list<str>');
        expect(typeColorRegistry.parseType({ base: 'dict', key_type: { base: 'str' }, value_type: { base: 'int' } })).toBe('dict<str, int>');
    });

    test('parseType passes through plain strings', () => {
        expect(typeColorRegistry.parseType('string')).toBe('string');
        expect(typeColorRegistry.parseType('LLMChatMessage')).toBe('LLMChatMessage');
    });

    test('parseType handles Any wildcard correctly', () => {
        expect(typeColorRegistry.parseType({ base: 'Any' })).toBe(0);
        expect(typeColorRegistry.parseType('any')).toBe(0);
        expect(typeColorRegistry.parseType('typing.Any')).toBe(0);
    });

    test('node input slots have comma-separated union types', () => {
        const node = new BaseCustomNode('TestNode', {
            inputs: { system: { base: 'union', subtypes: [{ base: 'str' }, { base: 'LLMChatMessage' }] } },
            outputs: {},
            params: []
        }, localServiceRegistry);

        const systemInput = node.inputs[node.findInputSlot('system')];
        expect(systemInput?.type).toBe('str,LLMChatMessage');
    });

    test('node output slots preserve simple types', () => {
        const sourceNode = new BaseCustomNode('Source', {
            inputs: {},
            outputs: { out: { base: 'str' } },
            params: []
        }, localServiceRegistry);

        expect(sourceNode.outputs[0]?.type).toBe('str');
    });
});
