import { describe, expect, test, beforeEach, vi } from 'vitest';
import { BaseCustomNode } from '../../nodes';

describe('Node UI Integration Tests', () => {
    beforeEach(() => {
        vi.restoreAllMocks();
        vi.resetModules();

        // Mock clipboard
        (globalThis as any).navigator = {
            clipboard: {
                writeText: vi.fn().mockResolvedValue(undefined)
            }
        };

        // Mock DOM
        document.createElement = vi.fn().mockImplementation((_tagName) => {
            const element = {
                id: '',
                className: '',
                textContent: '',
                innerHTML: '',
                style: {},
                value: '',
                addEventListener: vi.fn(),
                appendChild: vi.fn(),
                focus: vi.fn(),
                select: vi.fn(),
                click: vi.fn(),
                classList: { add: vi.fn(), remove: vi.fn(), contains: vi.fn() },
                setAttribute: vi.fn(),
                getAttribute: vi.fn(),
                scrollTop: 0,
                scrollHeight: 0
            };
            return element as any;
        });

        const mockBody = document.createElement('body');
        mockBody.appendChild = vi.fn();
        mockBody.removeChild = vi.fn();
        mockBody.contains = vi.fn().mockReturnValue(true);
        Object.defineProperty(document, 'body', { value: mockBody, writable: true });

        // Mock window
        (window as any).innerWidth = 1000;
        (window as any).innerHeight = 800;
    });

    function baseData() {
        return {
            category: 'test',
            inputs: { input: { base: 'str' } },
            outputs: { output: { base: 'str' } },
            params: [{ name: 'value', type: 'text', default: '' }],
        } as any;
    }

    test('BaseCustomNode widget creation and interaction', () => {
        const data = baseData();
        data.params = [
            { name: 'textParam', type: 'text', default: 'initial' },
            { name: 'numParam', type: 'number', default: 5, min: 0, max: 10 },
            { name: 'comboParam', type: 'combo', options: ['A', 'B', 'C'], default: 'A' }
        ];

        const node = new BaseCustomNode('TestNode', data, null as any);

        // Verify widgets were created
        expect(node.widgets).toHaveLength(3);
        expect(node.widgets?.[0]?.name).toBe('textParam: initial');
        expect(node.widgets?.[1]?.type).toBe('number');
        expect(node.widgets?.[2]?.type).toBe('button');

        // Test widget callbacks
        node.widgets?.[1]?.callback?.(7);
        expect(node.properties.numParam).toBe(7);

        // Test sync
        node.properties.comboParam = 'B';
        node.syncWidgetValues();
        expect(node.widgets?.[2]?.name).toBe('comboParam: B');
    });

    test('Node connection typing integration', () => {
        const sourceNode = new BaseCustomNode('Source', {
            inputs: {},
            outputs: { out: { base: 'str' } },
            params: []
        }, null as any);

        const targetNode = new BaseCustomNode('Target', {
            inputs: { input: { base: 'str' } },
            outputs: {},
            params: []
        }, null as any);

        const unionTargetNode = new BaseCustomNode('UnionTarget', {
            inputs: { input: { base: 'union', subtypes: [{ base: 'str' }, { base: 'int' }] } },
            outputs: {},
            params: []
        }, null as any);

        expect(sourceNode.outputs[0]?.type).toBe('str');
        expect(targetNode.inputs[0]?.type).toBe('str');
        expect(unionTargetNode.inputs[0]?.type).toBe('str,int');
    });

    test('Node error handling integration', () => {
        const node = new BaseCustomNode('TestNode', baseData(), {} as any);

        node.setError('Test error');
        expect(node.error).toBe('Test error');
        expect(node.color).toBe('#FF0000');

        node.setError('');
        expect(node.error).toBe('');
    });

    test('Node progress integration', () => {
        const node = new BaseCustomNode('TestNode', baseData(), {} as any);

        node.setProgress(50, 'Half done');
        expect(node.progress).toBe(50);
        expect(node.progressText).toBe('Half done');

        const mockCtx = {
            save: vi.fn(),
            restore: vi.fn(),
            fillRect: vi.fn(),
            strokeRect: vi.fn(),
            measureText: vi.fn(() => ({ width: 0 })),
            fillText: vi.fn(),
            beginPath: vi.fn()
        };

        const renderer = (node as any).renderer;
        const spy = vi.spyOn(renderer, 'drawProgressBar');

        node.onDrawForeground(mockCtx as any);
        expect(spy).toHaveBeenCalled();
    });

    test('Node widget synchronization integration', () => {
        const data = baseData();
        data.params = [
            { name: 'syncParam', type: 'number', default: 10 },
            { name: 'dropdownParam', type: 'combo', options: ['A', 'B', 'C'], default: 'A' }
        ];

        const node = new BaseCustomNode('TestNode', data, null as any);

        expect(node.properties.syncParam).toBe(10);
        expect(node.properties.dropdownParam).toBe('A');

        node.properties.syncParam = 20;
        node.properties.dropdownParam = 'B';

        node.syncWidgetValues();
        expect(node.widgets?.[0]?.value).toBe(20);
        expect(node.widgets?.[1]?.name).toBe('dropdownParam: B');
    });
});
